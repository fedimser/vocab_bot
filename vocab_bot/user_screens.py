import typing as tp
from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class UserScreen(ABC):
    """Model for possible 'screens' shown to user.
    Screen is a Telegram message with buttons below it.
    Typically, screen is shown as response to button press on a screen and
    it replaces previous screen.
    """

    @abstractmethod
    def get_buttons(self) -> list[tuple[str, str]]:
        pass

    def max_buttons_per_row(self) -> int:
        return 1

    @abstractmethod
    def get_message_text(self) -> str:
        pass

    def get_markup(self) -> InlineKeyboardMarkup:
        buttons = self.get_buttons()
        mb = self.max_buttons_per_row()
        rows = [buttons[i:i + mb] for i in range(0, len(buttons), mb)]
        builder = InlineKeyboardBuilder()
        for row in rows:
            builder.row(*[InlineKeyboardButton(text=b[0], callback_data=b[1]) for b in row])
        return builder.as_markup()


@dataclass
class Question(UserScreen):
    prev_correct: tp.Optional[bool]  # Whether previous question was answered correctly.
    prev_prompt: str
    prev_correct_answer: str
    prev_extra_info: tp.Optional[str]
    prompt: str
    options: list[str]

    def get_buttons(self) -> list[tuple[str, str]]:
        # <option> - callback "ans:<option_number>".
        buttons = [(text, "ans:%d" % i) for i, text in enumerate(self.options)]
        buttons.append(("🤷 I don't know", "ans:-1"))
        return buttons

    def get_message_text(self) -> str:
        text = ""
        if self.prev_correct is not None:
            if self.prev_correct is True:
                text += "✅ Correct!\n"
            else:
                text += "❌ Wrong!\n"
            text += "%s - <b>%s</b>\n" % (self.prev_prompt, self.prev_correct_answer)
            if self.prev_extra_info is not None:
                text += self.prev_extra_info + "\n"
            text += "\n"
        text += self.prompt
        return text


@dataclass
class SessionSummary(UserScreen):
    correct_count: int
    incorrect_count: int
    box_move_summary: dict[str, list[str]]

    def get_buttons(self) -> list[tuple[str, str]]:
        return [("OK", "goto:home")]

    def get_message_text(self) -> str:
        total = self.correct_count + self.incorrect_count
        text = "Session done!\n"
        if self.correct_count > 0:
            text += "✅ %d/%d correct\n" % (self.correct_count, total)
        if self.incorrect_count > 0:
            text += "❌ %d/%d wrong\n" % (self.incorrect_count, total)
        text += "\n"
        text += "Session summary:\n"
        for box_change in sorted(list(self.box_move_summary.keys())):
            text += "\t%s: %s\n" % (box_change, ','.join(self.box_move_summary[box_change]))
        text += "\n"
        if self.incorrect_count == 0:
            text += "Great job!!! All correct!!! 🎉\n"
        elif self.correct_count > self.incorrect_count:
            text += "Good job!\n"
        return text


@dataclass
class HomeScreen(UserScreen):
    user_name: str
    vocab_id: str
    progress_summary: str

    def get_buttons(self) -> list[tuple[str, str]]:
        return [
            ("Learn!", "goto:session"),
            ("Select vocab", "goto:select_vocab"),
            ("Help", "goto:help")
        ]

    def get_message_text(self) -> str:
        text = "👋 Hello, %s!\n" % self.user_name
        text += "You are learning vocab %s.\n" % self.vocab_id
        text += "Your progress is: %s\n" % self.progress_summary
        return text


@dataclass
class VocabSelect(UserScreen):
    vocab_ids: list[str]
    vocab_summaries: list[str]

    def get_buttons(self) -> list[tuple[str, str]]:
        # <index> (1-indexed) - "select_vocab:<vocab_id>"
        return [(vocab_id, "select_vocab:%s" % vocab_id) for vocab_id in self.vocab_ids]

    def max_buttons_per_row(self) -> int:
        return 4

    def get_message_text(self) -> str:
        text = "📚 All available vocabularies:\n"
        for i, vocab_id in enumerate(self.vocab_ids):
            text += f"\t{i + 1}. {vocab_id} - {self.vocab_summaries[i]}\n"
        text += "\n"
        text += "Click button below to select vocabulary to learn.\n"
        return text


@dataclass
class MessageBox(UserScreen):
    msg: str
    ok_cb: str

    def get_buttons(self) -> list[tuple[str, str]]:
        return [("OK", self.ok_cb)]

    def get_message_text(self) -> str:
        return self.msg


HELP_TEXT = '\n'.join([
    "This is Vocab Bot by fedimser.",
    "It helps you learn vocabulary of foreign languages using Spaced Repetition technique.",
    "First, you select a vocabulary. Then you will learn and review words from this vocabulary in "
    "sessions. In each session, you will review %d words. You will be asked to match word with "
    "correct translation. If you answer correctly, the word moves to a box with higher number. "
    "If you make a mistake, it goes to box with smaller number.",
    "Your goal is to move all words from box 0 to box 4. Sometimes you will have to wait until "
    "you can review words.",
    "",
    "Tips:",
    "👉 If you don't know a word, click 'I don't know' and you will see the correct answer. "
    "Memorize it, you will be asked this word again in the same session.",
    "👉 You can switch to a different vocabulary, your progress on other vocabularies will be "
    "saved.",
    "👉 If you want to exit session early, or are stuck just type anything - but then you will "
    "lose all progress from that session."
])


@dataclass
class HelpScreen(UserScreen):
    session_size: int

    def get_buttons(self) -> list[tuple[str, str]]:
        return [("OK", "goto:home")]

    def get_message_text(self) -> str:
        return HELP_TEXT % (self.session_size,)
