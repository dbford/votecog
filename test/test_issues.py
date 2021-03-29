import os
import unittest

from git_vote_cog.issues import *


class TestIssues(unittest.IsolatedAsyncioTestCase):
    async def test_get_repo(self):
        api_token = os.environ["GIT_API_TOKEN"]
        repo_name = "dbford/votecog"

        repo = await open_issue_repo(api_token, repo_name)
        print(repo)

        issue = await repo.get_issue(1)
        self.assertTrue(issue.exists)
