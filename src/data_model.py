import asyncio
import time
from datetime import timedelta
from typing import Set


## This file contains "interface" classes that
## define the data model of the program.


class Issue:
    """optionally, url of issue"""
    url: str
    """optionally, unique id of isse"""
    id: str
    """title line of issue"""
    title: str
    """summary or description of issue"""
    description: str
    """author of issue"""
    author: str
    """set of tags assigned to usse"""
    tags: Set[str]
    """true if issue exists"""
    exists: bool = True

    async def remove_tag(self, tag: str):
        """Remove 'tag' from the set of tags attached to this issue"""
        self.tags.remove(tag)
        pass

    async def add_tag(self, tag: str):
        """Add 'tag' to the set of tags attached to this issue"""
        self.tags.add(tag)
        pass

    async def refresh(self):
        """
        Reload all state (title/descr/tags,exists) of this object.
        This may be required if this object was loaded from a remote source (i.e., http)
        """
        pass


class Vote:
    """Issue being voted on"""
    issue: Issue
    """epoch second start time of voting period"""
    period_start: int
    """epoc second end time of voting period"""
    period_end: int
    """number of aye votes"""
    positive_count: int = -1
    """number of nay votes"""
    negative_count: int = -1
    """true if vote was cancelled at some point"""
    cancelled: bool = False

    def __init__(self, issue: Issue, voting_period_seconds: int):
        self.issue = issue
        self.period_start = int(time.time())
        self.period_end = self.period_start + voting_period_seconds

    def remaining_seconds(self) -> int:
        seconds = self.period_end - int(time.time())
        if seconds < 0:
            seconds = 0

        return seconds

    def is_positive(self) -> bool:
        return self.positive_count > self.negative_count

    async def refresh(self):
        """Refreshes state (counts, cancelled) of this object"""
        pass


class PollingPlace:
    tag_needs_vote: str = "needs_vote"
    tag_voting: str = "vote_in_progress"
    tag_accept: str = "vote_pass"
    tag_reject: str = "vote_reject"

    async def start_vote(self, issue: Issue, voting_period_seconds: int) -> Vote:
        print("Starting vote on {}".format(issue))
        print("Vote will go on for {}".format(timedelta(seconds=float(voting_period_seconds))))

        vote = Vote(issue, voting_period_seconds)
        await vote.issue.remove_tag(self.tag_needs_vote)
        await vote.issue.add_tag(self.tag_voting)

        return vote

    async def resume_vote(self, vote: Vote):
        # wait for voting period to end
        pause_duration = vote.remaining_seconds()
        if pause_duration > 0:
            await asyncio.sleep(pause_duration)

        # poll results
        await vote.issue.refresh()
        await vote.refresh()

        # announce results
        if vote.issue.exists and not vote.cancelled:
            await self.end_vote(vote)

    async def end_vote(self, vote: Vote):
        print("Voting on {} has ended".format(vote.issue))
        print("{}: Aye({}) , Nay({})".format(
            "PASS" if vote.is_positive() else "REJECT",
            vote.positive_count, vote.negative_count
        ))

        await vote.issue.remove_tag(self.tag_voting)
        await vote.issue.add_tag(self.tag_accept if vote.is_positive() else self.tag_reject)

    async def execute_vote(self, issue: Issue, voting_period_seconds: int) -> Vote:
        vote = await self.start_vote(issue, voting_period_seconds)
        await self.resume_vote(vote)

        return vote
