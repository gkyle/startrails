"""Recent-project history persists ordering without duplicates or missing files."""

from support import IsolatedTestCase
from startrails.lib.recent import add_recent_project, get_recent_projects, remove_recent_project


class RecentProjectsTests(IsolatedTestCase):
    def test_history_orders_deduplicates_and_filters_missing_projects(self):
        first = self.root / "first.proj_startrails"
        second = self.root / "second.proj_denoise"
        first.touch()
        second.touch()
        add_recent_project(first)
        add_recent_project(second)
        add_recent_project(first)
        self.assertEqual(get_recent_projects(), [first, second])
        remove_recent_project(first)
        self.assertEqual(get_recent_projects(), [second])
        second.unlink()
        self.assertEqual(get_recent_projects(), [])
