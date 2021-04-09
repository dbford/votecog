from redbot.core.bot import Red

from .cog import VoteCog


async def setup(bot: Red):
    cog = VoteCog(bot)
    bot.add_cog(cog)

    await cog.init()
