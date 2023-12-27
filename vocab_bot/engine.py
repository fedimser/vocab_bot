import copy
import csv
import logging
import random
import typing as tp
from dataclasses import dataclass
from pathlib import Path

from .storage import VocabBotStorage, ItemLearnState, UserStorageInfo
from .user_screens import (Question, SessionSummary, HomeScreen, VocabSelect, MessageBox,
                           UserScreen, HelpScreen)
from .utils import get_cur_time, secs_to_interval

# Number of "boxes"
# Box 0 is new, box NUM_BOXES-1 is learned (won't be asked anymore).
NUM_BOXES = 5
WAIT_TIMES_HR = [0, 1 * 24, 7 * 24, 16 * 24, 1000000]


@dataclass(frozen=True)
class VocabItem:
    foreign: str  # 1st column in CSV.
    native: str  # 2nd column in CSV.
    extra_info: tp.Optional[str]  # Pronunciation, or anything else (3rd optional column in CSV).


@dataclass(frozen=True)
class Vocab:
    id: str
    items: list[VocabItem]
    private_user_ids: tp.Optional[set[int]]

    @staticmethod
    def load_from_csv(id: str, path: Path):
        items = []  # type: list[VocabItem]
        private_user_ids = None
        with open(path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                assert 2 <= len(row) <= 3
                if row[0] == "__private_user_ids__":
                    private_user_ids = set(int(uid) for uid in row[1].split(","))
                    continue
                elif row[0].startswith("__"):
                    continue
                native = row[1].strip()
                if "," in native:
                    synonyms = [w.strip() for w in native.split(",")]
                    native = ",".join(synonyms[:3])
                extra_info = None if len(row) == 2 else row[2]
                items.append(VocabItem(foreign=row[0], native=native, extra_info=extra_info))
        return Vocab(id=id, items=items, private_user_ids=private_user_ids)

    def get_items(self, idxs: tp.Sequence[int]) -> list[VocabItem]:
        return [self.items[idx] for idx in idxs]

    def is_visible(self, user_id: int):
        if self.private_user_ids is None:
            return True
        else:
            return user_id in self.private_user_ids


@dataclass
class LearningSession:
    """
    Based on Spaced repetition technique (https://en.wikipedia.org/wiki/Spaced_repetition).
    """

    def __init__(self, user_vocab: 'UserVocab', items_idx: list[int]):
        self.user_vocab = user_vocab
        self.items_idx = items_idx
        self.not_answered = copy.copy(items_idx)
        self.wrong_guesses = set()  # type: set[int]
        self.quest_prompt = ""
        self.quest_correct_answer = ""
        self.quest_extra_info = None  # type: tp.Optional[str]
        self.quest_item_idx = -1
        self.quest_correct_option = -1
        self.prev_correct: tp.Optional[bool] = None

    def answer_question(self, option: int):
        if option == self.quest_correct_option:
            assert self.quest_item_idx in self.not_answered
            self.not_answered.remove(self.quest_item_idx)
            self.prev_correct = True
        else:
            self.wrong_guesses.add(self.quest_item_idx)
            self.prev_correct = False
        self.quest_item_idx = -1

    def done(self) -> bool:
        return len(self.not_answered) == 0

    def next_question(self) -> Question:
        assert not self.done()
        assert self.quest_item_idx == -1
        prev_prompt = self.quest_prompt
        prev_correct_answer = self.quest_correct_answer
        prev_extra_info = self.quest_extra_info

        self.quest_item_idx = random.choice(self.not_answered)
        var_num = self.user_vocab.engine.variants_num
        if len(self.items_idx) >= var_num:
            variants = random.sample(self.items_idx, var_num)
        else:
            variants = copy.copy(self.items_idx)
            total_words = len(self.user_vocab.state)
            while len(variants) < var_num:
                idx = random.randint(0, total_words - 1)
                if idx not in variants:
                    variants.append(idx)
        if self.quest_item_idx not in variants:
            variants[0] = self.quest_item_idx
        random.shuffle(variants)
        assert len(variants) == var_num
        self.quest_correct_option = variants.index(self.quest_item_idx)

        # Generate prompt and responses.
        question_dir = random.randint(0, 1)  # foreign->native or other way around.
        items = self.user_vocab.vocab.items
        if question_dir == 0:
            prompt = items[self.quest_item_idx].foreign
            options = [items[i].native for i in variants]
            self.quest_correct_answer = items[self.quest_item_idx].native
        else:
            prompt = items[self.quest_item_idx].native
            options = [items[i].foreign for i in variants]
            self.quest_correct_answer = items[self.quest_item_idx].foreign
        self.quest_prompt = prompt
        self.quest_extra_info = self.user_vocab.vocab.items[self.quest_item_idx].extra_info
        return Question(prompt=prompt,
                        options=options,
                        prev_correct=self.prev_correct,
                        prev_prompt=prev_prompt,
                        prev_correct_answer=prev_correct_answer,
                        prev_extra_info=prev_extra_info)

    def finalize(self) -> SessionSummary:
        """Save session results and generate summary."""
        assert self.done()
        assert len(self.items_idx) > 0
        correct_count = 0
        incorrect_count = 0
        box_move_summary = dict()  # type: dict[str, list[str]]
        cur_time = get_cur_time()
        vocab = self.user_vocab.vocab.items
        for idx in self.items_idx:
            state = self.user_vocab.state[idx]
            box_before = state.box
            if idx in self.wrong_guesses:
                incorrect_count += 1
                state.box = max(box_before - 1, 0)
            else:
                correct_count += 1
                state.box = min(box_before + 1, NUM_BOXES - 1)
            state.next_show_time_sec = cur_time + WAIT_TIMES_HR[state.box] * 3600
            move_type = f"{box_before}->{state.box}"
            if state.box > box_before:
                move_type = "⬆️" + move_type
            elif state.box < box_before:
                move_type = "⬇️" + move_type
            word = vocab[idx].foreign
            if move_type in box_move_summary:
                box_move_summary[move_type].append(word)
            else:
                box_move_summary[move_type] = [word]
        self.user_vocab.save()
        return SessionSummary(
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            box_move_summary=box_move_summary
        )


@dataclass
class UserVocab:
    """State of user's learning of particular vocabulary."""
    engine: 'VocabBotEngine'
    user_id: int
    vocab: Vocab
    state: list[ItemLearnState]
    session: tp.Optional[LearningSession] = None
    wait_time_sec = 0  # Set in case user needs to wait.

    def compute_summary(self):
        box_cnt = [0 for _ in range(NUM_BOXES)]
        for item in self.state:
            box_cnt[item.box] += 1
        progress = sum(i * box_cnt[i] for i in range(NUM_BOXES))
        total = len(self.state) * (NUM_BOXES - 1)
        summary = "/".join(map(str, box_cnt))
        percent = (100 * progress) // total
        summary += f" - {percent}%"
        if progress == total:
            summary += "🏆"
        return summary

    def fully_learned(self):
        last_box = NUM_BOXES - 1
        return all(s.box >= last_box for s in self.state)

    def start_session(self):
        # Select words that are ready for review. Prefer higher boxes.
        cur_time = get_cur_time()
        ready_idx_by_box = [[] for _ in range(NUM_BOXES)]
        ready_cnt = 0
        for i, state in enumerate(self.state):
            if state.next_show_time_sec <= cur_time:
                ready_idx_by_box[state.box].append(i)
                ready_cnt += 1
        idx = []
        ss = self.engine.session_size
        for i in range(NUM_BOXES - 1, -1, -1):
            if len(idx) == ss:
                break
            assert len(idx) < ss
            if len(idx) + len(ready_idx_by_box[i]) <= ss:
                idx += ready_idx_by_box[i]
            else:
                cnt = ss - len(idx)
                idx += random.sample(ready_idx_by_box[i], cnt)
        assert len(idx) == min(ss, ready_cnt)

        # Don't show synonyms in the same session
        words = set()
        idx2 = []
        for i in idx:
            item = self.vocab.items[i]
            if not (item.foreign in words or item.native in words):
                idx2.append(i)
                words.add(item.foreign)
                words.add(item.native)

        if len(idx2) > 0:
            self.session = LearningSession(self, idx2)
        else:
            self.wait_time_sec = min(s.next_show_time_sec for s in self.state) - cur_time
            self.session = None

    def save(self):
        """Saves learning state to storage."""
        self.engine.storage.save_vocab(
            self.user_id, self.vocab.id, self.compute_summary(), self.state)


class VocabBotEngine:
    def __init__(self,
                 db_path: Path = Path('./data/vocab_bot_db.sqlite'),
                 vocabs_dir: Path = Path('./data/vocab_bot_vocabs'),
                 session_size: int = 20,
                 variants_num: int = 5):
        # Number of words in one learning session.
        self.session_size = session_size
        # Number of answer variants for a question.
        self.variants_num = variants_num
        assert self.session_size >= self.variants_num

        self.storage = VocabBotStorage(db_path)

        # Load all vocabs.
        self.vocabs = dict()  # type: dict[str, Vocab]
        assert vocabs_dir.exists()
        for vocab_file in vocabs_dir.iterdir():
            file_name = vocab_file.name
            if not vocab_file.is_file() or not file_name.endswith(".csv"):
                continue
            vocab_id = file_name[:-4]
            vocab = Vocab.load_from_csv(vocab_id, vocab_file)
            assert len(vocab.items) >= self.variants_num
            self.vocabs[vocab_id] = vocab
        assert len(self.vocabs) > 0, "No vocabs found in %s" % vocabs_dir
        print("Loaded %d vocabs." % len(self.vocabs))

        # Sessions.
        self.active_vocabs = dict()  # type: dict[int, UserVocab]

    def get_user_vocab(self, user_id: int, vocab_id: str) -> tp.Optional[UserVocab]:
        """Loads vocab. Creates it if it doesn't exist."""
        state = self.storage.load_vocab_state(user_id, vocab_id)
        if state is None:
            assert vocab_id in self.vocabs
            vocab = self.vocabs[vocab_id]
            num_items = len(vocab.items)
            state = [ItemLearnState.new() for _ in range(num_items)]
            result = UserVocab(engine=self, user_id=user_id, vocab=vocab, state=state)
            result.save()
            return result
        else:
            assert len(state) == len(self.vocabs[vocab_id].items)
            return UserVocab(
                engine=self, user_id=user_id, vocab=self.vocabs[vocab_id], state=state)

    def respond_to_button(self, user_id: int, callback_data: str) -> tp.Optional[UserScreen]:
        args = callback_data.split(":")
        if len(args) != 2:
            logging.warning("Bad callback:", callback_data)
            return None

        # Answer to question within session.
        if args[0] == "ans":
            option = int(args[1])
            if user_id not in self.active_vocabs:
                logging.warning("User %d doesn't have active vocab.", user_id)
                return None
            user_vocab = self.active_vocabs[user_id]
            if user_vocab.session is None:
                logging.warning("User %d doesn't have active session.", user_id)
                return None
            user_vocab.session.answer_question(option)
            if user_vocab.session.done():
                response = user_vocab.session.finalize()
                del self.active_vocabs[user_id]
                return response
            else:
                return user_vocab.session.next_question()

        user = self.storage.get_user(user_id)
        if user is None:
            logging.warning("User not found: %d", user_id)
            logging.warning("User not found: %d", user_id)
            return None

        # Switching vocab.
        if args[0] == "select_vocab":
            vocab_id = args[1]
            if vocab_id not in self.vocabs:
                return None
            if not self.vocabs[vocab_id].is_visible(user_id):
                return None
            user.active_vocab = vocab_id
            self.storage.update_user(user)
            self.get_user_vocab(user_id, vocab_id)  # Creates vocab if it doesn't exist.
            return self.create_home_screen(user)

        elif args[0] == "goto":
            if args[1] == "home":
                return self.create_home_screen(user)
            elif args[1] == "select_vocab":
                return self.create_vocab_select_screen(user)
            elif args[1] == "help":
                return self.create_help_screen()
            elif args[1] == "session":
                if user.active_vocab is None:
                    return None
                user_vocab = self.get_user_vocab(user_id, user.active_vocab)
                self.active_vocabs[user_id] = user_vocab
                user_vocab.start_session()
                if user_vocab.session is not None:
                    return user_vocab.session.next_question()
                else:
                    if user_vocab.fully_learned():
                        return MessageBox(msg="You learned all words in this vocab! 🎉🎉🎉",
                                          ok_cb="goto:home")
                    else:
                        wait = secs_to_interval(user_vocab.wait_time_sec)
                        return MessageBox(
                            msg=f"You need to wait {wait} before you can review this vocab.",
                            ok_cb="goto:home")

        logging.warning("Unrecognized callback: %s", callback_data)
        return None

    def respond_default(self, user_id: int, name: str) -> UserScreen:
        """Respond to /start and arbitrary text message."""
        user = self.storage.get_user(user_id)
        if user is None:
            logging.info("Inserting user %d (%s) into database", user_id, name)
            user = self.storage.insert_user(user_id, name)
        if user.active_vocab is None:
            return self.create_vocab_select_screen(user)
        else:
            return self.create_home_screen(user)

    def create_vocab_select_screen(self, user: UserStorageInfo) -> VocabSelect:
        """Returns list of all vocabs. Current first, then all attempted, then the rest."""
        all_vocab_ids = set(v_id for v_id, v in self.vocabs.items() if v.is_visible(user.id))
        summaries_from_storage = self.storage.get_vocab_summaries_for_user(user.id)
        vocab_ids = []
        summaries = []
        if user.active_vocab is not None and user.active_vocab in all_vocab_ids:
            vocab_ids.append(user.active_vocab)
            summaries.append(summaries_from_storage[user.active_vocab] + " ✔️")
            all_vocab_ids.remove(user.active_vocab)
            del summaries_from_storage[user.active_vocab]
        names1 = list(summaries_from_storage.keys())
        names1.sort()
        for name in names1:
            if name not in all_vocab_ids:
                continue
            vocab_ids.append(name)
            summaries.append(summaries_from_storage[name])
            all_vocab_ids.remove(name)
        names2 = list(all_vocab_ids)
        names2.sort()
        for name in names2:
            vocab_ids.append(name)
            summaries.append("Not started")
        return VocabSelect(vocab_ids=vocab_ids, vocab_summaries=summaries)

    def create_home_screen(self, user: UserStorageInfo) -> HomeScreen:
        assert user.active_vocab is not None
        summary = self.storage.get_vocab_summary(user.id, user.active_vocab)
        return HomeScreen(user_name=user.name, vocab_id=user.active_vocab, progress_summary=summary)

    def create_help_screen(self):
        return HelpScreen(session_size=self.session_size)
