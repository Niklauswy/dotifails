import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.effects
import qs.components.controls
import qs.services

// Text read from the selection, editable before it is copied.
StyledRect {
    id: root

    property string text
    property bool running

    signal copy(text: string)
    signal cancel

    function focusText(): void {
        area.forceActiveFocus();
    }

    implicitWidth: Tokens.sizes.screenshot.ocrWidth
    implicitHeight: Tokens.sizes.screenshot.ocrHeight
    radius: Tokens.rounding.large
    color: Colours.palette.m3surfaceContainer
    border.width: 1
    border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

    onTextChanged: area.text = text

    Elevation {
        anchors.fill: parent
        radius: root.radius
        level: 3
        z: -1
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: "text_fields"
                color: Colours.palette.m3primary
                fontStyle: Tokens.font.icon.medium
            }

            StyledText {
                Layout.fillWidth: true
                text: root.running ? Tr.tr("Reading text…") : root.text ? Tr.tr("Text in the selection") : Tr.tr("No text found")
                font: Tokens.font.title.small
            }

            IconButton {
                icon: "close"
                type: IconButton.Text
                onClicked: root.cancel()
            }
        }

        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Tokens.rounding.medium
            color: Colours.palette.m3surfaceContainerHigh

            ScrollView {
                anchors.fill: parent
                anchors.margins: Tokens.padding.small

                TextArea {
                    id: area

                    readOnly: root.running
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    color: Colours.palette.m3onSurface
                    selectionColor: Colours.palette.m3primaryContainer
                    selectedTextColor: Colours.palette.m3onPrimaryContainer
                    font: Tokens.font.mono.medium
                    background: null

                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Escape) {
                            root.cancel();
                            event.accepted = true;
                        } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && event.modifiers & Qt.ControlModifier) {
                            root.copy(area.selectedText || area.text);
                            event.accepted = true;
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            StyledText {
                Layout.fillWidth: true
                text: Tr.tr("Edit it if needed · Ctrl+Enter copies")
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
                elide: Text.ElideRight
            }

            TextButton {
                text: area.selectedText ? Tr.tr("Copy selection") : Tr.tr("Copy text")
                disabled: root.running || !area.text
                onClicked: root.copy(area.selectedText || area.text)
            }
        }
    }
}
