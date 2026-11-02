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

    def test_bars_show_what_is_left_by_default(self):
        self.assertIn('showUsed: false', SERVICE.read_text())

    def test_confetti_waits_for_a_size(self):
        text = qml('Confetti.qml')
        self.assertNotIn('Component.onCompleted', text)
        self.assertIn('pieces.length === 0', text)

    def test_backend_is_killed_when_it_hangs(self):
        self.assertIn('loader.running = false', SERVICE.read_text())

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


class NavigationTests(unittest.TestCase):
    def test_a_press_in_the_panel_pins_it_open(self):
        self.assertIn('root.interacted()', qml('Content.qml'))
        self.assertIn('mouse.accepted = false', qml('Content.qml'))
        self.assertIn('aiUsagePinned = true', qml('Wrapper.qml'))
        self.assertIn('aiUsagePinned = false', qml('Wrapper.qml'))

    def test_hover_never_closes_a_pinned_panel(self):
        text = (SHELL / 'modules/drawers/Interactions.qml').read_text()
        self.assertEqual(text.count('!aiUsageShortcutActive && !screenState.aiUsagePinned'), 2)
        self.assertNotIn('if (!aiUsageShortcutActive)', text)

    def test_every_navigation_starts_at_the_top(self):
        text = qml('Content.qml')
        for handler in ('onPageChanged', 'onProviderChanged', 'onAddingChanged'):
            self.assertIn(handler, text)
        self.assertIn('scroller.contentY = 0', text)


class OverviewTests(unittest.TestCase):
    def test_accounts_come_first_and_sessions_stay_in_the_account_page(self):
        text = qml('OverviewPage.qml')
        self.assertNotIn('SessionRows', text)
        self.assertIn('SessionRows', qml('AccountPage.qml'))
        self.assertLess(text.index('AiUsage.providers'), text.index('UsageSummary'))

    def test_summary_adds_only_visible_accounts(self):
        text = qml('UsageSummary.qml')
        self.assertIn('Logic.aggregateUsage(AiUsage.visibleAccounts', text)
        for field in ('cacheRead', 'savings', 'models', 'projects'):
            self.assertIn(field, text)


class PageTests(unittest.TestCase):
    def test_settings_write_through_service(self):
        text = qml('SettingsPage.qml')
        self.assertIn('AiUsage.setSetting(', text)
        self.assertIn('AiUsage.setHidden(', text)
        self.assertNotIn('FileView', text)
        self.assertNotIn('setText(', text)

    def test_disk_page_never_deletes(self):
        text = qml('DiskPage.qml')
        for word in ('rm ', '"rm"', 'unlink', 'remove', 'trash'):
            self.assertNotIn(word, text)

    def test_cost_page_has_four_tabs(self):
        text = qml('CostPage.qml')
        for value in ('"daily"', '"windows"', '"activity"', '"ledger"'):
            self.assertIn(value, text)

    def test_history_page_draws_the_even_use_guide(self):
        text = qml('LimitHistoryPage.qml')
        self.assertIn('limit.history', text)
        self.assertIn('limit.windows', text)
        self.assertIn('paceGuide', text)


class IndicatorTests(unittest.TestCase):
    def test_indicator_uses_indicator_target(self):
        text = (SHELL / 'modules/bar/components/AiUsageIndicator.qml').read_text()
        self.assertIn('AiUsage.indicator', text)
        self.assertIn('AiUsage.isStale(', text)
        self.assertNotIn('AiUsage.tightest', text)
        for style in ('"meters"', '"percent"', '"stacked"', '"pace"'):
            self.assertIn(style, text)

    def test_confetti_follows_weekly_reset(self):
        text = qml('Confetti.qml')
        self.assertIn('onWeeklyReset', text)
        self.assertIn('Colours.palette', text)


if __name__ == '__main__':
    unittest.main()
