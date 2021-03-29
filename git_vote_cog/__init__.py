from redbot.core.bot import Red

from .cog import VoteCog


async def setup(bot: Red):
    bot.add_cog(VoteCog())
