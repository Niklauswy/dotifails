pragma Singleton

import QtQuick
import Quickshell

// "Identify displays": a big label on every screen for a few seconds, so the names in Settings can be
// matched with the monitors on the desk. `showing` drives the card's entrance and exit; `alive` keeps
// the windows around just long enough for the exit to play, so nothing exists while it is idle.
Singleton {
    id: root

    property bool showing
    property bool alive

    function show(): void {
        alive = true;
        showing = true;
        hide.restart();
    }

    Timer {
        id: hide

        interval: 3500
        onTriggered: {
            root.showing = false;
            gone.restart();
        }
    }

    Timer {
        id: gone

        interval: 600
        onTriggered: root.alive = root.showing
    }
}
