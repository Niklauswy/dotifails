#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
# Only inside this disposable container: remove a boot splash from an earlier test.
if dpkg-query -W -f='${Status}' plymouth 2>/dev/null | grep -q 'unpacked\|half-configured'; then
    apt-get purge -y plymouth plymouth-label
fi
apt-get update
apt-get install --no-install-recommends -y sudo python3 git ca-certificates curl xvfb xauth shellcheck python3-pyside6.qttest
id tester2 >/dev/null 2>&1 || useradd -m -s /bin/bash tester2
printf '%s\n' 'tester2 ALL=(ALL) NOPASSWD:ALL' >/etc/sudoers.d/tester2
mkdir -p /opt/dotifails
(cd /src && tar --exclude=.git --exclude=__pycache__ --exclude=test-results -cf - .) | tar -xf - -C /opt/dotifails
chown -R tester2:tester2 /opt/dotifails
su tester2 -c 'export PATH="$HOME/.local/bin:$PATH"; cd /opt/dotifails && ./instalar.sh'
su tester2 -c 'export PATH="$HOME/.local/bin:$PATH"; cd /opt/dotifails && python3 -m unittest discover -s tests -v'
su tester2 -c 'export PATH="$HOME/.local/bin:$PATH"; cd /opt/dotifails/apps/orbit && QT_QPA_PLATFORM=offscreen python3 -m unittest test_orbit test_v2 test_v3 test_v4 test_settings_hub test_bar_visibility -q'
su tester2 -c 'export PATH="$HOME/.local/bin:$PATH"; cd /opt/dotifails && ./instalar.sh --skip-nvim-tools'
su tester2 -c 'PATH="$HOME/.local/bin:$PATH" "$HOME/.config/nvim/scripts/verify.sh"'
su tester2 -c 'export PATH="$HOME/.local/bin:$PATH"; DOTIFAILS_ISOLATED_TEST=1 xvfb-run -a -s "-screen 0 1366x768x24 +extension GLX" dbus-run-session -- python3 /opt/dotifails/tests/session_smoke.py'
printf '\nFULL_CONTAINER_INSTALL_OK\n'
