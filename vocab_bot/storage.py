import json
import logging
import os
import sqlite3
import typing as tp
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .utils import get_cur_time


@dataclass
class UserStorageInfo:
    id: int
    name: str
    first_seen: datetime
    active_vocab: tp.Optional[str]


@dataclass
class ItemLearnState:
    box: int
    next_show_time_sec: int

    def to_arr(self) -> list[tp.Any]:
        return [self.box, self.next_show_time_sec]

    @staticmethod
    def from_arr(arr: list[tp.Any]):
        assert len(arr) == 2
        return ItemLearnState(box=arr[0], next_show_time_sec=arr[1])

    @staticmethod
    def new():
        return ItemLearnState(box=0, next_show_time_sec=0)


class VocabBotStorage:
    def __init__(self, db_path: Path):
        if not os.path.exists(db_path):
            logging.warning("DB not found, creating empty DB")
            if not os.path.exists(db_path.parent):
                os.makedirs(db_path.parent)
            self.conn = sqlite3.connect(db_path)
            with open('db_schema.sdl') as f:
                sdl = f.read().split(";")
                for statement in sdl:
                    self.conn.execute(statement)
            self.conn.commit()
        else:
            self.conn = sqlite3.connect(db_path)
            # Check that DB is valid.
            query = "SELECT COUNT(*) FROM UserVocabs"
            result = list(self.conn.execute(query))
            cnt = result[0][0]
            logging.info("Database contains %d user-vocab entires" % cnt)

    def close(self):
        self.conn.close()

    def get_vocab_summary(self, user_id: int, vocab_id: str) -> tp.Optional[str]:
        query = "SELECT summary FROM UserVocabs WHERE user_id = ? AND vocab_id = ?"
        params = (user_id, vocab_id)
        rows = list(self.conn.execute(query, params))
        if len(rows) == 0:
            return None
        else:
            return rows[0][0]

    def get_vocab_summaries_for_user(self, user_id: int) -> dict[str, str]:
        query = "SELECT vocab_id, summary FROM UserVocabs WHERE user_id = ?"
        return {row[0]: row[1] for row in self.conn.execute(query, (user_id,))}

    def load_vocab_state(
            self, user_id: int, vocab_id: str) -> tp.Optional[list[ItemLearnState]]:
        query = "SELECT state FROM UserVocabs WHERE user_id = ? AND vocab_id=?"
        rows = list(self.conn.execute(query, (user_id, vocab_id)))
        if len(rows) == 0:
            return None
        assert len(rows) == 1
        state = json.loads(rows[0][0])
        assert type(state) is list
        assert len(state) > 0
        return [ItemLearnState.from_arr(x) for x in state]

    def save_vocab(
            self,
            user_id: int,
            vocab_id: str,
            summary: str,
            state: list[ItemLearnState]) -> None:
        query = """
            INSERT OR REPLACE INTO UserVocabs(user_id,vocab_id,summary,state)
            VALUES (?,?,?,?)
        """
        state_str = json.dumps([ws.to_arr() for ws in state])
        params = (user_id, vocab_id, summary, state_str)
        self.conn.execute(query, params)
        self.conn.commit()

    def insert_user(self, user_id: int, name: str) -> UserStorageInfo:
        query = """
            INSERT INTO Users(user_id,name,first_seen_sec)
            VALUES (?,?,?)
        """
        cur_time = get_cur_time()
        params = (user_id, name, get_cur_time())
        self.conn.execute(query, params)
        self.conn.commit()
        return UserStorageInfo(
            id=user_id,
            name=name,
            first_seen=datetime.fromtimestamp(cur_time),
            active_vocab=None)

    def get_user(self, user_id) -> tp.Optional[UserStorageInfo]:
        query = """
            SELECT name,first_seen_sec,active_vocab
            FROM Users WHERE user_id=?
        """
        rows = list(self.conn.execute(query, (user_id,)))
        if len(rows) == 0:
            return None
        assert len(rows) == 1
        row = rows[0]
        return UserStorageInfo(
            id=user_id,
            name=row[0],
            first_seen=datetime.fromtimestamp(row[1]),
            active_vocab=row[2])

    def update_user(self, user: UserStorageInfo) -> None:
        query = """
            UPDATE Users
            SET active_vocab=?
            WHERE user_id=?
        """
        params = (user.active_vocab, user.id)
        self.conn.execute(query, params)
        self.conn.commit()
