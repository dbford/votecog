import asyncio
from typing import Union, Dict

import discord
import redbot.core
from discord import TextChannel
from redbot.core import Config, checks
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.data_manager import cog_data_path

from .api import VoteAPI, Interrupted
from .config import *
from .db import VoteDB
from .issues import Issue
from .util import LOG
from .votes import Vote
from .webhook import Webhook, LabelEvent


class VoteCog(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # save this for later
        self.bot: Red = bot

        # setup config
        self.config: Config = Config.get_conf(self, identifier=37298011)
        self.config.register_global(**GlobalConfig().to_dict())
        self.config.register_channel(**ChannelConfig().to_dict())

        # state machines
        self.vote_machine: Optional[VoteAPI] = None
        self.webhook: Optional[Webhook] = None
        self.vote_db: Optional[VoteDB] = None

        # reverse repo_name->channel lookup. used for webhook events
        self.repo_lookup: Dict[str, ChannelConfig] = {}

    def cog_unload(self):
        LOG.info("cog_unload")
        asyncio.create_task(self.clean_up())

    async def clean_up(self):
        LOG.info("clean_up")

        # dispose vote machine
        if self.vote_machine is not None:
            self.vote_machine.disposed = True
            self.vote_machine = None

        # dispose webhook
        if self.webhook is not None and self.webhook.running:
            await self.webhook.stop()
            self.webhook = None

        # clear repo_lookup
        self.repo_lookup.clear()

        # close vote db
        if self.vote_db is not None:
            self.vote_db = None

    async def init(self):
        # clean up any existing resources
        LOG.info("init")
        await self.clean_up()

        # load repo_lookup
        for conf in (await self.config.all_channels()).values():
            conf = ChannelConfig().from_dict(conf)
            if conf.github.repo_name is not None and len(conf.github.repo_name) > 0:
                self.repo_lookup[conf.github.repo_name] = conf

        # load conf
        conf = await self._global_config()

        # new vote machine
        if conf.github.api_token is not None and len(conf.github.api_token) > 0:
            self.vote_machine = VoteAPI(conf)

        # new webhook
        if bool(conf.github.webhook.on) and conf.github.webhook.on != 'False':
            self.webhook = Webhook(conf.github.webhook, self.on_pr_labeled)
            self.webhook.config = conf.github.webhook
            await self.webhook.start()

        # vote db
        self.vote_db = VoteDB(cog_data_path(self))
        await self.vote_db.init()

        # resume running votes
        for vote in await self.vote_db.list():
            LOG.info(f"Resuming vote on PR #{vote._issue_id} in {vote.config.github.repo_name}")
            asyncio.create_task(self._resume_vote(vote))

    @commands.group()
    async def vote(self, ctx: Context):
        """Commands for voting on Github PullRequests"""
        pass

    @vote.command()
    @checks.is_owner()
    async def reset(self, ctx: Context):
        """Reset the vote cog - must be done after updating critical config"""
        with ctx.typing():
            await self.init()
            await ctx.message.add_reaction("☑")

    @vote.command(name="start")
    async def start_vote(self, ctx: Context, pull_request_id: int):
        """Initiate a vote on a pull request"""

        # load config
        conf = await self._channel_config(ctx.channel)

        # check vote is setup
        if conf.github.repo_name is None or len(conf.github.repo_name) == 0:
            await asyncio.gather(
                ctx.send("`Set 'repo_name' before starting vote on pull request`"),
                ctx.message.add_reaction("❌")
            )
            return

        # check vote machine is setup
        if self.vote_machine is None:
            await asyncio.gather(
                ctx.send("`Set 'api_token' before starting vote on pull request`"),
                ctx.message.add_reaction("❌")
            )
            return

        # lookup the issue
        issue: Issue = await self.vote_machine.get_issue(conf.github.repo_name, pull_request_id)
        if issue is None:
            await asyncio.gather(
                ctx.send(f"`PR #{pull_request_id} not found in {conf.github.repo_name}`"),
                ctx.message.add_reaction("❌")
            )
            return

        # execute vote
        await self._run_vote(issue, conf)

    async def on_pr_labeled(self, event: LabelEvent):
        LOG.debug(
            f"PR #{event.pr_id} in {event.repo_name} {'added' if event.label_added else 'removed'} label {event.label_name}")

        # start by looking up the channel config
        conf = self.repo_lookup[event.repo_name]
        if conf is None:
            LOG.warn(
                f"Encountered label added webhook event for repo '{event.repo_name}', but no channel connected to that name exists!")
            return

        # check if this a vote start label
        if not event.label_added or event.label_name != conf.github.labels.needs_vote:
            return

        # Check if api token is setup
        if self.vote_machine is None:
            LOG.warn(
                f"Encountered needs_vote label in webhook event for repo '{event.repo_name}' PR #{event.pr_id}, but not VoteAPI instance exists (is the api_token set?)")
            return

        # lookup the issue
        issue: Issue = await self.vote_machine.get_issue(conf.github.repo_name, event.pr_id)
        if issue is None:
            LOG.error(
                f"Encountered needs_vote label in webhook event for repo '{event.repo_name} PR #{event.pr_id}, but failed to lookup the issue!")
            return

        # execute vote
        await self._run_vote(issue, conf)

    async def _run_vote(self, issue: Issue, conf: ChannelConfig):
        # new vote data
        vote = self.vote_machine.new_vote(issue, conf)

        # execute vote
        try:
            await self.vote_machine.start_vote(self.bot, vote)
            await self.vote_db.persist(vote)
            await self.vote_machine.resume_vote(vote)
        except Interrupted:
            return

        # delete old vote data
        await self.vote_db.remove(vote)

    async def _resume_vote(self, vote_data: Vote):
        # reload vote data
        vote = await self.vote_machine.load_vote(vote_data, self.bot)
        if vote is None:
            LOG.warning(
                f"Unable to resume vote on PR #{vote_data._issue_id} in {vote_data.config.github.repo_name}. It may have been cancelled")
            await self.vote_db.remove(vote_data)
            return

        # resume vote execution
        try:
            await self.vote_machine.resume_vote(vote)
        except Interrupted:
            return

        # delete old vote data
        await self.vote_db.remove(vote)

    @vote.command(name="list")
    async def list_votes(self, ctx: Context):
        """List any running votes (votes persisted in db) """

        with ctx.typing():
            votes: [Vote] = await self.vote_db.list()

            lines = [
                f"[PR #{vote._issue_id} in {vote.config.github.repo_name}](https://github.com/{vote.config.github.repo_name}/pull/{vote._issue_id}) - open for {vote.remaining_seconds()} seconds"
                for vote in votes
            ]

            text = "\n".join(lines) if len(lines) > 0 else "no votes"
            embed = discord.Embed()
            embed.add_field(name="--Running Votes--", value=text)
            await ctx.send(embed=embed)

    @vote.command(name="clear")
    @checks.is_owner()
    async def clear_votes(self, ctx: Context):
        """Clear persisted votes (debugging/troubleshooting)"""
        await self.vote_db.clear()
        await ctx.message.add_reaction("☑")

    @vote.command(name="set")
    @checks.is_owner()
    async def set_global_conf(self, ctx: Context, key: Optional[str], value: Optional[str]):
        """Set global config"""

        # if key/value not passed, print out available keys
        if key is None or value is None:
            await self.get_global_conf(ctx)
            return

        # set conf
        delete_msg = "api_token" in key or "secret" in key
        await self._set_conf(ctx, key, value, self.config, GlobalConfig(), delete_msg=delete_msg)

    @vote.command(name="get")
    @checks.is_owner()
    async def get_global_conf(self, ctx: Context):
        """Print global config"""
        # load conf
        conf = await self._global_config()

        # hide api token
        api_token = conf.github.api_token
        if api_token is not None and len(api_token) > 0:
            conf.github.api_token = f"*************{api_token[-5:]}"

        # hide webhook secret
        secret = conf.github.webhook.secret
        if secret is not None and len(secret) > 0:
            conf.github.webhook.secret = "*********"

        # print conf
        await self._get_conf(ctx, conf)

    @vote.group(name="channel", aliases=["c"])
    async def channel(self, ctx: Context):
        """Per-channel commands and config"""
        pass

    @channel.command(name="set")
    async def set_channel_conf(self, ctx: Context, key: Optional[str], value: Optional[str]):
        """Set per-channel config"""
        # load config
        raw_config = self.config.channel(ctx.channel)

        # if key/value not passed, print out available keys
        if key is None or value is None:
            await self.get_channel_conf(ctx)
            return

        # keep repo_lookup in sync
        old_repo_name = await raw_config.github.repo_name()

        # set conf
        await self._set_conf(ctx, key, value, raw_config, ChannelConfig())

        # keep repo_lookup in sync
        conf = await raw_config.all(acquire_lock=False)
        conf = ChannelConfig().from_dict(conf)
        if conf.github.repo_name is not None and len(conf.github.repo_name) > 0:
            self.repo_lookup[conf.github.repo_name] = conf
        if old_repo_name != conf.github.repo_name:
            self.repo_lookup.pop(old_repo_name, None)

    @channel.command(name="get")
    async def get_channel_conf(self, ctx: Context):
        """Print per-channel config"""

        # load config
        conf = await self._channel_config(ctx.channel)

        # print conf
        await self._get_conf(ctx, conf)

    async def _global_config(self) -> GlobalConfig:
        conf = await self.config.all(acquire_lock=False)
        conf = GlobalConfig().from_dict(conf)

        return conf

    async def _channel_config(self, channel: TextChannel) -> ChannelConfig:
        # load config
        raw_conf = self.config.channel(channel)
        conf = await raw_conf.all(acquire_lock=False)
        conf = ChannelConfig().from_dict(conf)

        # set channel_id, if it hasn't been set already
        if conf.discord.channel_id is None:
            conf.discord.channel_id = channel.id
            await raw_conf.discord.channel_id.set(channel.id)

        return conf

    async def _get_conf(self, ctx: Context, config: BaseConfig):
        # serialize to string
        lines = []
        for new_obj, key, val in config.walk():
            if new_obj is not None:
                if len(lines) != 0:
                    lines.append("")
                lines.append(f"#{new_obj.__doc__}")

            if val is None or (isinstance(val, str) and len(val) == 0):
                lines.append(f"{key}=")
            else:
                lines.append(f"{key}={val}")

        config_text = "\n".join(lines)
        await ctx.send(f"```ini\n{config_text}\n```")

    async def _set_conf(self, ctx: Context, key: str, value: str, config: Union[Config, redbot.core.config.Group],
                        valid_keys: BaseConfig, delete_msg: bool = False):
        # check if the key being set is known
        valid_keys = {key for _, key, _ in valid_keys.walk()}
        if key not in valid_keys:
            await asyncio.gather(
                ctx.message.add_reaction("❌"),
                ctx.send(f"`Unknown key: '{key}'`")
            )
            return

        # check if key is protected
        if is_protected_key(key):
            await asyncio.gather(
                ctx.message.add_reaction("❌"),
                ctx.send(f"`Not set here: '{key}'`")
            )
            return

        # prepare update actions
        actions = [
            config.set_raw(*key.split('.'), value=value),
        ]
        if delete_msg:
            actions.append(ctx.message.delete())
            actions.append(ctx.send(f"`Set key '{key}'`"))
        else:
            actions.append(ctx.message.add_reaction("☑"))

        # execute
        await asyncio.gather(*actions)
