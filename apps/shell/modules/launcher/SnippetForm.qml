pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// Create or edit a snippet inside the launcher (pushed view).
Item {
    id: root

    property int snippetId: -1
    property alias title: nameField.text
    property alias shortcut: shortcutField.text
    property alias body: bodyField.text
    readonly property bool valid: nameField.text.trim() !== "" && bodyField.text.trim() !== ""

    signal submit
    signal cancel

    function load(row: var): void {
        snippetId = row ? row.id : -1;
        nameField.text = row ? row.title : "";
        shortcutField.text = row ? row.shortcut : "";
        bodyField.text = row ? row.body : "";
        nameField.forceActiveFocus();
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium

        StyledTextField {
            id: nameField

            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            placeholderText: "Name"
            KeyNavigation.tab: shortcutField
            Keys.onEscapePressed: root.cancel()
            Keys.onReturnPressed: shortcutField.forceActiveFocus()
        }
        StyledTextField {
            id: shortcutField

            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            placeholderText: "Abbreviation (optional)"
            KeyNavigation.tab: bodyField
            KeyNavigation.backtab: nameField
            Keys.onEscapePressed: root.cancel()
            Keys.onReturnPressed: bodyField.forceActiveFocus()
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            TextArea {
                id: bodyField

                placeholderText: "Your text… Variables: {date}, {time}, {datetime}"
                wrapMode: TextEdit.Wrap
                color: Colours.palette.m3onSurface
                placeholderTextColor: Colours.palette.m3onSurfaceVariant
                selectionColor: Colours.palette.m3primaryContainer
                font: Tokens.font.body.medium
                background: Rectangle {
                    color: Colours.tPalette.m3surfaceContainerHigh
                    radius: Tokens.rounding.medium
                }
                Keys.onEscapePressed: root.cancel()
                KeyNavigation.backtab: shortcutField
                Keys.onPressed: event => {
                    if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && root.valid) {
                        root.submit();
                        event.accepted = true;
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            StyledText {
                Layout.fillWidth: true
                text: "Ctrl ↵ to save · Esc to cancel"
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }
            TextButton {
                text: "Save Snippet"
                disabled: !root.valid
                onClicked: root.submit()
            }
        }
    }
}
