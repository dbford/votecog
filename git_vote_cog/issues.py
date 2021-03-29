import asyncio
from typing import Optional, Set, Union

import github
from github import Github, Repository, PullRequest


class Issue:
    def __init__(self, pr: Optional[PullRequest.PullRequest]):
        # class variables def
        self._pr: Optional[PullRequest.PullRequest] = None
        self.id: int = -1
        self.url: str = ""
        self.title: str = ""
        self.description: str = ""
        self.author: str = ""
        self.labels: Set[str] = set()
        self.exists: bool = False

        # init class
        self.pr = pr

    async def remove_label(self, tag: [str]):
        _self = self

        def _do():
            try:
                _self.pr.remove_from_labels(tag)
                _self.labels.remove(tag)
            except github.GithubException as err:
                if not err.status == 404:
                    raise err

        await asyncio.get_running_loop().run_in_executor(None, _do)

    async def add_label(self, tag: str):
        _self = self

        def _do():
            _self.pr.add_to_labels(tag)
            _self.labels.add(tag)

        await asyncio.get_running_loop().run_in_executor(None, _do)

    async def update(self):
        if self.pr is None:
            return

        _self = self

        def _do():
            try:
                _self.pr.update()
                _self.pr = _self.pr
            except github.UnknownObjectException:
                _self.pr = None

        await asyncio.get_running_loop().run_in_executor(None, _do)

    @property
    def pr(self) -> Optional[PullRequest.PullRequest]:
        return self._pr

    @pr.setter
    def pr(self, pr: Optional[PullRequest.PullRequest]):
        self._pr = pr
        if pr is None:
            self.id = -1
            self.exists = False
        else:
            self.id = pr.number
            self.url = pr.url
            self.title = pr.title
            self.description = pr.body
            self.author = pr.user.login
            self.labels = {label.name for label in pr.labels}
            self.exists = pr.state == "open" and not pr.is_merged()


class IssueRepo:
    def __init__(self, client: Github, repo: Repository):
        self.client: Github = client
        self.repo: Repository = repo
        self.repo_id: int = repo.id

    async def get_issue(self, pr_id: int) -> Optional[Issue]:
        def _do():
            issue: Optional[Issue]
            try:
                pr = self.repo.get_pull(pr_id)
                issue = Issue(pr)
            except github.UnknownObjectException:
                issue = None

            return issue

        return await asyncio.get_running_loop().run_in_executor(None, _do)


async def open_issue_repo(personal_api_token: str, repo_name_or_id: Union[int, str]) -> IssueRepo:
    def _do():
        client = Github(personal_api_token)
        repo = client.get_repo(repo_name_or_id, lazy=False)

        return IssueRepo(client, repo)

    return await asyncio.get_event_loop().run_in_executor(None, _do)
