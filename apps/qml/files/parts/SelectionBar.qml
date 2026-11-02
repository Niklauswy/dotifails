// The floating bar of a multiple selection (F-29): clear, count, open, copy, cut, rename (one file), trash and
// more. It rises over the top of the folder while two or more files are selected.
import QtQuick
import WysunM3

Surface {
    id: root

    property int count
    property bool chooser
    readonly property bool shown: count > 1
    signal action(string id)
    signal moreRequested(real x, real y)

    objectName: "selectionBar"
    implicitHeight: Metrics.topAppBarSmall
    radius: Theme.rounding.extraLarge ?? 0
    container: Theme.m3surfaceContainerHigh
    color: container
    level: 3
    opacity: shown ? 1 : 0
    visible: opacity > 0
    scale: shown ? 1 : 0.92

    Behavior on opacity {
        Anim {
            kind: "fastEffects"
        }
    }
    SpringBehavior on scale {
        kind: "fastSpatial"
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.padding.small ?? 0
        anchors.rightMargin: Theme.padding.small ?? 0
        spacing: Theme.spacing.small ?? 0

        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            icon: "close"
            onClicked: root.action("clear")

            Tooltip {
                text: "Quitar la selección · Esc"
            }
        }
        Label {
            objectName: "selectionCount"
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - actions.width - parent.spacing
            role: "title.medium"
            text: root.count + " seleccionados"
            color: Theme.m3onSurface
            elide: Text.ElideRight
        }
        Row {
            id: actions

            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.extraSmall ?? 0

            Repeater {
                model: root.chooser ? [] : [{id: "open", icon: "open_in_new", tip: "Abrir · Enter"}, {id: "copy", icon: "content_copy", tip: "Copiar · Ctrl+C"}, {id: "cut", icon: "content_cut", tip: "Cortar · Ctrl+X"}, {id: "trash", icon: "delete", tip: "Enviar a la papelera · Supr"}]

                IconButton {
                    required property var modelData

                    objectName: "selection-" + modelData.id
                    icon: modelData.icon
                    onClicked: root.action(modelData.id)

                    Tooltip {
                        text: parent.modelData.tip
                    }
                }
            }
            IconButton {
                id: more

                visible: !root.chooser
                icon: "more_vert"
                onClicked: {
                    const point = more.mapToItem(null, 0, more.height);
                    root.moreRequested(point.x, point.y);
                }

                Tooltip {
                    text: "Más acciones · Alt+K"
                }
            }
        }
    }
}
