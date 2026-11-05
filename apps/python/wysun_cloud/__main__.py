"""`python3 -m wysun_cloud` (what `wysun cloud` runs)."""
import subprocess
import sys
import time

from wysun_core import launch
from wysun_cloud import inventory
from wysun_cloud.gcloud import Gcloud, GcloudError


def estado():
    """One gcloud read for the bar: write the private state file, save the cache, stay silent.

    Any gcloud failure exits 0 and leaves the previous state file alone, so the bar keeps
    showing what it last knew instead of flashing an error.
    """
    try:
        inventory.refresh(Gcloud(), time.time())
    except GcloudError:
        pass
    return 0


def terminal():
    """Open the TUI in a new terminal window, detached from the shell that asked for it."""
    argv = launch.terminal_argv(['wysun', 'cloud'])
    if argv is None:
        print('No encontré una terminal para abrir Wysun Cloud', file=sys.stderr)
        return 1
    subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--terminal' in args:
        return terminal()
    if '--estado' in args:
        return estado()
    from wysun_cloud.ui.cloudapp import CloudApp
    return CloudApp().run()


if __name__ == '__main__':
    raise SystemExit(main())
