"""Shell contract for "Save and view" and the screen-awake hint: static checks of the QML (no Quickshell in unit tests)."""
import re
import unittest
from pathlib import Path

SHELL = Path(__file__).resolve().parents[1] / 'apps/shell'


def source(relative):
    return (SHELL / relative).read_text()


def function_body(text, name):
    start = text.index(f'function {name}(')
    brace = text.index('{', start)
    depth = 0
    for index in range(brace, len(text)):
        depth += {'{': 1, '}': -1}.get(text[index], 0)
        if depth == 0:
            return text[brace:index + 1]
    raise AssertionError(name)


class SaveAndViewTests(unittest.TestCase):
    def setUp(self):
        self.session = source('modules/areapicker/Session.qml')

    def test_saving_reports_completion_instead_of_returning_a_path_early(self):
        signature = re.search(r'function keep\(([^)]*)\)\s*:\s*(\w+)', self.session)
        self.assertIsNotNone(signature)
        self.assertEqual(signature.group(2), 'void', 'keep() used to return the target before the copy had run')
        self.assertIn('done', signature.group(1))
        self.assertIn('failed', signature.group(1))
        self.assertIn('property Process saver', self.session)
        self.assertIn('code === 0 ? pending.done(pending.target) : pending.failed()', self.session)
        self.assertNotIn('Quickshell.execDetached(["sh", "-c", \'mkdir -p', self.session, 'the copy must run in the tracked process')

    def test_the_command_verifies_the_published_file(self):
        self.assertIn('test -s "$2"', self.session)

    def test_the_viewer_opens_only_after_the_file_is_published(self):
        body = function_body(self.session, 'view')
        self.assertIn('keep(path, saved => {', body)
        launch = body.index('["wysun", "player", "--", saved]')
        self.assertGreater(launch, body.index('keep('), 'launch sits inside the success callback')
        self.assertIn('notifyFailure', body, 'a failed save is reported')
        failure = body[body.index('}, notifyFailure'):]
        self.assertNotIn('finished()', failure, 'a failed save keeps the overlay open so it can be retried')

    def test_a_failed_quick_save_still_closes_but_tells_the_person(self):
        body = function_body(self.session, 'deliver')
        self.assertIn('notifyFailure();', body)
        self.assertIn('copy to the clipboard did succeed', body)

    def test_the_action_is_offered_and_reachable_by_keyboard(self):
        bar, picker = source('modules/areapicker/ActionBar.qml'), source('modules/areapicker/Picker.qml')
        self.assertIn('signal view', bar)
        self.assertIn('Tr.tr("Save and view")', bar)
        self.assertIn('onClicked: root.view()', bar)
        self.assertIn('onView: root.view()', picker)
        self.assertIn('phase === "actions" && event.key === Qt.Key_V', picker)
        self.assertIn('session.view(frame)', picker)


class ScreenAwakeTests(unittest.TestCase):
    def test_a_visible_playing_video_keeps_the_screen_on_without_touching_the_manual_switch(self):
        text = source('daemons/IdleInhibit.qml')
        self.assertIn('"wysun:visibleVideo"', text)
        self.assertIn('enabled: RuntimeState.inhibitIdle || root.videoPlaying', text)
        self.assertEqual(text.count('RuntimeState.inhibitIdle = '), 3, 'only the existing manual handlers write the switch')
        self.assertNotIn('inhibitIdle = root.videoPlaying', text)
        self.assertIn('RuntimeState.inhibitIdle || root.videoPlaying;', text, 'isInhibiting() reports both reasons')
        for method in ('isEnabled', 'isInhibiting', 'toggle', 'enable', 'disable'):
            self.assertIn(f'function {method}()', text)

    def test_the_metadata_key_matches_what_the_player_publishes(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
        from wysun_media import mpris
        self.assertEqual(mpris.VISIBLE_VIDEO, 'wysun:visibleVideo')


if __name__ == '__main__':
    unittest.main()
