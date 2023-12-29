# Vocab Bot
Telegram bot for learning foreign languages using 
[Spaced Repetition](https://en.wikipedia.org/wiki/Spaced_repetition).

The bot may be available at https://t.me/fedimser_vocab_bot (you need to be a Telegram user to use
it).

### Vocabs

The words to be learned come from vocabularies (vocabs). Vocabs are CSV files with 2 or 3 columns 
without headers, that should be placed in `data/vocabs`.

Format:
 * First column is a foreign word, it should be one word.
 * Second column is translation to native language (for the learner), it can be a word or 
a list of words.
 * Third column (if present) contains additional information (such as reading or transcription).

### How to run:

1. Install Python 3.9+ and git.
2. Clone this repository.
3. Add vocabs to `data/vocab_bot_vocabs`
4. Install requirements: `pip install -r requirements.txt requirements-dev.txt`
5. Run tests: `pytest ./vocab_bot`
6. Run: `VOCAB_BOT_TOKEN=<token> python3 ./run_bot.py`
