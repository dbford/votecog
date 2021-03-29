class VoteError(Exception):
    pass


class NoChannel(VoteError):
    pass


class NoRepo(VoteError):
    pass
