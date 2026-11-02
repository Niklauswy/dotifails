pragma ComponentBehavior: Bound

import QtQuick
import QtMultimedia
import Quickshell.Widgets
import Wysun.Config
import "../../utils/CameraBubble.js" as Bubble
import qs.components
import qs.services

// The live camera as it will look in the recording: the bubble of the chosen shape and size, in the chosen corner of
// the selected area. Drag it and it jumps to the nearest corner when let go (the renderer only knows four). It is shown
// before recording starts only: once it does, the camera belongs to the recorder's worker, and a bubble drawn on the
// screen would be captured twice. `live: false` releases the camera.
Item {
    id: root

    // The selected area, in the coordinates of this item's parent.
    required property rect area
    property bool live: true

    readonly property var style: Recorder.cameraStyle
    readonly property var bubble: Bubble.rect(area.width, area.height, style)
    readonly property string device: Recorder.cameraDevice || (Recorder.cameras.length > 0 ? Recorder.cameras[0].id : "")
    property string failure

    property bool dragging
    property real dragX
    property real dragY
    property point grabOffset
    readonly property string target: Bubble.nearestCorner(dragX + width / 2, dragY + height / 2, area.width, area.height)

    function beginDrag(px: real, py: real): void {
        grabOffset = Qt.point(px - x, py - y);
        dragX = x - area.x;
        dragY = y - area.y;
        dragging = true;
    }

    function moveDrag(px: real, py: real): void {
        if (!dragging)
            return;
        dragX = Math.max(0, Math.min(area.width - width, px - grabOffset.x - area.x));
        dragY = Math.max(0, Math.min(area.height - height, py - grabOffset.y - area.y));
    }

    function endDrag(): void {
        if (!dragging)
            return;
        const corner = target;
        dragging = false;
        if (corner !== (style.corner ?? "bottom-right"))
            Recorder.setPref("camera_corner", corner);
    }

    x: area.x + (dragging ? dragX : bubble.x)
    y: area.y + (dragging ? dragY : bubble.y)
    width: bubble.width
    height: bubble.height

    // Where it will land while it is being dragged.
    Repeater {
        model: root.dragging ? Bubble.corners() : []

        Rectangle {
            id: slot

            required property string modelData
            readonly property var spot: Bubble.rect(root.area.width, root.area.height, Object.assign({}, root.style, { corner: modelData }))

            x: root.area.x + spot.x - root.x
            y: root.area.y + spot.y - root.y
            width: spot.width
            height: spot.height
            radius: spot.radius
            color: "transparent"
            border.width: slot.modelData === root.target ? 3 : 1
            border.color: Qt.alpha(Colours.palette.m3primary, slot.modelData === root.target ? 1 : 0.5)
        }
    }

    ClippingRectangle {
        anchors.fill: parent
        radius: root.bubble.radius
        color: Colours.palette.m3surfaceContainerHighest
        border.width: 2
        border.color: Colours.palette.m3primary

        Loader {
            anchors.fill: parent
            active: root.live && root.visible && root.device !== ""
            sourceComponent: Item {
                MediaDevices {
                    id: devices
                }

                CaptureSession {
                    camera: Camera {
                        active: true
                        cameraDevice: devices.videoInputs.find(d => String(d.id) === root.device) ?? devices.defaultVideoInput
                        onErrorOccurred: (error, errorString) => {
                            root.failure = errorString;
                            console.warn("Camera preview:", errorString);
                        }
                    }
                    videoOutput: output
                }

                VideoOutput {
                    id: output

                    anchors.fill: parent
                    fillMode: VideoOutput.PreserveAspectCrop
                }
            }
        }

        // No camera, or it could not start: the shape stays, with a crossed-out camera.
        MaterialIcon {
            anchors.centerIn: parent
            visible: root.failure !== "" || root.device === ""
            text: "videocam_off"
            color: Colours.palette.m3onSurfaceVariant
            fontStyle: Tokens.font.icon.large
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.live
        cursorShape: root.dragging ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        preventStealing: true
        onPressed: mouse => {
            const p = mapToItem(root.parent, mouse.x, mouse.y);
            root.beginDrag(p.x, p.y);
        }
        onPositionChanged: mouse => {
            if (!pressed)
                return;
            const p = mapToItem(root.parent, mouse.x, mouse.y);
            root.moveDrag(p.x, p.y);
        }
        onReleased: root.endDrag()
    }
}
