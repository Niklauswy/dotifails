// One file in the grid: its icon, the name on up to two lines and a detail line (size, or the folder's count).
// Selected tiles sit on secondaryContainer with a check; cut ones fade until they are pasted. The view decides
// what a click means (FolderView.press); the tile only reports it.
import QtQuick
import WysunM3

Item {
    id: root

    required property int index
    required property var model
    property var view
    property bool current
    readonly property bool selected: model.selected
    readonly property bool entering: view ? view.entering && index < FilesMetrics.entranceRows : false

    width: FilesMetrics.tileWidth
    height: FilesMetrics.tileHeight
    opacity: model.cut ? 0.45 : 1

    Item {
        id: body

        anchors.fill: parent
        anchors.margins: Theme.spacing.extraSmall ?? 0
        opacity: 1

        Rectangle {
            anchors.fill: parent
            radius: Theme.rounding.large ?? 0
            color: root.selected ? Theme.m3secondaryContainer : "transparent"
            scale: root.selected ? 1 : 0.94

            SpringBehavior on scale {
                kind: "fastSpatial"
            }
            Behavior on color {
                CAnim {
                    kind: "fastEffects"
                }
            }
        }

        StateLayer {
            id: layer

            anchors.fill: parent
            radius: Theme.rounding.large ?? 0
            tint: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurface
            focused: root.current && (root.view?.activeFocus ?? false)
            mouseArea.acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
            // Dragging files out to other apps (F-33); the chooser does not drag.
            mouseArea.drag.target: root.view && !root.view.chooser ? dragProxy : null
            mouseArea.onPressed: mouse => root.view.press(root.index, mouse.button, mouse.modifiers)
            mouseArea.onDoubleClicked: mouse => {
                if (mouse.button === Qt.LeftButton)
                    root.view.activate(root.index);
            }
            mouseArea.onClicked: mouse => {
                if (mouse.button === Qt.RightButton) {
                    const point = mapToItem(null, mouse.x, mouse.y);
                    root.view.contextAt(root.index, point.x, point.y);
                }
            }
        }

        Rectangle {
            visible: root.selected
            x: Theme.spacing.small ?? 0
            y: Theme.spacing.small ?? 0
            z: 2
            width: Metrics.chipIconSize + 2
            height: width
            radius: width / 2
            color: Theme.m3primary

            Icon {
                anchors.centerIn: parent
                name: "check"
                size: Metrics.chipIconSize - 4
                color: Theme.m3onPrimary
            }
        }

        FileIcon {
            id: icon

            anchors.horizontalCenter: parent.horizontalCenter
            y: Theme.spacing.medium ?? 0
            width: FilesMetrics.tileIcon
            height: FilesMetrics.tileIcon
            kind: root.model.kind
            icon: root.model.icon
            glyph: root.model.glyph
            badge: root.model.badge
            role: root.model.role
            thumb: root.model.thumb
            duration: root.model.duration
            snippet: root.model.snippet
            scale: layer.pressed ? 0.94 : 1

            SpringBehavior on scale {
                kind: "fastSpatial"
            }
        }

        Label {
            id: name

            anchors.top: icon.bottom
            anchors.topMargin: Theme.spacing.small ?? 0
            x: Theme.spacing.extraSmall ?? 0
            width: parent.width - 2 * x
            role: "label.large"
            text: root.model.name
            color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurface
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            maximumLineCount: 2
            elide: Text.ElideMiddle
        }
        Label {
            anchors.top: name.bottom
            x: name.x
            width: name.width
            role: "label.small"
            text: root.model.detail
            color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            visible: name.lineCount < 2
        }
    }

    // The staggered entrance of a folder that opens (none with reduced motion).
    // What a drag towards another app carries: the selection as file:// URLs.
    Item {
        id: dragProxy

        width: 1
        height: 1
        Drag.dragType: Drag.Automatic
        Drag.supportedActions: Qt.CopyAction
        Drag.mimeData: ({
                "text/uri-list": fileOps.uris(root.view && root.selected ? root.view.model.selectedPaths : [root.model.path]).join("\r\n")
            })
        Drag.active: layer.mouseArea.drag.active
    }

    states: State {
        when: root.entering
        PropertyChanges {
            body.opacity: 0
            body.anchors.topMargin: (Theme.spacing.extraSmall ?? 0) + FilesMetrics.entranceRise
        }
    }
    transitions: Transition {
        from: "*"
        to: ""
        SequentialAnimation {
            PauseAnimation {
                duration: Motion.reduced ? 0 : Math.max(0, root.index) * FilesMetrics.entranceStep
            }
            ParallelAnimation {
                Anim {
                    target: body
                    property: "opacity"
                    kind: "defaultEffects"
                }
                Anim {
                    target: body
                    property: "anchors.topMargin"
                    kind: "defaultSpatial"
                }
            }
        }
    }
}
