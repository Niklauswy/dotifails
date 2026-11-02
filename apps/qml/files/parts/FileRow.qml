// One file in the list: icon, name, and the Modificado / Tamaño / Tipo columns (narrow lists keep the size only).
import QtQuick
import WysunM3

Item {
    id: root

    required property int index
    required property var model
    property var view
    property bool current
    property bool wide: true
    readonly property bool selected: model.selected
    readonly property bool entering: view ? view.entering && index < FilesMetrics.entranceRows : false

    height: FilesMetrics.rowHeight
    opacity: model.cut ? 0.45 : 1

    Item {
        id: body

        width: parent.width
        height: parent.height

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 1
            anchors.bottomMargin: 1
            radius: Theme.rounding.medium ?? 0
            color: root.selected ? Theme.m3secondaryContainer : "transparent"

            Behavior on color {
                CAnim {
                    kind: "fastEffects"
                }
            }
        }
        StateLayer {
            id: layer

            anchors.fill: parent
            radius: Theme.rounding.medium ?? 0
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

        Row {
            anchors.fill: parent
            anchors.leftMargin: Theme.padding.medium ?? 0
            anchors.rightMargin: Theme.padding.medium ?? 0
            spacing: Theme.spacing.medium ?? 0

            FileIcon {
                anchors.verticalCenter: parent.verticalCenter
                width: FilesMetrics.rowIcon
                height: FilesMetrics.rowIcon
                compact: true
                kind: root.model.kind
                icon: root.model.icon
                glyph: root.model.glyph
                badge: root.model.badge
                role: root.model.role
                thumb: root.model.thumb
            }
            Label {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - x - (root.wide ? FilesMetrics.dateColumn + FilesMetrics.typeColumn + 2 * parent.spacing : 0) - FilesMetrics.sizeColumn - parent.spacing
                role: "body.large"
                text: root.model.name
                color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                elide: Text.ElideMiddle
            }
            Label {
                visible: root.wide
                anchors.verticalCenter: parent.verticalCenter
                width: FilesMetrics.dateColumn
                role: "body.medium"
                text: root.model.modifiedText
                color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                elide: Text.ElideRight
            }
            Label {
                anchors.verticalCenter: parent.verticalCenter
                width: FilesMetrics.sizeColumn
                role: "body.medium"
                text: root.model.isDir ? "—" : root.model.sizeText
                color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                elide: Text.ElideRight
            }
            Label {
                visible: root.wide
                anchors.verticalCenter: parent.verticalCenter
                width: FilesMetrics.typeColumn
                role: "body.medium"
                text: root.model.label
                color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                elide: Text.ElideRight
            }
        }
    }

    // What a drag towards another app carries: the selection as file:// URLs.
    Item {
        id: dragProxy

        width: 1
        height: 1
        Drag.dragType: Drag.Automatic
        Drag.supportedActions: Qt.CopyAction
        Drag.mimeData: ({
                "text/uri-list": root.view && !root.view.chooser ? fileOps.uris(root.selected ? root.view.model.selectedPaths : [root.model.path]).join("\r\n") : ""
            })
        Drag.active: layer.mouseArea.drag.active
    }

    states: State {
        when: root.entering
        PropertyChanges {
            body.opacity: 0
            body.y: FilesMetrics.entranceRise
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
                    property: "y"
                    kind: "defaultSpatial"
                }
            }
        }
    }
}
