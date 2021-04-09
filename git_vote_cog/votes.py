import time

from .config import *
from .issues import *
from .polls import *
from .util import *


class Vote:
    _issue: Optional[Issue] = None
    _issue_id: int = -1
    _poll: Optional[Poll] = None
    _poll_id: Optional[PollId] = None
    period_start: int = 0
    period_end: int = 0
    config: ChannelConfig

    def remaining_seconds(self) -> int:
        seconds = self.period_end - int(time.time())
        if seconds < 0:
            seconds = 0

        return seconds

    async def update(self):
        actions = []
        if self.issue is not None:
            actions.append(self.issue.update())
        if self.poll is not None:
            actions.append(self.poll.update())

        if len(actions) > 0:
            await asyncio.gather(*actions)

    @property
    def exists(self) -> bool:
        if self.issue is None or self.poll is None:
            return False
        return self.issue.exists and self.poll.exists

    @property
    def issue(self) -> Optional[Issue]:
        return self._issue

    @issue.setter
    def issue(self, issue: Optional[Issue]):
        self._issue = issue
        if issue is not None:
            self._issue_id = self._issue.id
        else:
            self._issue_id = -1

    @property
    def poll(self) -> Optional[Poll]:
        return self._poll

    @poll.setter
    def poll(self, poll: Optional[Poll]):
        self._poll = poll
        if poll is not None:
            self._poll_id = poll.id
        else:
            self._poll_id = None

    def __str__(self) -> str:
        return f"Vote({self.issue},{self.poll},{self.remaining_seconds()}sec)"
