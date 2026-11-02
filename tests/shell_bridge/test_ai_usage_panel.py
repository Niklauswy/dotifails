"""AI usage panel QML: static guarantees that do not need a running shell."""
import re
import unittest
from pathlib import Path

SHELL = Path(__file__).resolve().parents[2] / 'apps/shell'
PANEL = SHELL / 'modules/aiusage'
SERVICE = SHELL / 'services/AiUsage.qml'


def qml(name):
    return (PANEL / name).read_text()


class ServiceTests(unittest.TestCase):
    def test_service_counts_only_visible_accounts(self):
        text = SERVICE.read_text()
        self.assertIn('Logic.tightest(visibleAccounts)', text)
        self.assertIn('Logic.indicatorTarget(visibleAccounts', text)
        self.assertIn('Logic.visibleAccounts(list.accounts', text)

    def test_settings_live_in_their_own_file(self):
        self.assertIn('`${Paths.config}/ai-usage.json`', SERVICE.read_text())

    def test_refresh_follows_the_adaptive_interval(self):
        text = SERVICE.read_text()
        self.assertIn('Logic.refreshInterval(settings.refresh', text)
        self.assertNotIn('backgroundInterval', text)


if __name__ == '__main__':
    unittest.main()
