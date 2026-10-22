pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.modules.areapicker
import qs.services

// Drawing on the screen while recording: what is drawn is part of the video. Marks
// stay on screen when the tools are put away and never take clicks; with the tools
// open the output takes the pointer and the keyboard until Esc.
Scope {
    id: root

    Variants {
        model: Recorder.running ? Screens.screens : []

        StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property bool owner: Recorder.screenName === modelData.name
            readonly property rect area: Recorder.wholeOutput ? Qt.rect(0, 0, modelData.width, modelData.height) : Recorder.region
            readonly property bool open: owner && Recorder.annotating

            Tokens.screen: modelData.name
            screen: modelData
            name: "recording-annotations"
            visible: owner
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
            anchors.top: true
            anchors.bottom: true
            anchors.left: true
            anchors.right: true
            // Closed, only the marks are shown: no input at all.
            mask: open ? null : none
            color: "transparent"

            Region {
                id: none
            }

            Item {
                id: stage

                anchors.fill: parent
                focus: win.open

                Keys.onPressed: event => {
                    const ctrl = event.modifiers & Qt.ControlModifier;
                    const shift = event.modifiers & Qt.ShiftModifier;
                    if (marks.editingText)
                        return;
                    if (event.key === Qt.Key_Escape)
                        Recorder.annotating = false;
                    else if (ctrl && event.key === Qt.Key_Z)
                        shift ? marks.redo() : marks.undo();
                    else if (ctrl && event.key === Qt.Key_Y)
                        marks.redo();
                    else if (!ctrl && event.key >= Qt.Key_1 && event.key <= Qt.Key_8)
                        marks.tool = toolbar.tools[event.key - Qt.Key_1].id;
                    else
                        return;
                    event.accepted = true;
                }

                Item {
                    id: backdrop

                    anchors.fill: parent
                    visible: false
                }

                Annotations {
                    id: marks

                    anchors.fill: parent
                    source: backdrop
                    bounds: win.area
                    drawing: win.open
                    tool: "pen"
                }

                // Out of the recorded area, so the tools are not in the video.
                EditorToolbar {
                    id: toolbar

                    readonly property real gap: Tokens.sizes.screenshot.toolbarGap
                    readonly property real below: win.area.y + win.area.height + gap
                    readonly property real above: win.area.y - height - gap

                    live: true
                    annotations: marks
                    visible: win.open || opacity > 0
                    opacity: win.open ? 1 : 0
                    x: Math.max(gap, Math.min(stage.width - width - gap, win.area.x + win.area.width / 2 - width / 2))
                    y: below + height + gap <= stage.height ? below : above >= gap ? above : stage.height - height - gap
                    onCancel: Recorder.annotating = false
                    onClear: {
                        marks.marks = [];
                        marks.undone = [];
                        marks.counter = 1;
                    }

                    Behavior on opacity {
                        Anim {}
                    }
                }
            }
        }
    }
}
