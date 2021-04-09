from typing import Optional, Set

import github
from github.PullRequest import PullRequest

from git_vote_cog.util import wrap_async


class Issue:
    def __init__(self, pr: Optional[PullRequest]):
        # class variables def
        self._pr: Optional[PullRequest] = None
        self.id: int = -1
        self.url: str = ""
        self.title: str = ""
        self.description: str = ""
        self.author: str = ""
        self.labels: Set[str] = set()
        self.exists: bool = False

        # init class
        self.pr = pr

    @wrap_async
    def remove_label(self, tag: [str]):
        try:
            self.pr.remove_from_labels(tag)
        except github.GithubException as err:
            if not err.status == 404:
                raise err

        try:
            self.labels.remove(tag)
        except KeyError:
            pass

    @wrap_async
    def add_label(self, tag: str):
        self.pr.add_to_labels(tag)
        self.labels.add(tag)

    @wrap_async
    def update(self):
        if self.pr is None:
            return

        try:
            self.pr.update()
            self.pr = self.pr
        except github.UnknownObjectException:
            self.pr = None

    @property
    def pr(self) -> Optional[PullRequest]:
        return self._pr

    @pr.setter
    def pr(self, pr: Optional[PullRequest]):
        self._pr = pr
        if pr is None:
            self.id = -1
            self.exists = False
        else:
            self.id = pr.number
            self.url = pr.html_url
            self.title = pr.title
            self.description = pr.body
            self.author = pr.user.login
            self.labels = {label.name for label in pr.labels}
            self.exists = pr.state == "open" and not pr.is_merged()

    def __str__(self) -> str:
        return f"PR(id={self.id}, exists={self.exists})"
