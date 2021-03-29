import datetime
import time

from redbot.core.commands import Context

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

    def remaining_seconds(self) -> int:
        seconds = self.period_end - int(time.time())
        if seconds < 0:
            seconds = 0

        return seconds

    async def update(self):
        futures = []
        if self.issue is not None:
            futures.append(self.issue.update())
        if self.poll is not None:
            futures.append(self.poll.update())

        if len(futures) > 0:
            await asyncio.gather(*futures)

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


class VoteExecutor:

    def __init__(self, config: VoteConfig, lookup: IssueRepo, channel: TextChannel):
        self.config: VoteConfig = config
        self.lookup: IssueRepo = lookup
        self.channel: TextChannel = channel

    async def start_vote(self, issue: Issue) -> Vote:
        # put together a vote object, then open polling
        vote = Vote()
        vote.issue = issue
        vote.period_start = int(time.time())
        vote.period_end = vote.period_start + int(self.config.discord.voting_period_seconds)

        # config this vote will use
        emojis = self.config.discord
        labels = self.config.github.labels
        channel = self.channel

        # action to start polling
        async def create_poll():
            # format a poll message
            issue_desc = issue.description if len(issue.description) < 200 else issue.description[:197] + '...'
            vote_end = datetime.timedelta(seconds=int(self.config.discord.voting_period_seconds))
            vote_end = pretty_print_timedelta(vote_end)

            embed = discord.Embed()
            embed.set_thumbnail(url=self.config.discord.vote_start_icon)
            embed.title = f"PR #{issue.id}"
            embed.description = f"Vote to merge [**PR #{issue.id} - {issue.title}**]({issue.url}) by _{issue.author}_.\n```{issue_desc}```"
            embed.set_footer(
                text=f"Vote {emojis.aye_vote_emoji} to accept, {emojis.nay_vote_emoji} to reject. Voting ends after {vote_end}")

            # try pin call
            async def try_pin():
                try:
                    await poll_msg.pin(reason="Voting in progress")
                except discord.errors.Forbidden:
                    pass

            # create msg and add menu items
            poll_msg = await channel.send(embed=embed)
            await asyncio.gather(
                poll_msg.add_reaction(emojis.aye_vote_emoji),
                poll_msg.add_reaction(emojis.nay_vote_emoji),
                try_pin()
            )

            vote.poll = Poll(poll_msg, emojis.aye_vote_emoji, emojis.nay_vote_emoji)

        # collect actions needed to start vote
        actions = [
            create_poll(),
            vote.issue.remove_label(labels.needs_vote),
            vote.issue.add_label(labels.vote_in_progress)
        ]
        # remove previous vote results
        for other_label in [labels.vote_rejected, labels.vote_accepted]:
            if other_label in vote.issue.labels:
                actions.append(vote.issue.remove_label(other_label))

        # run all actions to start vote
        await asyncio.gather(*actions)

        return vote

    async def sleep_voting_period(self, vote: Vote):
        remaining_seconds = vote.remaining_seconds()
        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)

    async def end_vote(self, vote: Vote):
        # get latest poll/issue data
        await vote.update()

        # check whether vote was cancelled (or otherwise invalidated)
        labels = self.config.github.labels
        if not vote.exists:
            # optionally, cleanup PR labels
            if vote.issue.exists and labels.vote_in_progress in vote.issue.labels:
                await vote.issue.remove_label(labels.vote_in_progress)
            if vote.poll.exists:
                await vote.poll.msg.unpin(reason="Voting has been cancelled")

            if self.config.debug:
                embed = discord.Embed()
                embed.title = f"--Vote on PR {vote.issue.id} has been cancelled--"

                if not vote.issue.exists:
                    embed.add_field(name="PR", value=f"PR {vote.issue.id} has been deleted, merged, or closed")
                if not vote.poll.exists:
                    embed.add_field(name="Discord Message",
                                    value=f"Poll message with id {vote.poll.id.msg_id} has been deleted")
                await self.channel.send(embed=embed)

            return

        # vote exists, start closing it
        async def end_poll():
            # format end poll message
            accepted = vote.poll.is_vote_accepted()
            result = "accepted" if accepted else "rejected"

            embed = discord.Embed()
            embed.colour = 0x008000 if accepted else 0xFF0000
            embed.set_thumbnail(
                url=self.config.discord.vote_accepted_icon if accepted else self.config.discord.vote_rejected_icon)
            embed.title = "Vote Accepted" if accepted else f"Vote Rejected"
            embed.description = f"[PR #{vote.issue.id} - {vote.issue.title}]({vote.issue.url}) has been **{result}**.\n\n`{vote.poll.aye_emoji}x{vote.poll.aye_count} to {vote.poll.nay_emoji}x{vote.poll.nay_count}`"

            await vote.poll.msg.channel.send(embed=embed)

        async def try_unpin_msg():
            try:
                await vote.poll.msg.unpin(reason="Voting has ended")
            except discord.errors.Forbidden:
                pass

        result_label = labels.vote_accepted if vote.poll.is_vote_accepted() else labels.vote_rejected
        await asyncio.gather(
            end_poll(),
            vote.issue.remove_label(labels.vote_in_progress),
            vote.issue.add_label(result_label),
            try_unpin_msg()
        )


async def new_vote_executor(config: VoteConfig, ctx: Context) -> VoteExecutor:
    channel = ctx.channel
    lookup = await open_issue_repo(config.github.api_token, config.github.repo_name)

    return VoteExecutor(config, lookup, channel)
