"""The OS-visible process name of a Wysun QML app, so `ps`, `top` and the process monitor read `wysun-processes`
instead of `python3`. Set it early: the kernel keeps at most 15 bytes plus the terminator."""
import ctypes

PR_SET_NAME = 15
MAX_NAME = 15


def process_name(name):
    """The name as the kernel stores it: UTF-8, cut at 15 bytes on a character boundary."""
    raw = (name or '').encode('utf-8')[:MAX_NAME]
    while raw:
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            raw = raw[:-1]
    return ''


def set_process_name(name):
    """Set this process' `comm` (`/proc/self/comm`) through PR_SET_NAME; returns the name that was set. Never
    raises: without `prctl` (non-Linux) the app keeps running with its interpreter name."""
    short = process_name(name)
    if not short:
        return ''
    try:
        ctypes.CDLL(None, use_errno=True).prctl(PR_SET_NAME, ctypes.c_char_p(short.encode()), 0, 0, 0)
    except (OSError, AttributeError):
        return ''
    return short
