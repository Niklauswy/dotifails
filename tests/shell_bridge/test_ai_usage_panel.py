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


SIZE = re.compile(r'\b(?:implicitWidth|implicitHeight|width|height|radius|spacing|margins|[a-z]+Margin|padding)\s*:\s*(\d+)\b')


class PanelTests(unittest.TestCase):
    def files(self):
        return sorted(PANEL.glob('*.qml'))

    def test_panel_has_no_card_grid(self):
        for path in self.files():
            text = path.read_text()
            self.assertNotIn('Card {', text, path.name)
            self.assertNotIn('GridLayout', text, path.name)
        self.assertFalse((PANEL / 'Card.qml').exists())

    def test_tabs_are_per_provider(self):
        text = qml('ProviderTabs.qml')
        self.assertIn('AiUsage.providers', text)
        self.assertNotIn('AiUsage.accounts', text)

    def test_hidden_accounts_are_filtered(self):
        # Only Settings lists every account, so hidden ones can be shown again.
        for path in self.files():
            if path.name != 'SettingsPage.qml':
                self.assertNotRegex(path.read_text(), r'AiUsage\.accounts\b', path.name)

    def test_overview_totals_use_visible_accounts(self):
        text = qml('OverviewPage.qml')
        self.assertNotIn('AiUsage.usage', text)
        self.assertIn('AiUsage.visibleAccounts', text)

    # The logo paths are drawn in a 24×24 coordinate space, then scaled to a token size.
    SIZE_EXCEPTIONS = {'ProviderLogo.qml'}

    def test_no_literal_sizes(self):
        for path in self.files():
            if path.name in self.SIZE_EXCEPTIONS:
                continue
            for match in SIZE.finditer(path.read_text()):
                self.assertLessEqual(int(match.group(1)), 4, f'{path.name}: {match.group(0)}')


if __name__ == '__main__':
    unittest.main()
