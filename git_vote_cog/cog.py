from redbot.core import Config
from redbot.core import commands

from .votes import *


class VoteCog(commands.Cog):
    def __init__(self, *args, **kwargs):
        super(VoteCog, self).__init__(*args, **kwargs)

        self.config = Config.get_conf(self, identifier=37298010)
        self.config.register_channel(**VoteConfig().to_dict())

    @commands.group()
    async def vote(self, ctx: Context):
        pass

    @vote.group(name="conf")
    async def vote_conf(self, ctx: Context):
        pass

    @vote_conf.command(name="set")
    async def set_conf(self, ctx: Context, key: str, value: str):
        # check if the key being set is known
        valid_keys = {key for _, key, _ in VoteConfig().walk()}
        if key not in valid_keys:
            with ctx.typing():
                await ctx.message.add_reaction("❌")
                await ctx.send(f"`Unknown key '{key}'`")
            return

        # update config
        config = self.config.channel(ctx.channel)
        await config.set_raw(*key.split('.'), value=value)
        await ctx.message.add_reaction("☑")

    @vote_conf.command(name="get")
    async def get_conf(self, ctx: Context):
        # load channel conf
        config = VoteConfig().from_dict(await self.config.channel(ctx.channel).all(acquire_lock=False))

        # hide api_token
        api_token = config.github.api_token
        if api_token is not None and len(api_token) > 0:
            api_token = f"*************{api_token[-5:]}"
            config.github.api_token = api_token

        # serialize to string
        lines = []
        for new_obj_flag, key, val in config.walk():
            if len(lines) != 0 and new_obj_flag:
                lines.append("")

            if val is None or (isinstance(val, str) and len(val) == 0):
                lines.append(f"{key}=")
            else:
                lines.append(f"{key}={val}")

        config_text = "\n".join(lines)

        await ctx.send(f"```ini\n{config_text}\n```")

    @vote.command(name="start")
    async def start_vote(self, ctx: Context, pull_request_id: int):
        # load channel conf
        config = self.config.channel(ctx.channel)
        await config.discord.channel_id.set(ctx.channel.id)  # always set this

        with ctx.typing():
            # setup vote executor
            exec_config = VoteConfig().from_dict(await config.all(acquire_lock=False))
            executor = await new_vote_executor(exec_config, ctx)
            await config.github.repo_id.set(executor.lookup.repo_id)

            # check if issue exists
            issue: Issue
            try:
                issue = await executor.lookup.get_issue(pull_request_id)
            except github.UnknownObjectException:
                await ctx.message.add_reaction("❌")
                await ctx.send(f"`PR not found: {pull_request_id}`")

            # execute vote
            vote = await executor.start_vote(issue)

        await executor.sleep_voting_period(vote)
        with ctx.typing():
            await executor.end_vote(vote)
