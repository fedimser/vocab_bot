import os
import random
import typing as tp

import pytest

from .engine import VocabBotEngine, Vocab
from .user_screens import UserScreen, HomeScreen, Question, SessionSummary, VocabSelect, MessageBox


@pytest.fixture(scope="session")
def engine(tmp_path_factory: pytest.TempPathFactory
           ) -> tp.Generator[VocabBotEngine, None, None]:
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = tmp_dir / "tmp_db.sqlite"
    vocabs_dir = tmp_dir / "vocabs"
    os.mkdir(vocabs_dir)
    vocab_file = vocabs_dir / "vocab1.csv"
    with open(vocab_file, "w") as f:
        for i in range(1000):
            f.write("word%d,trans%d,info%d\n" % (i, i, i))
    engine = VocabBotEngine(db_path=db_path, vocabs_dir=vocabs_dir, session_size=50, variants_num=3)
    try:
        yield engine
    finally:
        engine.storage.close()
        os.remove(db_path)


def test_loads_vocabs(engine: VocabBotEngine):
    assert len(engine.vocabs) == 1

    assert len(engine.vocabs["vocab1"].items) == 1000
    item = engine.vocabs["vocab1"].items[100]
    assert item.foreign == "word100"
    assert item.native == "trans100"
    assert item.extra_info == "info100"


class AutoLearner:
    def __init__(self, engine: VocabBotEngine):
        self.engine = engine
        self.user_id = random.randint(1, 1000000)
        self.user_name = "Bob"
        self.screen = None  # type: tp.Optional[UserScreen]
        self.done = False
        self.knowledge = dict()  # type: dict[str, set[str]]

        self.screen = tp.cast(VocabSelect, engine.respond_default(self.user_id, "Bob"))
        self.click(self.screen.get_buttons()[0][0])
        assert type(self.screen) is HomeScreen

    def memorize_pair(self, word1: str, word2: str):
        if word1 in self.knowledge:
            self.knowledge[word1].add(word2)
        else:
            self.knowledge[word1] = {word2}

    def memorize(self, prompt: str, correct_answer: str):
        self.memorize_pair(correct_answer, prompt)
        self.memorize_pair(prompt, correct_answer)

    def get_answer(self, prompt: str, variants: list[str]) -> str:
        if prompt not in self.knowledge:
            return variants[0]
        known_answers = self.knowledge[prompt]
        for variant in variants:
            if variant in known_answers:
                return variant
        return variants[0]  # Can happen with synonyms.

    def click(self, text: str):
        buttons = self.screen.get_buttons()
        for btn_text, cb in buttons:
            if btn_text == text:
                self.screen = self.engine.respond_to_button(self.user_id, cb)
                return
        assert False, "No button with text %s (buttons are: %s)" % (text, buttons)

    def do_session(self):
        self.click("Learn!")
        if type(self.screen) is MessageBox:
            assert "wait 24 hours" in self.screen.get_message_text()
            self.click("OK")
            self.done = True
            return
        while type(self.screen) is Question:
            question = tp.cast(Question, self.screen)
            guess = self.get_answer(question.prompt, question.options)
            self.click(guess)
            if type(self.screen) is Question:
                next_question = tp.cast(Question, self.screen)
                if not next_question.prev_correct:
                    guess = next_question.prev_correct_answer
            self.memorize(question.prompt, guess)
        assert type(self.screen) is SessionSummary
        self.click("OK")
        assert type(self.screen) is HomeScreen

    def learn_vocab(self, vocab_id):
        n = len(self.engine.vocabs[vocab_id].items)

        self.click("Select vocab")
        assert type(self.screen) is VocabSelect
        self.click(vocab_id)
        assert type(self.screen) is HomeScreen
        home = tp.cast(HomeScreen, self.screen)
        assert home.user_name == self.user_name
        assert home.vocab_id == vocab_id
        assert home.progress_summary == f"{n}/0/0/0/0 - 0%"

        self.knowledge.clear()
        while not self.done:
            self.do_session()
        assert type(self.screen) is HomeScreen
        home = tp.cast(HomeScreen, self.screen)
        assert home.progress_summary == f"0/{n}/0/0/0 - 25%"

    def validate(self, true_vocab: Vocab):
        for item in true_vocab.items:
            assert item.foreign in self.knowledge
            known_translations = self.knowledge[item.foreign]
            assert len(known_translations) <= 5  # If we got a lot of synonyms, something is wrong.
            assert item.native in known_translations


@pytest.mark.parametrize('vocab_id', ["vocab1"])
def test_learn_vocab(engine: VocabBotEngine, vocab_id: str):
    learner = AutoLearner(engine)
    learner.learn_vocab(vocab_id)
    learner.validate(engine.vocabs[vocab_id])
