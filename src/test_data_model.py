import random
import time
import unittest

from data_model import Issue, Vote, PollingPlace


def test_issue() -> Issue:
    issue = Issue()
    issue.url = "localhost"
    issue.id = "PR-{}".format(random.randint(1000, 2000))
    issue.title = "Merge a cool new feature"
    issue.description = ""
    issue.tags = {"one", "two", "three", "four"}
    issue.author = "unit_test"

    return issue


class VoteTest(unittest.TestCase):
    def test_positive(self):
        vote = Vote(test_issue(), 1_000)

        vote.positive_count = 100
        vote.negative_count = 99
        self.assertTrue(vote.is_positive())

        vote.positive_count = vote.negative_count
        self.assertFalse(vote.is_positive())

        vote.positive_count = 99
        vote.negative_count = 100
        self.assertFalse(vote.is_positive())

    def test_remaining_seconds(self):
        vote = Vote(test_issue(), 1_000)
        self.assertEqual(1_000, vote.remaining_seconds())

        vote = Vote(test_issue(), 10)
        self.assertEqual(10, vote.remaining_seconds())

        vote = Vote(test_issue(), 0)
        self.assertEqual(0, vote.remaining_seconds())

        time.sleep(2)
        self.assertEqual(0, vote.remaining_seconds())


class PollingPlaceTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_vote(self):
        pp = PollingPlace()

        # create a test vote
        issue = test_issue()
        await issue.add_tag(pp.tag_needs_vote)
        vote = await pp.start_vote(issue, 1_000)

        self.assertEqual(1_000, vote.remaining_seconds())
        self.assertFalse(pp.tag_needs_vote in issue.tags)
        self.assertTrue(pp.tag_voting in issue.tags)

    async def test_end_vote(self):
        pp = PollingPlace()

        issue = test_issue()
        await issue.add_tag(pp.tag_voting)
        vote = Vote(issue, 1_000)
        vote.positive_count = 99
        vote.negative_count = 50

        await pp.end_vote(vote)
        self.assertTrue(pp.tag_accept in vote.issue.tags)
        self.assertFalse(pp.tag_reject in vote.issue.tags)
        self.assertFalse(pp.tag_voting in vote.issue.tags)
