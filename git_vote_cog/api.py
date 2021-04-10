import asyncio
import datetime
import time

import discord
import github
from discord import TextChannel, Message
from redbot.core.bot import Red

from git_vote_cog.config import *
from git_vote_cog.issues import Issue
from git_vote_cog.polls import Poll
from git_vote_cog.util import wrap_async, pretty_print_timedelta, LOG
from git_vote_cog.votes import Vote


class NoChannel(Exception):
    pass


class Interrupted(Exception):
    pass


class VoteAPI:
    def __init__(self, config: GlobalConfig):
        self.config = config
        self.client = github.Github(config.github.api_token)
        self.disposed = False

    @wrap_async
    def get_issue(self, repo_name: str, pr_id: int) -> Optional[Issue]:
        issue: Optional[Issue]
        try:
            repo = self.client.get_repo(repo_name, lazy=True)
            pr = repo.get_pull(pr_id)
            issue = Issue(pr)
        except github.UnknownObjectException:
            issue = None

        LOG.debug(f"Lookup {repo_name}/PR #{pr_id}: {issue}")
        return issue

    def new_vote(self, issue: Issue, config: ChannelConfig) -> Vote:
        """Create a new vote object"""

        # create a vote object
        vote = Vote()
        vote.issue = issue
        vote.poll = None
        vote.period_start = int(time.time())
        vote.period_end = vote.period_start + int(config.discord.voting_period_seconds)
        vote.config = config

        return vote

    async def load_vote(self, vote: Vote, bot: Red) -> Optional[Vote]:
        """Reload a vote object that was stored in the VoteDB"""

        # lookup issue data
        issue: Issue = await self.get_issue(vote.config.github.repo_name, vote._issue_id)
        if issue is None:
            return None

        # lookup poll data
        channel: TextChannel
        try:
            channel = await bot.fetch_channel(vote._poll_id.channel_id)
        except discord.errors.NotFound:
            return None

        msg: Message
        try:
            msg = await channel.fetch_message(vote._poll_id.msg_id)
        except discord.errors.NotFound:
            return None

        # build full msg object
        emojis = vote.config.discord.media
        vote.issue = issue
        vote.poll = Poll(msg, emojis.aye_vote_emoji, emojis.nay_vote_emoji)
        return vote

    async def start_vote(self, bot: Red, vote: Vote):
        # config this vote will use
        emojis = vote.config.discord.media
        labels = vote.config.github.labels

        channel = bot.get_channel(vote.config.discord.channel_id)
        if channel is None:
            LOG.error(f"Error looking up channel_id found in channel conf. channel_id={vote.config.discord.channel_id}")
            raise NoChannel()

        # action to start polling
        async def create_poll():
            embed = _display_vote_start(vote)

            # create msg with menu items
            poll_msg = await channel.send(embed=embed)
            await asyncio.gather(
                poll_msg.add_reaction(emojis.aye_vote_emoji),
                poll_msg.add_reaction(emojis.nay_vote_emoji),
                _try_pin(poll_msg, "Voting has started")
            )

            vote.poll = Poll(poll_msg, emojis.aye_vote_emoji,
                             emojis.nay_vote_emoji)  # legacy, passing emojis here but should just keep that in config

        # actions needed to start vote
        actions = [
            create_poll(),
            vote.issue.remove_label(labels.needs_vote),
            vote.issue.add_label(labels.vote_in_progress)
        ]

        # remove previous vote results
        for other_label in [labels.vote_rejected, labels.vote_accepted, labels.vote_in_progress]:
            if other_label in vote.issue.labels:
                actions.append(vote.issue.remove_label(other_label))

        # execute
        LOG.debug(f"Starting vote {vote}")
        try:
            await asyncio.gather(*actions)
            LOG.info(f"Started vote {vote}")
        except Exception as err:
            LOG.exception(f"Error starting vote {vote}")
            raise err

        return vote

    async def sleep_voting_period(self, vote: Vote):
        remaining_seconds = vote.remaining_seconds()
        if remaining_seconds > 0:
            LOG.debug(f"Waiting {remaining_seconds} seconds before polling {vote}")
            await asyncio.sleep(remaining_seconds)

    async def end_vote(self, vote: Vote):
        # get latest poll/issue data
        LOG.debug(f"Ending vote {vote}")
        try:
            await vote.update()
        except Exception as err:
            LOG.exception(f"Error updating vote data: {vote}")
            raise err

        # check if vote was cancelled or otherwise invalidated
        labels = vote.config.github.labels
        actions = []
        if not vote.exists:
            # vote cancelled - cleanup
            LOG.info(f"Vote {vote} has been cancelled. Cleaning up any labels/messages")
            actions = []
            if vote.issue.exists and labels.vote_in_progress in vote.issue.labels:
                actions.append(vote.issue.remove_label(labels.vote_in_progress))
            if vote.poll is not None and vote.poll.exists:
                actions.append(_try_unpin(vote.poll.msg, "Vote cancelled"))
        else:
            # vote exists, close
            LOG.info(f"Vote {vote} is closing. Doing cleanup and adding result labels")
            result_label = labels.vote_accepted if vote.poll.is_vote_accepted() else labels.vote_rejected
            actions.append(vote.poll.msg.channel.send(embed=_display_vote_end(vote)))
            actions.append(vote.issue.remove_label(labels.vote_in_progress))
            actions.append(vote.issue.add_label(result_label))
            actions.append(_try_unpin(vote.poll.msg, "Vote finished"))

        # execute
        if len(actions) > 0:
            try:
                await asyncio.gather(*actions)
            except Exception as err:
                LOG.exception(f"Error ending vote {vote}")
                raise err

    async def resume_vote(self, vote: Vote):
        # wait for vote to finish
        await self.sleep_voting_period(vote)
        if self.disposed:
            raise Interrupted()

        # end the vote
        await self.end_vote(vote)

    async def run_vote(self, bot: Red, vote: Vote):
        # start the vote
        await self.start_vote(bot, vote)
        if self.disposed:
            raise Interrupted()

        await self.resume_vote(vote)


# try pin call
async def _try_pin(msg: Message, reason: str):
    try:
        await msg.pin(reason=reason)
    except discord.errors.Forbidden:
        pass


async def _try_unpin(msg: Message, reason: str):
    try:
        await msg.unpin(reason=reason)
    except discord.errors.Forbidden:
        pass


def _display_vote_start(vote: Vote) -> discord.Embed:
    # config
    emojis = vote.config.discord.media
    config = vote.config
    issue = vote.issue

    # format a poll message
    issue_desc = issue.description if len(issue.description) < 200 else issue.description[:197] + '...'
    vote_end = datetime.timedelta(seconds=int(config.discord.voting_period_seconds))
    vote_end = pretty_print_timedelta(vote_end)

    embed = discord.Embed()
    embed.set_thumbnail(url=emojis.vote_start_icon)
    embed.title = f"PR #{issue.id}"
    embed.description = f"Vote to merge [**PR #{issue.id} - {issue.title}**]({issue.url}) by _{issue.author}_.\n```{issue_desc}```"
    embed.set_footer(
        text=f"Vote {emojis.aye_vote_emoji} to accept, {emojis.nay_vote_emoji} to reject. Voting ends after {vote_end}")

    return embed


def _display_vote_end(vote: Vote) -> discord.Embed:
    # format end poll message
    accepted = vote.poll.is_vote_accepted()
    result = "accepted" if accepted else "rejected"
    media = vote.config.discord.media

    embed = discord.Embed()
    embed.colour = 0x008000 if accepted else 0xFF0000
    embed.set_thumbnail(
        url=media.vote_accepted_icon if accepted else media.vote_rejected_icon)
    embed.title = "Vote Accepted" if accepted else f"Vote Rejected"
    embed.description = f"[PR #{vote.issue.id} - {vote.issue.title}]({vote.issue.url}) has been **{result}**.\n\n`{vote.poll.aye_emoji}x{vote.poll.aye_count} to {vote.poll.nay_emoji}x{vote.poll.nay_count}`"

    return embed
