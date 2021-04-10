import json
import sqlite3
from pathlib import Path
from typing import Optional

from git_vote_cog.config import ChannelConfig
from git_vote_cog.polls import PollId
from git_vote_cog.util import wrap_async
from git_vote_cog.votes import Vote


class VoteDB:
    def __init__(self, dir: Path):
        self.dir = dir
        self.con: Optional[sqlite3.Connection] = None

    def _open(self) -> sqlite3.Connection:
        path = self.dir / 'votes.db'
        con = sqlite3.connect(str(path))

        return con

    @wrap_async
    def init(self):
        with self._open() as con:
            con.execute('''
                create table if not exists vote (
                    issue_id int,
                    channel_id int,
                    message_id int,
                    period_start int,
                    period_end int,
                    config_json text
                )
            ''')

    @wrap_async
    def persist(self, vote: Vote):
        config_json = json.dumps(vote.config.to_dict())

        with self._open() as con:
            con.execute(
                '''
                insert into vote (issue_id, channel_id, message_id, period_start, period_end, config_json)
                values (?, ?, ?, ?, ?, ?)
                ''',
                [
                    vote._issue_id,
                    vote._poll_id.channel_id,
                    vote._poll_id.msg_id,
                    vote.period_start, vote.period_end,
                    config_json
                ]
            )

    @wrap_async
    def remove(self, vote: Vote):
        with self._open() as con:
            con.execute("delete from vote where channel_id = ? and msg_id = ?",
                        [vote._poll_id.channel_id, vote._poll_id.msg_id])

    @wrap_async
    def clear(self):
        with self._open() as con:
            con.execute("delete from vote")

    @wrap_async
    def list(self) -> [Vote]:
        with self._open() as con:
            votes = []
            for row in con.execute(
                    "select issue_id, channel_id, message_id, period_start, period_end, config_json from vote"):
                (issue_id, channel_id, message_id, period_start, period_end, config_json) = row
                vote = Vote()
                vote._issue_id = issue_id
                vote._poll_id = PollId(channel_id, message_id)
                vote.period_start = period_start
                vote.period_end = period_end
                vote.config = ChannelConfig().from_dict(json.loads(config_json))

                votes.append(vote)

            return votes
