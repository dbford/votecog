import datetime


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
