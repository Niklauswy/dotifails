pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import M3Shapes
import Wysun.Config
import qs.components
import qs.services
import qs.modules.launcher.services
import "services/Translate.js" as Translate

// The ";" translator: a badge that morphs while the answer is on its way, the language pair as
// chips, and the translation rising into place. The live state is Translator's; this row only
// asks for it (LauncherPanel.syncTranslation).
Item {
    id: root

    required property var modelData
    required property real scale

    // A language chip was clicked: the panel rewrites the query as ";code text".
    signal picked(string code)

    readonly property bool loading: Translator.busy
    readonly property bool failed: Translator.state === "error"
    readonly property bool ready: Translator.state === "done"
    // Something to show even while a newer answer is being fetched: the old one dims instead of vanishing.
    readonly property bool hasText: Translator.result.length > 0 && !failed
    readonly property string sourceName: Translator.from ? Translate.languageName(Translator.from) : (loading ? "Detecting" : "Auto")
    readonly property string targetName: Translate.languageName(Translator.target || modelData.target)
    readonly property real pad: Tokens.padding.large

    // The pieces inside animate their own height; the card just follows them.
    implicitHeight: body.implicitHeight + Tokens.padding.large * 2

    // The result lands: rise, fade, a wash across the card, a pop of the badge and a nudge of the arrow.
    onReadyChanged: {
        if (ready)
            reveal.restart();
    }

    // The badge spins while waiting and eases back to rest on the nearest turn.
    onLoadingChanged: {
        if (loading) {
            settle.stop();
            spin.restart();
            return;
        }
        spin.stop();
        settle.to = badge.turn > 180 ? 360 : 0;
        settle.restart();
    }

    Rectangle {
        id: card

        anchors.fill: parent
        anchors.topMargin: Tokens.padding.extraSmall
        anchors.bottomMargin: Tokens.padding.extraSmall
        radius: Tokens.rounding.large
        color: root.failed ? Colours.palette.m3errorContainer : Colours.palette.m3tertiaryContainer

        Behavior on color {
            CAnim {}
        }

        // A soft wash that sweeps across the card each time a translation arrives.
        ClipRect {
            anchors.fill: parent
            radius: card.radius

            Rectangle {
                id: sweep

                y: 0
                width: parent.width * 0.45
                height: parent.height
                x: -width
                rotation: 0
                opacity: 0
                gradient: Gradient {
                    orientation: Gradient.Horizontal

                    GradientStop {
                        position: 0
                        color: "transparent"
                    }
                    GradientStop {
                        position: 0.5
                        color: Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.14)
                    }
                    GradientStop {
                        position: 1
                        color: "transparent"
                    }
                }
            }
        }

        Column {
            id: body

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: root.pad
            anchors.topMargin: root.pad - Tokens.padding.extraSmall
            spacing: Tokens.spacing.medium

            // Header: badge, language pair, copy hint.
            Item {
                width: parent.width
                height: 34 * root.scale

                MaterialShape {
                    id: badge

                    readonly property var forms: [MaterialShape.Cookie9Sided, MaterialShape.SoftBurst, MaterialShape.Sunny, MaterialShape.Cookie12Sided, MaterialShape.Pentagon]
                    property int form
                    property real turn

                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    implicitSize: parent.height
                    shape: root.failed ? MaterialShape.Gem : root.loading ? forms[form % forms.length] : MaterialShape.Cookie9Sided
                    color: root.failed ? Colours.palette.m3error : Colours.palette.m3tertiary
                    animationEasing: Tokens.anim.expressiveFastSpatial
                    animationDuration: Tokens.anim.durations.expressiveDefaultSpatial
                    rotation: turn

                    Behavior on color {
                        CAnim {}
                    }

                    Timer {
                        interval: 560
                        repeat: true
                        running: root.loading
                        onTriggered: badge.form++
                    }

                    NumberAnimation {
                        id: spin

                        target: badge
                        property: "turn"
                        from: 0
                        to: 360
                        duration: 2600
                        loops: Animation.Infinite
                    }

                    Anim {
                        id: settle

                        target: badge
                        property: "turn"
                        type: Anim.DefaultSpatial
                    }

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: root.failed ? "wifi_off" : "translate"
                        fill: 1
                        color: root.failed ? Colours.palette.m3onError : Colours.palette.m3onTertiary
                        rotation: -badge.rotation
                        fontStyle: Tokens.font.icon.builders.small.scale(root.scale).build()
                    }
                }

                RowLayout {
                    anchors.left: badge.right
                    anchors.leftMargin: Tokens.spacing.medium
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Tokens.spacing.small

                    Chip {
                        text: root.sourceName
                        pulsing: root.loading && !Translator.from
                    }

                    MaterialIcon {
                        id: arrow

                        Layout.alignment: Qt.AlignVCenter
                        text: "arrow_forward"
                        color: Colours.palette.m3onTertiaryContainer
                        opacity: 0.7
                        fontStyle: Tokens.font.icon.builders.small.scale(root.scale).build()

                        transform: Translate {
                            id: arrowShift
                        }
                    }

                    Chip {
                        text: root.targetName
                        accent: true
                    }
                }

                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Tokens.spacing.small
                    opacity: root.ready ? 1 : 0
                    visible: opacity > 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.FastEffects
                        }
                    }

                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Copy"
                        font: Tokens.font.body.builders.small.size(9 * root.scale).weight(Font.Medium).build()
                        color: Colours.palette.m3onTertiaryContainer
                    }
                    Keycaps {
                        anchors.verticalCenter: parent.verticalCenter
                        keys: ["↵"]
                    }
                }
            }

            // Answer: skeleton while nothing is there yet, the text afterwards.
            Item {
                id: answer

                width: parent.width
                implicitHeight: root.hasText ? text.implicitHeight : root.failed ? fault.implicitHeight : skeleton.height
                height: implicitHeight

                Behavior on implicitHeight {
                    Anim {
                        type: Anim.DefaultSpatial
                    }
                }

                Column {
                    id: skeleton

                    width: parent.width
                    spacing: Tokens.spacing.small
                    opacity: root.loading && !root.hasText ? 1 : 0
                    visible: opacity > 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.FastEffects
                        }
                    }

                    Repeater {
                        model: [1, 0.62]

                        ClipRect {
                            id: bar

                            required property real modelData

                            width: skeleton.width * modelData
                            height: 14 * root.scale
                            radius: height / 2
                            color: Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.12)

                            Rectangle {
                                id: glint

                                width: bar.width * 0.5
                                height: bar.height
                                radius: bar.radius
                                color: Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.16)

                                SequentialAnimation on x {
                                    running: skeleton.visible
                                    loops: Animation.Infinite

                                    NumberAnimation {
                                        from: -glint.width
                                        to: bar.width
                                        duration: 1100
                                        easing.type: Easing.InOutSine
                                    }
                                    PauseAnimation {
                                        duration: 260
                                    }
                                }
                            }
                        }
                    }
                }

                StyledText {
                    id: text

                    width: parent.width
                    text: Translator.result
                    visible: root.hasText
                    wrapMode: Text.WordWrap
                    maximumLineCount: 5
                    elide: Text.ElideRight
                    font: Tokens.font.title.large
                    color: Colours.palette.m3onTertiaryContainer
                    // A newer answer is on its way: keep the old one, quieter.
                    opacity: root.loading ? 0.4 : 1
                    transformOrigin: Item.TopLeft

                    Behavior on opacity {
                        Anim {
                            type: Anim.FastEffects
                        }
                    }

                    transform: Translate {
                        id: rise
                    }

                    ParallelAnimation {
                        id: reveal

                        Anim {
                            target: text
                            property: "opacity"
                            from: 0
                            to: 1
                            type: Anim.DefaultEffects
                        }
                        Anim {
                            target: rise
                            property: "y"
                            from: 12 * root.scale
                            to: 0
                            type: Anim.DefaultSpatial
                        }
                        Anim {
                            target: sweep
                            property: "x"
                            from: -sweep.width
                            to: card.width
                            duration: 720
                            easing.type: Easing.OutCubic
                        }
                        SequentialAnimation {
                            Anim {
                                target: badge
                                property: "scale"
                                to: 1.14
                                type: Anim.FastSpatial
                            }
                            Anim {
                                target: badge
                                property: "scale"
                                to: 1
                                type: Anim.DefaultSpatial
                            }
                        }
                        SequentialAnimation {
                            Anim {
                                target: arrowShift
                                property: "x"
                                to: 7 * root.scale
                                type: Anim.FastSpatial
                            }
                            Anim {
                                target: arrowShift
                                property: "x"
                                to: 0
                                type: Anim.DefaultSpatial
                            }
                        }
                        SequentialAnimation {
                            PropertyAction {
                                target: sweep
                                property: "opacity"
                                value: 1
                            }
                            PauseAnimation {
                                duration: 700
                            }
                            PropertyAction {
                                target: sweep
                                property: "opacity"
                                value: 0
                            }
                        }
                    }
                }

                StyledText {
                    id: fault

                    width: parent.width
                    text: Translator.fault + " — Alt ↵ opens Google Translate"
                    visible: root.failed
                    wrapMode: Text.WordWrap
                    font: Tokens.font.body.builders.medium.size(10.5 * root.scale).build()
                    color: Colours.palette.m3onErrorContainer
                }
            }

            // What was asked, quietly, once the answer is in.
            Item {
                width: parent.width
                height: root.ready ? original.implicitHeight : 0
                clip: true

                Behavior on height {
                    Anim {
                        type: Anim.DefaultSpatial
                    }
                }

                StyledText {
                    id: original

                    width: parent.width
                    text: "“" + root.modelData.text + "”"
                    elide: Text.ElideRight
                    font: Tokens.font.body.builders.small.size(9 * root.scale).build()
                    color: Colours.palette.m3onTertiaryContainer
                    opacity: root.ready ? 0.6 : 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                }
            }

            // Other languages are one click away; the choice lands in the query as ";fr …".
            Flow {
                width: parent.width
                spacing: Tokens.spacing.small
                opacity: root.ready ? 1 : 0
                visible: opacity > 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }

                Repeater {
                    model: root.quickLanguages

                    Rectangle {
                        id: pill

                        required property string modelData
                        required property int index

                        readonly property bool active: modelData === Translator.target

                        width: pillLabel.implicitWidth + Tokens.padding.medium * 1.6
                        height: 24 * root.scale
                        radius: active ? height / 2 : Tokens.rounding.small
                        color: active ? Colours.palette.m3tertiary : pillHover.containsMouse ? Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.2) : Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.1)
                        scale: pillHover.pressed ? 0.94 : 1

                        Behavior on color {
                            CAnim {}
                        }
                        Behavior on radius {
                            Anim {
                                type: Anim.FastSpatial
                            }
                        }
                        Behavior on scale {
                            Anim {
                                type: Anim.FastSpatial
                            }
                        }

                        StyledText {
                            id: pillLabel

                            anchors.centerIn: parent
                            text: Translate.languageName(pill.modelData)
                            font: Tokens.font.body.builders.small.size(9 * root.scale).weight(pill.active ? Font.DemiBold : Font.Medium).build()
                            color: pill.active ? Colours.palette.m3onTertiary : Colours.palette.m3onTertiaryContainer
                        }

                        MouseArea {
                            id: pillHover

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.picked(pill.modelData)
                        }
                    }
                }
            }
        }
    }

    readonly property var quickLanguages: ["es", "en", "fr", "de", "pt", "it", "ja"]

    // A language pill; the accented one is the target.
    component Chip: Rectangle {
        id: chip

        property string text
        property bool accent
        property bool pulsing

        onPulsingChanged: {
            if (!pulsing)
                label.opacity = 1;
        }

        Layout.alignment: Qt.AlignVCenter
        implicitWidth: label.implicitWidth + Tokens.padding.medium * 1.6
        implicitHeight: 24 * root.scale
        radius: height / 2
        color: accent ? Colours.palette.m3tertiary : Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.12)

        Behavior on implicitWidth {
            Anim {
                type: Anim.FastSpatial
            }
        }
        Behavior on color {
            CAnim {}
        }

        StyledText {
            id: label

            anchors.centerIn: parent
            text: chip.text
            font: Tokens.font.body.builders.small.size(9 * root.scale).weight(Font.Medium).build()
            color: chip.accent ? Colours.palette.m3onTertiary : Colours.palette.m3onTertiaryContainer

            SequentialAnimation on opacity {
                running: chip.pulsing
                loops: Animation.Infinite

                NumberAnimation {
                    to: 0.45
                    duration: 520
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    to: 1
                    duration: 520
                    easing.type: Easing.InOutSine
                }
            }
        }
    }
}
