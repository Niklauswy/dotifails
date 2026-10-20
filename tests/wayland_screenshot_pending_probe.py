#!/usr/bin/env python3
"""Pending/cancel/reopen regression only (55s across both legacy close deadlines); same private nested guards as route."""
from functools import partial
import wayland_screenshot_route_case as route
from wayland_portal_probe import main

if __name__ == '__main__':
    route.run_case=partial(route.run_case,pending_only=True,pending_hold_s=55.0)
    main(case_selector='screenshot-route')
