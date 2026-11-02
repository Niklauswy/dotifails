// The expanded preview (F-53, files-details.html «Vista ampliada»): the whole window for the selected file; zoom
// with the wheel or + / − / 0, drag to move, double click resets; ← / → walk the files of the same kind in the
// folder; F makes a video full screen; Escape goes back. It swallows every click under it.
import QtQuick
import QtMultimedia
import WysunM3

FocusScope {
    id: root

    property var player
    property bool open
    property alias pane: pane
    readonly property real zoom: pane.zoom
    signal closeRequested
    signal stepRequested(int delta)
    signal fullScreenRequested
    signal linkActivated(string target)

    objectName: "expandedPreview"
    visible: opacity > 0
    opacity: open ? 1 : 0
    enabled: open

    Behavior on opacity {
        Anim {
            kind: "defaultEffects"
        }
    }

    Keys.onPressed: event => {
        switch (event.key) {
        case Qt.Key_Escape:
        case Qt.Key_Space:
            root.closeRequested();
            break;
        case Qt.Key_Left:
            root.stepRequested(-1);
            break;
        case Qt.Key_Right:
            root.stepRequested(1);
            break;
        case Qt.Key_Plus:
        case Qt.Key_Equal:
            pane.zoomBy(1.25);
            break;
        case Qt.Key_Minus:
            pane.zoomBy(0.8);
            break;
        case Qt.Key_0:
            pane.resetZoom();
            break;
        case Qt.Key_F:
            if (preview.kind === "video")
                root.fullScreenRequested();
            break;
        default:
            return;
        }
        event.accepted = true;
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.m3surface

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            onWheel: wheel => wheel.accepted = true
        }
    }

    Item {
        id: bar

        width: parent.width
        height: Metrics.topAppBarSmall

        Row {
            x: Theme.padding.small ?? 0
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.small ?? 0

            IconButton {
                objectName: "expandedClose"
                type: "tonal"
                icon: "close"
                onClicked: root.closeRequested()

                Tooltip {
                    text: "Volver · Esc"
                }
            }
            Label {
                anchors.verticalCenter: parent.verticalCenter
                role: "title.medium"
                text: preview.name
                color: Theme.m3onSurface
                elide: Text.ElideMiddle
                width: Math.min(implicitWidth, root.width / 2)
            }
        }
        Row {
            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.small ?? 0
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.extraSmall ?? 0

            IconButton {
                visible: pane.picture
                icon: "zoom_out"
                onClicked: pane.zoomBy(0.8)
            }
            Label {
                visible: pane.picture
                anchors.verticalCenter: parent.verticalCenter
                role: "label.large"
                text: Math.round(pane.zoom * 100) + " %"
                color: Theme.m3onSurface
            }
            IconButton {
                visible: pane.picture
                icon: "zoom_in"
                onClicked: pane.zoomBy(1.25)
            }
            IconButton {
                icon: "chevron_left"
                onClicked: root.stepRequested(-1)

                Tooltip {
                    text: "Anterior · ←"
                }
            }
            IconButton {
                icon: "chevron_right"
                onClicked: root.stepRequested(1)

                Tooltip {
                    text: "Siguiente · →"
                }
            }
            IconButton {
                visible: preview.kind === "video"
                icon: "fullscreen"
                onClicked: root.fullScreenRequested()

                Tooltip {
                    text: "Pantalla completa · F"
                }
            }
        }
    }

    PreviewPane {
        id: pane

        anchors.top: bar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.padding.large ?? 0
        zoomable: true
        player: root.player
        onLinkActivated: target => root.linkActivated(target)
    }
}
