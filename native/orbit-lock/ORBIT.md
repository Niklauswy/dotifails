# Wysun lock renderer

Based on upstream i3lock tag 2.15. Original BSD license is preserved in LICENSE.
Source archive: https://github.com/i3/i3lock/archive/refs/tags/2.15.tar.gz
Archive SHA-256: b3253dfc42b6fa3879498310b536d42224d3a492f9a957a5652e6ff6c91862dc

Local changes: orbit_motion.c replaces the indicator renderer and adds an event-driven
60 Hz animation timer. Keys produce an interruptible 380 ms ripple and a short arc.
Backspace uses an amber cue. Failed authentication shows a rose ring and a 460 ms
settling shake. Entrance fades the artwork in over 360 ms after grabs are held.
After successful authentication, a mint check appears and the window opacity fades
out over 280 ms; grabs remain held until the final frame. Opacity requires a running
X11 compositor such as Picom. Reduced motion keeps static feedback and immediate exit.

The native i3lock PAM service, authentication conversation, password clearing,
UTF-8 handling, X11 grabs, raise-loop process, and focus restoration are upstream.
No password characters, input length, or credentials are exposed to the renderer.
The only authentication change is delaying the successful event-loop break until the
exit animation completes. Key pulse notifications contain only a backspace boolean.
No Qt password window or external password process is involved.

The installer builds locally with Meson and deploys the executable separately to
~/.local/share/orbit/bin/orbit-lock. It uses the system /etc/pam.d/i3lock configuration
installed by the i3lock Debian package. Sources are vendored; building needs no network.

`ORBIT_THEME` selects Tokyo (violet, wider 380 ms pulse, 400 ms entrance, 320 ms exit) or Severance (icy cyan, precise 240 ms pulse/entrance, 200 ms exit). The Qt launcher passes the current persisted theme for each lock.
