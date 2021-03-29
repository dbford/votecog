from typing import Optional

import discord
from discord import Message


class PollId:
    def __init__(self, msg: Message):
        self.channel_id: int = msg.channel.id
        self.msg_id: int = msg.id


class Poll:

    def __init__(self, msg: Optional[Message], aye_emoji: str, nay_emoji: str):
        # field declarations
        self._msg: Optional[Message] = None
        self.id: Optional[PollId] = None
        self.aye_count: int = 0
        self.nay_count: int = 0
        self.aye_emoji: str = aye_emoji
        self.nay_emoji: str = nay_emoji
        self.exists: bool = True

        # init
        self.msg = msg

    async def update(self):
        msg = self.msg
        if msg is None:
            return

        try:
            self.msg = await msg.channel.fetch_message(msg.id)
        except discord.errors.NotFound:
            self.msg = None

    def is_vote_accepted(self):
        return self.aye_count > self.nay_count

    @property
    def msg(self) -> Optional[Message]:
        return self._msg

    @msg.setter
    def msg(self, msg: Optional[Message]):
        self._msg = msg

        if msg is None:
            self.exists = False
        else:
            self.id = PollId(msg)
            for reaction in msg.reactions:
                if reaction.emoji == self.aye_emoji:
                    self.aye_count = reaction.count - 1
                elif reaction.emoji == self.nay_emoji:
                    self.nay_count = reaction.count - 1
