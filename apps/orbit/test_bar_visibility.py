import unittest

from bar_visibility import Visibility, fullscreen_monitors


def window(state="tiled", hidden=False):
    return {"hidden": hidden, "client": {"state": state}}


def desktop(ident, root):
    return {"id": ident, "root": root}


def monitor(name, active, *desktops):
    return {"name": name, "focusedDesktopId": active, "desktops": list(desktops)}


class FullscreenBarTests(unittest.TestCase):
    def setUp(self):
        self.state = {"monitors": [
            monitor("DP-2", 1, desktop(1, window("fullscreen")), desktop(2, None)),
            monitor("DP-1", 3, desktop(3, window()), desktop(4, window("fullscreen"))),
        ]}
        self.bars = {101: ("DP-2", 1001, 1), 102: ("DP-2", 1002, 1), 201: ("DP-1", 2001, 1)}

    def test_only_visible_desktop_on_each_monitor(self):
        self.assertEqual(fullscreen_monitors(self.state), {"DP-2": True, "DP-1": False})
        self.state["monitors"][0]["focusedDesktopId"] = 2
        self.assertEqual(fullscreen_monitors(self.state), {"DP-2": False, "DP-1": False})

    def test_hidden_fullscreen_and_hidden_subtree_do_not_hide_bar(self):
        desk = self.state["monitors"][0]["desktops"][0]
        desk["root"] = {"firstChild": window(), "secondChild": window("fullscreen", True)}
        self.assertFalse(fullscreen_monitors(self.state)["DP-2"])
        desk["root"] = {"hidden": True, "firstChild": window("fullscreen")}
        self.assertFalse(fullscreen_monitors(self.state)["DP-2"])

    def test_close_or_exit_fullscreen_restores_all_sections(self):
        sent = []
        controller = Visibility(lambda pid, hide: sent.append((pid, hide)) or True)
        controller.update(self.state, self.bars)
        self.assertEqual(sent, [(101, True), (102, True), (201, False)])
        controller.update(self.state, self.bars)
        self.assertEqual(len(sent), 3, "Unchanged bars should not receive repeated commands")
        self.state["monitors"][0]["desktops"][0]["root"] = None
        controller.update(self.state, self.bars)
        self.assertEqual(sent[-2:], [(101, False), (102, False)])

    def test_in_place_bar_restart_reapplies_hidden_state(self):
        sent = []
        controller = Visibility(lambda pid, hide: sent.append((pid, hide)) or True)
        controller.update(self.state, self.bars)
        self.bars[101] = ("DP-2", 3001, 2)
        controller.update(self.state, self.bars)
        self.assertEqual(sent[-1], (101, True))
        self.assertEqual(len(sent), 4)

    def test_failed_ipc_retries_and_shutdown_restores_only_hidden_bars(self):
        sent = []
        controller = Visibility(lambda pid, hide: False)
        controller.update(self.state, self.bars)
        self.assertEqual(controller.applied, {})
        controller.sender = lambda pid, hide: sent.append((pid, hide)) or True
        controller.update(self.state, self.bars)
        controller.restore()
        self.assertEqual(sent[-2:], [(101, False), (102, False)])
        self.assertEqual(controller.applied, {})


if __name__ == "__main__":
    unittest.main()
