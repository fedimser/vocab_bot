import os
import typing as tp

import pytest

from .storage import VocabBotStorage, ItemLearnState


@pytest.fixture(scope="session")
def storage(tmp_path_factory: pytest.TempPathFactory
            ) -> tp.Generator[VocabBotStorage, None, None]:
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = tmp_dir / "tmp_db.sqlite"
    storage = VocabBotStorage(db_path)
    try:
        yield storage
    finally:
        storage.close()
        os.remove(db_path)


def test_get_summary(storage: VocabBotStorage):
    storage.save_vocab(5, "vocab10", "summary10", [])
    assert storage.get_vocab_summary(5, "vocab10") == "summary10"


def test_get_summaries(storage: VocabBotStorage):
    storage.save_vocab(1, "vocab1", "summary1",
                       [ItemLearnState.from_arr([1, 2])])
    storage.save_vocab(1, "vocab2", "summary2",
                       [ItemLearnState.from_arr([1, 2])])
    summaries1 = storage.get_vocab_summaries_for_user(1)
    assert summaries1 == {"vocab1": "summary1", "vocab2": "summary2"}
    summaries2 = storage.get_vocab_summaries_for_user(2)
    assert len(summaries2) == 0


def test_update_state(storage: VocabBotStorage):
    assert storage.load_vocab_state(3, "vocab1") is None
    state1 = [ItemLearnState.from_arr([1, 2]), ItemLearnState.from_arr([3, 4])]
    storage.save_vocab(3, "vocab1", "summary1", state1)
    assert storage.load_vocab_state(3, "vocab1") == state1
    state2 = [ItemLearnState.from_arr([1, 6]), ItemLearnState.from_arr([7, 8])]
    storage.save_vocab(3, "vocab1", "summary2", state2)
    assert storage.get_vocab_summaries_for_user(3) == {"vocab1": "summary2"}
    assert storage.load_vocab_state(3, "vocab1") == state2


def test_insert_user(storage: VocabBotStorage):
    assert storage.get_user(4) is None
    storage.insert_user(4, "Bob")
    user = storage.get_user(4)
    assert user.id == 4
    assert user.name == "Bob"
    assert user.active_vocab is None


def test_user_set_active_vocab(storage: VocabBotStorage):
    storage.insert_user(5, "Bob")
    user1 = storage.get_user(5)
    assert user1.active_vocab is None
    user1.active_vocab = "vocab1"
    storage.update_user(user1)
    assert storage.get_user(5).active_vocab == "vocab1"
    user1.active_vocab = "vocab2"
    storage.update_user(user1)
    assert storage.get_user(5).active_vocab == "vocab2"
    user1.active_vocab = None
    storage.update_user(user1)
    assert storage.get_user(5).active_vocab is None
