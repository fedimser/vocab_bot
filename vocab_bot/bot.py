import asyncio
import logging
from os import getenv
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types.callback_query import CallbackQuery

from vocab_bot.engine import VocabBotEngine

logging.getLogger().setLevel(logging.WARNING)

engine = VocabBotEngine(
    db_path=Path('./data/vocab_bot_db.sqlite'),
    vocabs_dir=Path('./data/vocab_bot_vocabs'),
    variants_num=5,
    session_size=15,
)
dp = Dispatcher()


@dp.callback_query()
async def callback_handler(query: CallbackQuery) -> None:
    user_id = query.from_user.id
    screen = engine.respond_to_button(user_id, query.data)
    if screen is not None:
        await query.message.edit_text(screen.get_message_text(), reply_markup=screen.get_markup())
    else:
        await query.message.answer("Unknown error. Click /start to start again.")


@dp.message(Command('help'))
async def command_help(message: Message) -> None:
    await message.answer(engine.create_help_screen().get_message_text())


@dp.message()
async def default_message_handler(message: types.Message) -> None:
    user = message.from_user
    screen = engine.respond_default(user.id, user.username)
    if screen is not None:
        await message.answer(screen.get_message_text(), reply_markup=screen.get_markup())
    else:
        await message.answer("Unknown error. Click /start to start again.")


async def main() -> None:
    bot_token = getenv("VOCAB_BOT_TOKEN")
    assert bot_token is not None, "No env variable VOCAB_BOT_TOKEN"
    bot = Bot(bot_token, parse_mode=ParseMode.HTML)
    print("Vocab Bot started.")
    await dp.start_polling(bot)


def run_bot():
    """Bot entry point."""
    asyncio.run(main())
