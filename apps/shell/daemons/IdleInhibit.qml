import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Wysun.State
import qs.services

Scope {
    id: root

    Connections {
        function onInhibitIdleChanged(): void {
            if (RuntimeState.inhibitIdle)
                RuntimeState.inhibitingIdleSince = new Date().getTime();
        }

        target: RuntimeState
    }

    // Wysun Player marks a visible, playing video in its MPRIS metadata (wysun:visibleVideo). That keeps the
    // screen awake by itself and leaves the manual "keep awake" switch (RuntimeState.inhibitIdle) alone.
    readonly property bool videoPlaying: Players.list.find(player => player.metadata["wysun:visibleVideo"] === true) !== undefined

    IdleInhibitor {
        enabled: RuntimeState.inhibitIdle || root.videoPlaying
        window: PanelWindow {
            implicitWidth: 0
            implicitHeight: 0
            color: "transparent"
            mask: Region {}
        }
    }

    IpcHandler {
        function isEnabled(): bool {
            return RuntimeState.inhibitIdle;
        }

        // Whether the screen is being kept awake right now, by the switch or by a playing video.
        function isInhibiting(): bool {
            return RuntimeState.inhibitIdle || root.videoPlaying;
        }

        function toggle(): void {
            RuntimeState.inhibitIdle = !RuntimeState.inhibitIdle;
        }

        function enable(): void {
            RuntimeState.inhibitIdle = true;
        }

        function disable(): void {
            RuntimeState.inhibitIdle = false;
        }

        target: "idleInhibitor"
    }
}
