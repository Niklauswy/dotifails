import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Icons.js" as Icons

Button {
    id: control
    property bool selected: false
    property string description: text
    property color foreground: Appearance.text
    property color accent: Appearance.accent
    property string glyph: ""
    property int textAlignment: Text.AlignHCenter
    property bool secondaryActionEnabled: false
    signal secondaryClicked()
    implicitHeight: 36
    implicitWidth: glyph && !text ? 36 : Math.max(36, label.implicitWidth + (glyph ? 26 : 0) + 26)
    leftPadding: glyph && !text ? 6 : 13
    rightPadding: glyph && !text ? 6 : 13
    topPadding: 0
    bottomPadding: 0
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: description
    Accessible.role: Accessible.Button
    ToolTip.visible: hovered && description !== text
    ToolTip.text: description
    ToolTip.delay: 500
    contentItem: RowLayout {
        spacing: 8
        Image {
            visible: control.glyph !== ""
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            sourceSize.width: 36
            sourceSize.height: 36
            source: control.glyph ? Icons.source(control.glyph, control.selected ? control.accent : control.foreground) : ""
        }
        Text {
            id: label
            Layout.fillWidth: true
            text: control.text
            color: control.selected ? control.accent : control.foreground
            font.family: Appearance.fontFamily
            font.pixelSize: Appearance.fontBody
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: control.textAlignment
            textFormat: Text.PlainText
        }
    }
    background: Rectangle {
        radius: Appearance.radiusControl
        color: control.down || control.selected ? Qt.alpha(control.accent, 0.16) : (control.hovered ? Appearance.hover : "transparent")
        border.width: control.activeFocus ? Appearance.focusWidth : (control.selected ? Appearance.borderWidth : 0)
        border.color: control.activeFocus ? control.accent : Qt.alpha(control.accent, 0.35)
    }
    // A right-only exclusive mouse grab avoids competing passive TapHandler
    // delivery inside AbstractButton and the bar's ancestor Flickable. Left
    // clicks and keyboard activation continue through the native Button.
    MouseArea {
        anchors.fill: parent
        enabled: control.secondaryActionEnabled
        acceptedButtons: Qt.RightButton
        preventStealing: true
        onClicked: control.secondaryClicked()
    }
}
