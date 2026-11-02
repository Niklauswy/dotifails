pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components.containers
import qs.services

// While recording with the camera on: a solid shape in the recorded area where the camera will cover the video (the
// camera is composited afterwards, on top of it), so the person can keep what matters out from under it. Never takes
// input. Shown from the countdown, on screen recordings of a whole output too.
Scope {
    Variants {
        model: Recorder.active && Recorder.cameraActive ? Screens.screens : []

        StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property rect area: Recorder.wholeOutput ? Qt.rect(0, 0, modelData.width, modelData.height) : Recorder.region

            Tokens.screen: modelData.name
            screen: modelData
            name: "recording-camera-marker"
            visible: Recorder.screenName === modelData.name && area.width > 0
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            anchors.top: true
            anchors.bottom: true
            anchors.left: true
            anchors.right: true
            // Empty input region: clicks go to what is under the marker.
            mask: Region {}
            color: "transparent"

            CameraMarkerShape {
                area: win.area
                style: Recorder.cameraActiveStyle
            }
        }
    }
}
