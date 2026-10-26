// M3 list item: one, two or three lines (56/72/88), a leading icon, avatar, image or custom item, and trailing
// text or a custom item. `selected` paints secondaryContainer; `highlighted` shows the 12 % focus layer (for the
// keyboard's current row of a ListView). Long text elides; the height never changes. Right click or long press
// emits `contextRequested(x, y)` for a context menu.
import QtQuick
import WysunM3

Rectangle {
    id: root

    property string headline
    property string supporting
    property string overline
    property int lines: supporting !== "" || overline !== "" ? 2 : 1
    property string leadingIcon
    property url leadingImage
    property string leadingAvatar             // initials (or a short label) in a 40 px circle
    property Component leading
    property string trailingText
    property Component trailing
    property bool selected
    property bool highlighted
    property bool disabled
    property bool divider
    readonly property color headlineColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : selected ? Theme.m3onSecondaryContainer : Theme.m3onSurface
    readonly property color supportingColor: disabled ? Qt.alpha(Theme.m3onSurface, Metrics.disabledContent) : selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
    readonly property bool headlineTruncated: headlineText.truncated
    readonly property alias stateLayer: layer

    signal clicked(var mouse)
    signal doubleClicked(var mouse)
    signal contextRequested(real x, real y)
    signal pressAndHold

    implicitWidth: Metrics.textFieldMinWidth
    implicitHeight: lines >= 3 ? Metrics.listItemThreeLine : lines === 2 ? Metrics.listItemTwoLine : Metrics.listItemOneLine
    height: implicitHeight
    color: selected ? Theme.m3secondaryContainer : "transparent"

    Behavior on color {
        CAnim {
            kind: "fastEffects"
        }
    }

    Row {
        id: row

        x: Theme.padding.large ?? 0
        width: parent.width - 2 * x
        height: parent.height
        spacing: Theme.spacing.large ?? 0

        Item {
            id: lead

            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: root.lines >= 3 ? -(parent.height - height) / 2 + (Theme.padding.medium ?? 0) : 0
            visible: root.leading !== null || root.leadingIcon !== "" || root.leadingAvatar !== "" || root.leadingImage.toString() !== ""
            width: root.leadingImage.toString() !== "" ? Metrics.listImageSize : root.leadingAvatar !== "" ? Metrics.listAvatarSize : root.leading ? leadLoader.width : Metrics.iconSize
            height: root.leadingImage.toString() !== "" ? Metrics.listImageSize : root.leadingAvatar !== "" ? Metrics.listAvatarSize : root.leading ? leadLoader.height : Metrics.iconSize

            Icon {
                anchors.centerIn: parent
                visible: root.leadingIcon !== "" && root.leading === null && root.leadingAvatar === ""
                name: root.leadingIcon
                filled: root.selected
                color: root.selected ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
            }

            Rectangle {
                anchors.fill: parent
                visible: root.leadingAvatar !== "" && root.leading === null
                radius: Theme.fullRadius(height)
                color: Theme.m3primaryContainer

                Label {
                    anchors.centerIn: parent
                    role: "title.medium"
                    text: root.leadingAvatar
                    color: Theme.m3onPrimaryContainer
                }
            }

            Image {
                anchors.fill: parent
                visible: root.leadingImage.toString() !== "" && root.leading === null
                source: root.leadingImage
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: width * 2
                sourceSize.height: height * 2
            }

            Loader {
                id: leadLoader

                anchors.centerIn: parent
                active: root.leading !== null
                sourceComponent: root.leading
            }
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - (lead.visible ? lead.width + parent.spacing : 0) - (tail.visible ? tail.width + parent.spacing : 0)

            Label {
                width: parent.width
                visible: root.overline !== ""
                role: "label.small"
                text: root.overline
                color: root.supportingColor
                elide: Text.ElideRight
            }
            Label {
                id: headlineText

                width: parent.width
                role: "body.large"
                text: root.headline
                color: root.headlineColor
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            Label {
                width: parent.width
                visible: root.supporting !== ""
                role: "body.medium"
                text: root.supporting
                color: root.supportingColor
                elide: Text.ElideRight
                wrapMode: root.lines >= 3 ? Text.Wrap : Text.NoWrap
                maximumLineCount: root.lines >= 3 ? 2 : 1
            }
        }

        Item {
            id: tail

            anchors.verticalCenter: parent.verticalCenter
            visible: root.trailing !== null || root.trailingText !== ""
            width: root.trailing ? tailLoader.width : tailText.implicitWidth
            height: root.trailing ? tailLoader.height : tailText.implicitHeight

            Label {
                id: tailText

                visible: root.trailing === null
                role: "label.small"
                text: root.trailingText
                color: root.supportingColor
            }
            Loader {
                id: tailLoader

                active: root.trailing !== null
                sourceComponent: root.trailing
            }
        }
    }

    Divider {
        visible: root.divider
        anchors.bottom: parent.bottom
        width: parent.width
    }

    StateLayer {
        id: layer

        tint: root.headlineColor
        disabled: root.disabled
        focused: root.highlighted
        mouseArea.acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton)
                root.contextRequested(mouse.x, mouse.y);
            else
                root.clicked(mouse);
        }
        onPressAndHold: mouse => {
            root.pressAndHold();
            root.contextRequested(mouse.x, mouse.y);
        }
    }

    Connections {
        target: layer.mouseArea

        function onDoubleClicked(mouse) {
            if (mouse.button === Qt.LeftButton)
                root.doubleClicked(mouse);
        }
    }
}
