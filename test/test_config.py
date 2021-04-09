import unittest

from git_vote_cog.config import *


class TestConfig(unittest.TestCase):

    def test_dict(self):
        config = VoteConfig()

        def print_vals(vals: dict, indent: str):
            for k, v in vals.items():
                if isinstance(v, dict):
                    print(f"{indent}::{k}::")
                    print_vals(v, f"\t{indent}")
                else:
                    print(f"{indent}{k} = {v}")

        print("::Config::")
        print_vals(config.to_dict(), "\t")

    def test_from_dict(self):
        config = VoteConfig()
        config.discord.aye_vote_emoji = "-1"
        config.discord.nay_vote_emoji = "+1"
        config.github.repo_name = "222"

        vals = config.to_dict()
        check = VoteConfig()
        check.from_dict(vals)

        # print(jsonpickle.encode(config, unpicklable=False))
        # print(jsonpickle.encode(check, unpicklable=False))
        self.assertEqual(config.discord.media.aye_vote_emoji, check.discord.media.aye_vote_emoji)
        self.assertEqual(config.discord.media.nay_vote_emoji, check.discord.media.nay_vote_emoji)
        self.assertEqual(config.github.repo_name, check.github.repo_name)
        # self.assertEqual(jsonpickle.encode(config), jsonpickle.encode(check))

        del check.discord.channel_id
        config.discord.from_dict(check.discord.to_dict())

    def test_walk(self):
        config = VoteConfig()
        for f, k, v in config.walk():
            if f:
                print("")
            print(f"{k}={v}")

    def test_attr_doc(self):
        labels = Labels()
        print(labels.__doc__)
