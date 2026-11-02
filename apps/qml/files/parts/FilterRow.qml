// Filter by name (Ctrl+F, or typing in the view) and by kind (F-24): a pill field that widens while focused and
// the type chips, which keep folders visible. Escape empties the field, then hands focus back to the files.
import QtQuick
import WysunM3

Item {
    id: root

    property var model                      // FolderModel
    property bool chooser                   // the file chooser keeps «Carpetas» out (its filters are the portal's)
    readonly property alias input: field
    readonly property bool focused: field.activeFocus
    signal leave

    function begin(text) {
        field.forceActiveFocus();
        if (text !== undefined && text !== "") {
            field.text = field.text + text;
            field.cursorPosition = field.text.length;
        }
    }

    implicitHeight: box.height + (Theme.spacing.small ?? 0) + chips.height

    Rectangle {
        id: box

        objectName: "filterField"
        width: Math.min(root.width, root.focused || field.text !== "" ? FilesMetrics.filterWideWidth : FilesMetrics.filterWidth)
        height: Metrics.buttonHeight
        radius: height / 2
        color: Theme.m3surfaceContainerHigh
        border.width: root.focused ? Metrics.textFieldFocusWidth : 0
        border.color: Theme.m3primary

        SpringBehavior on width {
            kind: "fastSpatial"
        }

        Icon {
            id: lead

            x: Theme.padding.medium ?? 0
            anchors.verticalCenter: parent.verticalCenter
            name: "filter_list"
            size: Metrics.buttonIconSize + 2
            color: Theme.m3onSurfaceVariant
        }
        TextInput {
            id: field

            objectName: "filterInput"
            anchors.left: lead.right
            anchors.leftMargin: Theme.spacing.medium ?? 0
            anchors.right: hint.visible ? hint.left : clear.left
            anchors.rightMargin: Theme.spacing.small ?? 0
            anchors.verticalCenter: parent.verticalCenter
            font.family: Theme.typeFont("body.large").family
            font.pointSize: Math.max(1, Theme.typeFont("body.large").pointSize)
            color: Theme.m3onSurface
            selectionColor: Theme.m3primary
            selectedTextColor: Theme.m3onPrimary
            clip: true
            text: root.model ? root.model.filterText : ""
            onTextEdited: root.model.setFilterText(text)
            Keys.onEscapePressed: event => {
                if (text !== "") {
                    text = "";
                    root.model.setFilterText("");
                } else {
                    root.leave();
                }
                event.accepted = true;
            }
            Keys.onDownPressed: root.leave()
            Keys.onReturnPressed: root.leave()
            Keys.onEnterPressed: root.leave()

            Label {
                anchors.verticalCenter: parent.verticalCenter
                visible: field.text === "" && !field.activeFocus
                role: "body.large"
                text: "Filtrar"
                color: Theme.m3onSurfaceVariant
            }
        }
        Rectangle {
            id: hint

            visible: field.text === "" && !root.focused && box.width > FilesMetrics.filterWidth * 0.6
            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.small ?? 0
            anchors.verticalCenter: parent.verticalCenter
            width: hintLabel.implicitWidth + 2 * (Theme.spacing.small ?? 0)
            height: hintLabel.implicitHeight + (Theme.spacing.extraSmall ?? 0)
            radius: Theme.rounding.extraSmall ?? 0
            color: Theme.m3surfaceContainerHighest

            Label {
                id: hintLabel

                anchors.centerIn: parent
                role: "label.small"
                text: "Ctrl F"
                color: Theme.m3onSurfaceVariant
            }
        }
        IconButton {
            id: clear

            visible: field.text !== ""
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            icon: "close"
            iconSize: Metrics.buttonIconSize
            onClicked: {
                field.text = "";
                root.model.setFilterText("");
            }
        }
        MouseArea {
            anchors.fill: parent
            z: -1
            onClicked: field.forceActiveFocus()
        }
    }

    Flow {
        id: chips

        objectName: "kindChips"
        anchors.top: box.bottom
        anchors.topMargin: Theme.spacing.small ?? 0
        width: root.width
        spacing: Theme.spacing.small ?? 0

        Repeater {
            model: [{id: "all", text: "Todo"}, {id: "folders", text: "Carpetas"}, {id: "images", text: "Imágenes"}, {id: "videos", text: "Vídeos"}, {id: "audio", text: "Audio"}, {id: "documents", text: "Documentos"}, {id: "code", text: "Código"}]

            Chip {
                required property var modelData

                objectName: "chip-" + modelData.id
                kind: "filter"
                text: modelData.text
                readonly property bool active: root.model ? root.model.group === modelData.id : modelData.id === "all"

                selected: active
                // The filter chip flips `selected` by itself; the model's group stays the source of truth.
                onClicked: {
                    root.model.setGroup(active && modelData.id !== "all" ? "all" : modelData.id);
                    selected = Qt.binding(() => active);
                }
            }
        }
    }
}
