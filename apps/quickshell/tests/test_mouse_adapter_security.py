"""Negative tests of the real mouse broker, without privilege or input devices.

Set WYSUN_MOUSE_HELPER_SOURCE to the source file during cross-worker review.
Default: apps/capture/privileged/wysun-pointer-helper in the integrated tree.
The helper is imported as a module, never executed through its privileged main.
All identities/session replies/socket metadata/selectors/device FDs are synthetic.
"""
import ast
import collections
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


DEFAULT = Path(__file__).resolve().parents[3] / "apps/capture/privileged/wysun-pointer-helper"
SOURCE = Path(os.environ.get("WYSUN_MOUSE_HELPER_SOURCE", str(DEFAULT)))


def session(uid=1000, **changes):
    return dict(Active=True, LockedHint=False, Remote=False, State="active", Type="wayland",
                Class="user", User=[uid, "/user"], Seat=["seat0", "/seat"], **changes)


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            if "WYSUN_MOUSE_HELPER_SOURCE" in os.environ:
                raise FileNotFoundError(SOURCE)
            raise unittest.SkipTest("Mouse helper absent; set WYSUN_MOUSE_HELPER_SOURCE (not a security PASS)")
        cls.source = SOURCE.read_text()
        cls.tree = ast.parse(cls.source)
        # Review the import surface before evaluating even unprivileged module code.
        for node in ast.walk(cls.tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if any(name.split(".")[0] not in sys.stdlib_module_names for name in names):
                    raise AssertionError("Non-stdlib import in privileged helper: " + repr(names))
        loader = importlib.machinery.SourceFileLoader("wysun_pointer_under_test", str(SOURCE))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.helper = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.helper)

    def setUp(self):
        self.h = self.helper
        self.identity = self.h.Identity(1000, 71, 12345)
        self.current = self.identity
        self.state = session()
        self.now = 0.0
        self.alive = True

    def guard(self, timeout=3):
        return self.h.Guard(self.identity, (71, 1000, 1000), lambda _: self.current,
                            lambda _: self.state, clock=lambda: self.now, timeout=timeout, alive_provider=lambda: self.alive)

    def test_entry_is_isolated_stdlib_and_has_no_forbidden_operations(self):
        self.assertEqual(self.source.splitlines()[0], "#!/usr/bin/python3 -I")
        forbidden = {"TakeControl", "ReleaseControl", "TakeDevice", "EVIOCGRAB", "/dev/uinput"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                for child in ast.walk(node):
                    if isinstance(child, ast.Constant):
                        self.assertNotIn(child.value if isinstance(child.value, (int, str)) else None, forbidden)
                        self.assertNotEqual(child.value, 0x40044590, "EVIOCGRAB ioctl literal")
                if isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, ("sendmsg", "exec_module", "load_module"), "No raw FD delivery or dynamic client imports")
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, ("eval", "exec", "__import__"))
                self.assertFalse(any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords))
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                self.assertFalse(any("sys.path" in ast.unparse(target) for target in targets))
        # This source-level check complements, not replaces, the fake I/O tests.
        self.assertNotIn("site.addsitedir", self.source)

    def test_canonical_arguments_reject_paths_and_extra_options(self):
        nonce = "a" * 64
        self.assertEqual(self.h.parse_arguments(["71", nonce]), (71, nonce))
        invalid = [[], ["71"], ["71", nonce, "RUN"], ["0", nonce], ["-1", nonce], ["+71", nonce],
                   ["071", nonce], ["../71", nonce], ["/proc/71", nonce], ["71\x00", nonce],
                   ["2147483648", nonce], ["71", "A" * 64], ["71", "a" * 63], ["71", "../" + nonce]]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(PermissionError):
                self.h.parse_arguments(args)
        for uid in (-1, 0, True, "1000"):
            with self.subTest(uid=uid), self.assertRaises(PermissionError):
                self.h.socket_path(uid, 71, nonce)

    def test_identity_reads_synthetic_proc_and_rejects_dead_or_truncated_process(self):
        with tempfile.TemporaryDirectory(prefix="wysun-proc-test-") as temporary:
            folder = Path(temporary) / "71"
            folder.mkdir()
            def write(state, start=12345):
                (folder / "stat").write_text("71 (name with ) spaces) " + " ".join([state] + ["0"] * 18 + [str(start)]))
            write("S")
            self.assertEqual(self.h.read_identity(71, temporary), self.h.Identity(os.getuid(), 71, 12345))
            write("S", 99999)
            self.assertNotEqual(self.h.read_identity(71, temporary).start, self.identity.start)
            for state in ("Z", "X"):
                write(state)
                with self.assertRaises(PermissionError): self.h.read_identity(71, temporary)
            (folder / "stat").write_text("71 (truncated) S 1")
            with self.assertRaises(PermissionError): self.h.read_identity(71, temporary)

    def test_peer_credentials_and_pid_reuse_fail_closed(self):
        self.assertTrue(self.h.validate_peer(self.identity, (71, 1000, 1000), self.identity))
        for peer, current in [((72, 1000, 1000), self.identity), ((71, 1001, 1000), self.identity),
                              ((71, 0, 0), self.identity), ((71, 1000), self.identity),
                              ((71, 1000, 1000), self.h.Identity(1000, 71, 12346))]:
            with self.subTest(peer=peer, current=current), self.assertRaises(PermissionError):
                self.h.validate_peer(self.identity, peer, current)

    def test_session_rejects_inactive_locked_remote_wrong_user_and_missing_seat(self):
        self.assertEqual(self.h.validate_session(self.identity, self.state), "seat0")
        invalid = {"Active": [False, "true", 1], "LockedHint": [True, None], "Remote": [True, None],
                   "State": ["closing", "online"], "Type": ["x11", "tty"], "Class": ["greeter", "lock-screen"],
                   "User": [[1001, "/user"], [], "1000"], "Seat": [[], ["", "/seat"], ["../seat0", "/seat"], "seat0"]}
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(PermissionError):
                    self.h.validate_session(self.identity, self.state | {field: value})
        for field in self.state:
            incomplete = dict(self.state); del incomplete[field]
            with self.subTest(missing=field), self.assertRaises(PermissionError):
                self.h.validate_session(self.identity, incomplete)

    def test_guard_revokes_pidfd_pid_reuse_session_and_seat_changes(self):
        for change in ("pid", "alive", "inactive", "locked", "seat", "provider_error"):
            self.setUp(); guard = self.guard()
            self.assertEqual(guard.check(), "seat0")
            if change == "pid": self.current = self.h.Identity(1000, 71, 77777)
            elif change == "alive": self.alive = False
            elif change == "inactive": self.state["Active"] = False
            elif change == "locked": self.state["LockedHint"] = True
            elif change == "seat": self.state["Seat"] = ["seat1", "/other-seat"]
            else: guard.session_provider = lambda _: (_ for _ in ()).throw(OSError("synthetic bus unavailable"))
            with self.subTest(change=change), self.assertRaises((PermissionError, OSError)): guard.check()
            self.assertTrue(guard.closed)
            self.current = self.identity; self.alive = True; self.state = session()
            with self.assertRaises(PermissionError): guard.touch()

    def test_guard_heartbeat_expiry_cannot_be_resurrected(self):
        guard = self.guard(); self.now = 2.0; guard.touch()
        self.now = 4.0; self.assertEqual(guard.check(), "seat0")
        self.now = 6.0
        with self.assertRaises(PermissionError): guard.touch()
        self.assertTrue(guard.closed)
        with self.assertRaises(PermissionError): guard.check()
        guard = self.guard(); guard.close()
        with self.assertRaises(PermissionError): guard.touch()
        # Keep heartbeat valid so this assertion exercises the absolute lease.
        guard = self.guard(timeout=self.h.MAX_LIFETIME + 10); self.now += self.h.MAX_LIFETIME + 1
        with self.assertRaises(PermissionError): guard.check()

    def test_socket_metadata_rejects_symlinks_owner_modes_and_traversal(self):
        base = Path("/synthetic-runtime/1000")
        path = base / "wysun-pointer" / ("71." + "a" * 64 + ".sock")
        def info(mode, uid=1000): return types.SimpleNamespace(st_mode=mode, st_uid=uid)
        valid = {base: info(stat.S_IFDIR | 0o700), path.parent: info(stat.S_IFDIR | 0o700), path: info(stat.S_IFSOCK | 0o600)}
        def validate(table, candidate=path):
            with patch.object(Path, "lstat", lambda value: table[value]):
                return self.h.validate_socket(candidate, 1000, runtime_root=base)
        self.assertTrue(validate(valid))
        for target, mode, uid in [(base, stat.S_IFLNK | 0o700, 1000), (path.parent, stat.S_IFLNK | 0o700, 1000),
                                  (path, stat.S_IFLNK | 0o600, 1000), (path, stat.S_IFREG | 0o600, 1000),
                                  (base, stat.S_IFDIR | 0o777, 1000), (path.parent, stat.S_IFDIR | 0o750, 1000),
                                  (path, stat.S_IFSOCK | 0o666, 1000), (path, stat.S_IFSOCK | 0o600, 1001)]:
            with self.subTest(target=target, mode=mode, uid=uid), self.assertRaises(PermissionError):
                validate(valid | {target: info(mode, uid)})
        for candidate in [base / ".." / path.name, Path("/tmp") / path.name, path.parent / "../escape.sock"]:
            with self.subTest(path=candidate), patch.object(Path, "lstat", side_effect=AssertionError("Must reject before filesystem access")), self.assertRaises(PermissionError):
                self.h.validate_socket(candidate, 1000, runtime_root=base)

    def test_device_seat_and_keyboard_composite_are_rejected(self):
        mouse = {"ID_INPUT_MOUSE": "1", "ID_SEAT": "seat0"}
        self.assertTrue(self.h.allowed_device(mouse, "seat0"))
        self.assertTrue(self.h.allowed_device({"ID_INPUT_TOUCHPAD": "1"}, "seat0"))
        for properties, seat in [(mouse, "seat1"), (mouse | {"ID_INPUT_KEYBOARD": "1"}, "seat0"),
                                  ({"ID_INPUT_KEYBOARD": "1"}, "seat0"), ({}, "seat0")]:
            with self.subTest(properties=properties, seat=seat):
                self.assertFalse(self.h.allowed_device(properties, seat))

    def test_device_open_rejects_symlink_traversal_and_changed_device_identity(self):
        path = Path("/dev/input/event99")
        good = types.SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=0, st_rdev=123)
        for candidate in (Path("/dev/input/../event99"), Path("/tmp/event99"), Path("/dev/input/not-event")):
            with patch.object(Path, "lstat", side_effect=AssertionError("Invalid path must not reach filesystem")), self.assertRaises(PermissionError):
                self.h.open_device(candidate, 123)
        for bad in (types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o600, st_uid=0, st_rdev=123),
                    types.SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=1000, st_rdev=123),
                    types.SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=0, st_rdev=456)):
            with patch.object(Path, "lstat", return_value=bad), patch.object(self.h.os, "open") as opener, self.assertRaises(PermissionError):
                self.h.open_device(path, 123)
            opener.assert_not_called()
        replaced = types.SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=0, st_rdev=456)
        with patch.object(Path, "lstat", return_value=good), patch.object(self.h.os, "open", return_value=91) as opener, patch.object(self.h.os, "fstat", return_value=replaced), patch.object(self.h.os, "close") as closer, self.assertRaises(PermissionError):
            self.h.open_device(path, 123)
        self.assertTrue(opener.call_args.args[1] & os.O_NOFOLLOW)
        self.assertTrue(opener.call_args.args[1] & os.O_NONBLOCK)
        self.assertEqual(opener.call_args.args[1] & os.O_ACCMODE, os.O_RDONLY)
        closer.assert_called_once_with(91)

    def test_privileged_entry_rejects_user_path_mode_owner_and_nonisolated_python(self):
        entry = self.h.ENTRY
        def metadata(path):
            return types.SimpleNamespace(st_uid=0, st_mode=(stat.S_IFREG if path == entry else stat.S_IFDIR) | 0o755)
        isolated = types.SimpleNamespace(flags=types.SimpleNamespace(isolated=True))
        with patch.object(self.h, "__file__", str(entry)), patch.object(self.h, "sys", isolated), patch.object(self.h.os, "geteuid", return_value=0), patch.object(Path, "lstat", metadata):
            self.h.verify_entry()
            with patch.object(self.h.os, "geteuid", return_value=1000), self.assertRaises(PermissionError): self.h.verify_entry()
            with patch.object(self.h, "__file__", "/home/synthetic/evil-helper"), self.assertRaises(PermissionError): self.h.verify_entry()
            with patch.object(self.h, "sys", types.SimpleNamespace(flags=types.SimpleNamespace(isolated=False))), self.assertRaises(PermissionError): self.h.verify_entry()
            for target in (entry, entry.parent):
                for uid, mode in ((1000, stat.S_IFREG | 0o755), (0, stat.S_IFREG | 0o777), (0, stat.S_IFLNK | 0o755)):
                    def altered(path): return types.SimpleNamespace(st_uid=uid, st_mode=mode) if path == target else metadata(path)
                    with self.subTest(target=target, uid=uid, mode=mode), patch.object(Path, "lstat", altered), self.assertRaises(PermissionError):
                        self.h.verify_entry()

    def test_opened_fd_capabilities_reject_keyboard_replacement_before_first_read(self):
        path = Path("/dev/input/event99")
        # Simulate stale inventory that classified this rdev/inode as a mouse.
        self.assertTrue(self.h.allowed_device({"ID_INPUT_MOUSE": "1"}, "seat0"))
        node = types.SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=0, st_rdev=123, st_dev=1, st_ino=9)
        for mask in ((1 << 272) | (1 << 30), (1 << 272) | (1 << 1), 1 << 273, 0):
            def ioctl(fd, request, data, mutate):
                self.assertEqual(fd, 91)
                self.assertEqual(request, (2 << 30) | (96 << 16) | (ord("E") << 8) | 0x21)
                self.assertIs(mutate, True)
                word = self.h.struct.calcsize("@L")
                for offset in range(0, 96, word):
                    data[offset:offset + word] = ((mask >> (offset * 8)) & ((1 << (word * 8)) - 1)).to_bytes(word, sys.byteorder)
                return 96
            with self.subTest(mask=mask), patch.object(Path, "lstat", return_value=node), patch.object(self.h.os, "open", return_value=91), patch.object(self.h.os, "fstat", return_value=node), patch.object(self.h.fcntl, "ioctl", ioctl), patch.object(self.h.os, "read") as reader, patch.object(self.h.os, "close") as closer, self.assertRaises(PermissionError):
                self.h.open_device(path, 123)
            reader.assert_not_called(); closer.assert_called_once_with(91)

    def test_opened_fd_capabilities_accept_mouse_and_close_on_ioctl_failure(self):
        node = types.SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=0, st_rdev=123, st_dev=1, st_ino=9)
        def mouse_ioctl(fd, request, data, mutate):
            # BTN_LEFT bit is byte34 bit0 on every native-word layout.
            word = self.h.struct.calcsize("@L"); offset = 272 // (word * 8) * word
            data[offset:offset + word] = (1 << (272 % (word * 8))).to_bytes(word, sys.byteorder)
            return 96
        with patch.object(Path, "lstat", return_value=node), patch.object(self.h.os, "open", return_value=91), patch.object(self.h.os, "fstat", return_value=node), patch.object(self.h.fcntl, "ioctl", mouse_ioctl), patch.object(self.h.os, "read") as reader, patch.object(self.h.os, "close") as closer:
            self.assertEqual(self.h.open_device(Path("/dev/input/event99"), 123), 91)
        reader.assert_not_called(); closer.assert_not_called()
        for error in (OSError("synthetic ioctl unavailable"), OSError("synthetic fstat unavailable")):
            with patch.object(Path, "lstat", return_value=node), patch.object(self.h.os, "open", return_value=91), patch.object(self.h.os, "fstat", side_effect=error if "fstat" in str(error) else None, return_value=node), patch.object(self.h.fcntl, "ioctl", side_effect=error), patch.object(self.h.os, "close") as closer, self.assertRaises(OSError):
                self.h.open_device(Path("/dev/input/event99"), 123)
            closer.assert_called_once_with(91)

    def test_decoder_drops_keyboard_scancodes_repeat_and_unknown_values(self):
        event = self.h.EVENT.pack
        safe = event(1, 500000, 1, 272, 1) + event(1, 600000, 1, 273, 0) + event(2, 0, 1, 274, 1)
        unsafe = b"".join([event(1, 0, 1, 30, 1), event(1, 0, 4, 4, 30), event(1, 0, 1, 272, 2),
                            event(1, 0, 1, 275, 1), event(-1, 0, 1, 272, 1), event(1, 1000000, 1, 272, 1)])
        decoded, remainder = self.h.decode_events(safe + unsafe + b"partial")
        self.assertEqual(decoded, [{"t": 1.5, "button": 1, "value": 1}, {"t": 1.6, "button": 3, "value": 0}, {"t": 2.0, "button": 2, "value": 1}])
        self.assertEqual(remainder, b"partial")
        first, rest = self.h.decode_events(safe[:7]); self.assertEqual(first, [])
        self.assertEqual(self.h.decode_events(rest + safe[7:])[0], decoded)

    def stream(self, steps, output=None):
        """Exercise real serve(), replacing only I/O with finite synthetic steps."""
        owner = self
        control = types.SimpleNamespace()
        control.sendall = lambda data: self.assertEqual(data, b"READY\n")
        control.recv = lambda count: owner.packet[:count]
        queue = collections.deque(steps)
        closed, opened, reads = [], [], []
        self.packet = b""
        self.event_data = b""
        class Selector:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def register(self, *_): pass
            def unregister(self, *_): pass
            def select(self, timeout):
                if not queue: raise AssertionError("Unexpected extra selector iteration")
                kind, value = queue.popleft()
                if callable(value): value = value()
                if kind == "timeout": return []
                if kind == "control":
                    owner.packet = value
                    return [(types.SimpleNamespace(fileobj=control, fd=1), 1)]
                owner.event_data = value
                return [(types.SimpleNamespace(fileobj=91, fd=91), 1)]
        def opener(path, device): opened.append((path, device)); return 91
        def read(fd, count): reads.append(fd); return self.event_data
        guard = self.guard(); output = output or io.StringIO()
        with patch.object(self.h.selectors, "DefaultSelector", Selector), patch.object(self.h.os, "read", read), patch.object(self.h.os, "close", closed.append):
            try:
                self.h.serve(control, guard, output, lambda seat: [(Path("/synthetic-mouse"), 1)], opener)
            finally:
                self.stream_state = dict(closed=closed, opened=opened, reads=reads, guard=guard, output=output)
        return self.stream_state

    def test_stream_run_pause_closes_mouse_and_stop_closes_guard(self):
        result = self.stream([("control", b"RUN\n"), ("device", self.h.EVENT.pack(1, 0, 1, 272, 1)),
                              ("control", b"PAUSE\n"), ("control", b"STOP\n")])
        self.assertEqual(result["closed"], [91]); self.assertEqual(len(result["opened"]), 1)
        self.assertEqual(len(result["output"].getvalue().splitlines()), 1); self.assertTrue(result["guard"].closed)

    def test_stream_peer_close_before_and_after_run_cleans_fds(self):
        for steps, expected in [([("control", b"")], []), ([("control", b"RUN\n"), ("control", b"")], [91])]:
            self.setUp(); result = self.stream(steps)
            self.assertEqual(result["closed"], expected); self.assertTrue(result["guard"].closed)
            self.assertEqual(result["output"].getvalue(), "")

    def test_stream_invalid_oversize_commands_close_devices(self):
        for payload in (b"../device\n", b"KEYBOARD\n", b"PING\x00\n", b"P" * 129):
            self.setUp()
            with self.subTest(payload=payload), self.assertRaises(PermissionError):
                self.stream([("control", b"RUN\n"), ("control", payload)])
            self.assertEqual(self.stream_state["closed"], [91]); self.assertTrue(self.stream_state["guard"].closed)

    def test_stream_timeout_closes_devices_without_more_input(self):
        def expires(): self.now = 4.0
        with self.assertRaises(PermissionError): self.stream([("control", b"RUN\n"), ("timeout", expires)])
        self.assertEqual(self.stream_state["closed"], [91]); self.assertEqual(self.stream_state["output"].getvalue(), "")

    def test_stream_revocation_drops_already_queued_mouse_event(self):
        for reason in ("pid_reuse", "inactive", "locked", "seat", "peer_dead"):
            self.setUp()
            def revoke():
                if reason == "pid_reuse": self.current = self.h.Identity(1000, 71, 99999)
                elif reason == "inactive": self.state["Active"] = False
                elif reason == "locked": self.state["LockedHint"] = True
                elif reason == "seat": self.state["Seat"] = ["seat1", "/seat1"]
                else: self.alive = False
                return self.h.EVENT.pack(1, 0, 1, 272, 1)
            with self.subTest(reason=reason), self.assertRaises(PermissionError):
                self.stream([("control", b"RUN\n"), ("device", revoke)])
            self.assertEqual(self.stream_state["closed"], [91]); self.assertEqual(self.stream_state["output"].getvalue(), "")

    def test_stream_keyboard_never_reaches_client_output(self):
        result = self.stream([("control", b"RUN\n"), ("device", self.h.EVENT.pack(1, 0, 1, 30, 1)), ("control", b"STOP\n")])
        self.assertEqual(result["output"].getvalue(), ""); self.assertEqual(result["closed"], [91])

    def test_stream_device_eof_closes_without_reopening_an_arbitrary_path(self):
        result = self.stream([("control", b"RUN\n"), ("device", b""), ("control", b"STOP\n")])
        self.assertEqual(result["closed"], [91]); self.assertEqual(len(result["opened"]), 1)
        self.assertEqual(result["output"].getvalue(), ""); self.assertTrue(result["guard"].closed)

    def test_stream_output_backpressure_is_nonblocking_and_closes_devices(self):
        output = types.SimpleNamespace(fileno=lambda: 200)
        with patch.object(self.h.os, "set_blocking") as blocking, patch.object(self.h.os, "write", side_effect=BlockingIOError("synthetic full pipe")), self.assertRaises(BlockingIOError):
            self.stream([("control", b"RUN\n"), ("device", self.h.EVENT.pack(1, 0, 1, 272, 1))], output)
        blocking.assert_called_once_with(200, False)
        self.assertEqual(self.stream_state["closed"], [91]); self.assertTrue(self.stream_state["guard"].closed)


if __name__ == "__main__":
    unittest.main()
