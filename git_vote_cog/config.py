from typing import Optional


class BaseConfig:
    def to_dict(self) -> dict:
        vals = dict()
        for k, v in self.__dict__.items():
            if isinstance(v, BaseConfig):
                vals[k] = v.to_dict()
            else:
                vals[k] = v

        return vals

    def from_dict(self, vals: dict):
        my_vals = self.__dict__
        for k, v in my_vals.items():
            other_val = vals.get(k)
            if other_val is None:
                continue

            if isinstance(v, BaseConfig) and isinstance(other_val, dict):
                v.from_dict(other_val)
            else:
                my_vals[k] = other_val

        return self

    def walk(self, prefix: str = "", sep: str = "."):
        new_obj_flag = True
        for k, v in self.__dict__.items():
            if isinstance(v, BaseConfig):
                next_prefix = f"{k}{sep}" if len(prefix) == 0 else f"{prefix}{k}{sep}"

                yield from v.walk(next_prefix, sep)
            else:
                yield new_obj_flag, f"{prefix}{k}", v
                new_obj_flag = False


class Labels(BaseConfig):
    def __init__(self):
        self.needs_vote: str = "needs_vote"
        self.vote_in_progress: str = "vote_in_progress"
        self.vote_accepted: str = "vote_accepted"
        self.vote_rejected: str = "vote_rejected"


class GithubConfig(BaseConfig):
    def __init__(self):
        self.api_token: str = ""
        self.repo_name: Optional[str] = None
        self.repo_id: Optional[str] = None
        self.labels: Labels = Labels()


class DiscordConfig(BaseConfig):
    def __init__(self):
        self.voting_period_seconds: int = 10
        self.aye_vote_emoji: str = "👍"
        self.nay_vote_emoji: str = "👎"
        self.vote_rejected_icon: str = "https://domains.byu.edu/help/lib/exe/fetch.php?cache=&media=red-x-mark-transparent-background.png"
        self.vote_accepted_icon: str = "https://rlv.zcache.com/green_check_mark_symbol_classic_round_sticker-rd595add23fee473ca44c12c0a1bdcd36_0ugmp_8byvr_704.jpg"
        self.vote_start_icon: str = "https://m.media-amazon.com/images/I/51q83-k4w7L._AC_SY355_.jpg"
        self.channel_id: Optional[int] = None


class VoteConfig(BaseConfig):
    def __init__(self):
        self.discord: DiscordConfig = DiscordConfig()
        self.github: GithubConfig = GithubConfig()
        self.debug: bool = False
