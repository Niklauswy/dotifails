pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Connected button group (M3 Expressive): the chosen rhythm fills with primary, rounds fully and widens.
Item {
    id: root

    property int current: 25
    property bool keyFocus
    readonly property var options: [{value: 25, text: "25 / 5", hint: "clásico"}, {value: 50, text: "50 / 10", hint: "largo"},
        {value: 90, text: "90 / 20", hint: "profundo"}]
    readonly property real gap: 2
    readonly property real share: (width - gap * (options.length - 1)) / (options.length + 0.25)

    signal picked(int value)

    implicitHeight: Tokens.padding.extraExtraLarge

    FocusRing {
        on: root.keyFocus
        radius: root.height / 2 + gap
    }

    Row {
        anchors.fill: parent
        spacing: root.gap

        Repeater {
            model: root.options

            StyledRect {
                id: button

                required property var modelData
                required property int index
                readonly property bool selected: root.current === modelData.value
                readonly property real outer: height / 2
                readonly property real inner: mouse.pressed ? Tokens.rounding.medium : Tokens.rounding.small

                width: root.share * (selected ? 1.25 : 1)
                height: root.height
                color: selected ? Colours.palette.m3primary : Colours.palette.m3surfaceContainerHighest
                topLeftRadius: selected || index === 0 ? outer : inner
                bottomLeftRadius: topLeftRadius
                topRightRadius: selected || index === root.options.length - 1 ? outer : inner
                bottomRightRadius: topRightRadius

                Behavior on width {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
                Behavior on topLeftRadius {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
                Behavior on topRightRadius {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }

                Column {
                    anchors.centerIn: parent

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: button.modelData.text
                        color: button.selected ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
                        font: Tokens.font.label.large
                    }

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: button.modelData.hint
                        color: button.selected ? Colours.palette.m3onPrimary : Colours.palette.m3onSurfaceVariant
                        opacity: 0.8
                        font: Tokens.font.label.small
                    }
                }

                MouseArea {
                    id: mouse

                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(button.modelData.value)
                }
            }
        }
    }
}
