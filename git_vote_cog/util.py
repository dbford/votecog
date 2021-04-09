import asyncio
import datetime
import logging
from functools import wraps, partial

LOG = logging.getLogger("git-vote-cog")
LOG.setLevel(logging.INFO)
if len(LOG.handlers) == 0:
    LOG.addHandler(logging.StreamHandler())


def wrap_async(func):
    @wraps(func)
    async def run(*args, **kwargs):
        pf = partial(func, *args, **kwargs)
        return await asyncio.get_running_loop().run_in_executor(None, pf)

    return run


def pretty_print_timedelta(delta: datetime.timedelta) -> str:
    days = delta.days
    seconds = delta.seconds
    minutes = 0
    if seconds > 60:
        minutes = int(seconds / 60)
        seconds -= (minutes * 60)

    msg = ""
    if days > 0:
        msg = f"{days} days"
    if minutes > 0:
        if len(msg) > 0:
            msg += ", "
        msg += f"{minutes} min"
    if seconds > 0:
        if len(msg) > 0:
            msg += ", "
        msg += f"{seconds} sec"

    return msg
