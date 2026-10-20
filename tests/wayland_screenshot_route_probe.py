#!/usr/bin/env python3
"""Native public Screenshot proof; private nested runtime only.

Add --tmpfs /tmp/hypr to the documented bwrap nested_runtime.py command and use
--probe-only --probe tests/wayland_screenshot_route_probe.py --probe-timeout 180.
Use tests/wayland_screenshot_pending_probe.py to repeat only the 55s pending
regression after a close-lifecycle change. The imported probe rejects host
displays/buses and provides only WYSUN-TEST-1.
"""
from wayland_portal_probe import main

if __name__ == '__main__':
    import sys
    if '--pending-only' in sys.argv:
        from functools import partial
        import wayland_screenshot_route_case as route
        route.run_case=partial(route.run_case,pending_only=True)
    main(case_selector='screenshot-route')
