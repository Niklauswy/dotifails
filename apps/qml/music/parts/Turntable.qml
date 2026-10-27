// «Ahora suena» as a record player: the sleeve (the cover) and, beside it, a platter where the record plays.
// Every song starts with its little ritual: the tonearm lifts and swings home, the record slides back into the
// sleeve, the new one slides out, the arm swings over the lead-in, lowers its tip onto the groove and the platter
// spins up. While the song plays the arm creeps towards the label; in pause it lifts and swings home and the record
// coasts to a stop. Reduced motion: every step happens at once.
import QtQuick
import QtQuick.Effects
import WysunM3

Item {
    id: root

    property url cover
    property string trackKey
    property bool playing
    property real progress                      // 0…1 through the song: where the stylus is
    property color tone: Theme.m3primary

    readonly property real side: Math.min(height, width / 1.55)
    readonly property real recordSize: side * 0.94
    readonly property real _inX: side * 0.03
    readonly property real _outX: side * 0.5

    // The ritual's state: what the sleeve and label show, how far the record is out, where the arm is.
    property url shownCover
    property real recordOut: 0                  // 0 in the sleeve … 1 on the platter
    property real armSwing: 0                   // 0 on its rest … 1 over the record
    property real armDown: 0                    // 0 lifted … 1 the stylus on the groove
    property bool _ready

    readonly property bool turning: playing && armDown > 0.95

    implicitWidth: 420
    implicitHeight: 280

    function _ms(name: string, factor: real): int {
        return Motion.reduced ? 0 : Theme.duration(name) * factor;
    }

    function _settle() {
        if (swap.running)
            return;           // the swap ends by settling itself
        lower.stop();
        lift.stop();
        (playing ? lower : lift).start();
    }

    onPlayingChanged: _settle()
    onTrackKeyChanged: {
        if (!_ready || Motion.reduced) {
            shownCover = cover;
            return;
        }
        lower.stop();
        lift.stop();
        swap.restart();
    }
    // The artwork of the same song can arrive a moment later; a new song's waits for the record to go in.
    onCoverChanged: Qt.callLater(_takeCover)
    function _takeCover() {
        if (!swap.running || swap.coverPending)
            shownCover = cover;
    }
    Component.onCompleted: {
        shownCover = cover;
        recordOut = 1;
        if (playing) {
            armSwing = 1;
            armDown = 1;
        }
        _ready = true;
    }

    // Play: the record out, the arm over the groove, the tip down.
    SequentialAnimation {
        id: lower

        NumberAnimation {
            target: root
            property: "recordOut"
            to: 1
            duration: root.recordOut > 0.99 ? 0 : root._ms("large", 1)
            easing.type: Easing.OutBack
            easing.overshoot: 0.8
        }
        NumberAnimation {
            target: root
            property: "armSwing"
            to: 1
            duration: root._ms("large", 1.1)
            easing.type: Easing.InOutCubic
        }
        PauseAnimation {
            duration: root._ms("small", 0.6)
        }
        NumberAnimation {
            target: root
            property: "armDown"
            to: 1
            duration: root._ms("normal", 1.2)
            easing.type: Easing.OutBounce
        }
    }

    // Pause: the tip lifts, the arm swings home.
    SequentialAnimation {
        id: lift

        NumberAnimation {
            target: root
            property: "armDown"
            to: 0
            duration: root._ms("small", 1.2)
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: root
            property: "armSwing"
            to: 0
            duration: root._ms("large", 1)
            easing.type: Easing.InOutCubic
        }
    }

    // A new song: lift, home, the record back into its sleeve, the new one out, and play.
    SequentialAnimation {
        id: swap

        property bool coverPending

        NumberAnimation {
            target: root
            property: "armDown"
            to: 0
            duration: root.armDown > 0.01 ? root._ms("small", 1) : 0
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: root
            property: "armSwing"
            to: 0
            duration: root.armSwing > 0.01 ? root._ms("normal", 1.4) : 0
            easing.type: Easing.InOutCubic
        }
        NumberAnimation {
            target: root
            property: "recordOut"
            to: 0
            duration: root._ms("normal", 1.2)
            easing.type: Easing.InCubic
        }
        ScriptAction {
            script: {
                root.shownCover = root.cover;
                swap.coverPending = true;
                sleeveBump.restart();
            }
        }
        PauseAnimation {
            duration: root._ms("small", 1)
        }
        NumberAnimation {
            target: root
            property: "recordOut"
            to: 1
            duration: root._ms("extraLarge", 0.9)
            easing.type: Easing.OutBack
            easing.overshoot: 0.8
        }
        ScriptAction {
            script: {
                swap.coverPending = false;
                if (root.playing)
                    lower.start();
            }
        }
    }

    // ------------------------------------------------------------- platter
    // A soft pool of the record's colour under the platter, breathing while it plays.
    Rectangle {
        id: glow

        x: root._outX + (root.recordSize - width) / 2
        y: (root.side - height) / 2
        width: root.recordSize * 1.04
        height: width
        radius: width / 2
        color: root.tone
        opacity: root.turning ? 0.55 : 0.18
        visible: !root._software
        layer.enabled: visible
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: 1
            blurMax: 64
            autoPaddingEnabled: true
        }

        Behavior on opacity {
            NumberAnimation {
                duration: root._ms("extraLarge", 1)
            }
        }

        SequentialAnimation on scale {
            running: root.turning && !Motion.reduced
            loops: Animation.Infinite

            NumberAnimation {
                to: 1.06
                duration: Theme.duration("extraLarge") * 2
                easing.type: Easing.InOutSine
            }
            NumberAnimation {
                to: 0.98
                duration: Theme.duration("extraLarge") * 2
                easing.type: Easing.InOutSine
            }
        }
    }
    readonly property bool _software: GraphicsInfo.api === GraphicsInfo.Software

    // The platter's rim, seen around the record when it slides into the sleeve.
    Rectangle {
        x: root._outX + (root.recordSize - width) / 2
        y: (root.side - height) / 2
        width: root.recordSize * 1.02
        height: width
        radius: width / 2
        color: Qt.alpha(Theme.m3surfaceContainerHighest, 0.65)
        border.width: Math.max(1, root.recordSize * 0.006)
        border.color: Qt.alpha(Theme.m3outlineVariant, 0.8)

        Rectangle {
            anchors.centerIn: parent
            width: root.recordSize * 0.03
            height: width
            radius: width / 2
            color: Theme.m3outline
        }
    }

    // --------------------------------------------------------------- record
    Vinyl {
        id: record

        objectName: "vinyl"
        width: root.recordSize
        height: width
        y: (root.side - height) / 2
        x: root._inX + (root._outX - root._inX) * root.recordOut
        cover: root.shownCover
        tone: root.tone
        spinning: root.turning
        layer.enabled: !root._software
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: 0.8
            blurMax: 32
            shadowVerticalOffset: 8
            shadowColor: Qt.alpha(Theme.m3shadow, 0.6)
        }
    }

    // --------------------------------------------------------------- sleeve
    Item {
        id: sleeve

        width: root.side
        height: root.side
        transformOrigin: Item.Right

        SequentialAnimation {
            id: sleeveBump

            NumberAnimation {
                target: sleeve
                property: "scale"
                to: 1.035
                duration: root._ms("small", 0.7)
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: sleeve
                property: "scale"
                to: 1
                duration: root._ms("normal", 1)
                easing.type: Easing.OutBack
            }
        }

        RectangularShadow {
            anchors.fill: art
            radius: art.radius
            blur: 30
            spread: 1
            offset.y: 12
            color: Qt.alpha(Theme.m3shadow, 0.5)
        }

        Rectangle {
            id: art

            anchors.fill: parent
            radius: Theme.rounding.medium ?? 0
            color: root.tone

            Image {
                id: sleeveImage

                anchors.fill: parent
                source: root.shownCover
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 640
                sourceSize.height: 640
                asynchronous: true
                visible: status === Image.Ready
                layer.enabled: !root._software
                layer.samples: 4
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskSource: sleeveMask
                    maskThresholdMin: 0.5
                    maskSpreadAtMin: 1.0
                    autoPaddingEnabled: false
                }
            }
            Icon {
                anchors.centerIn: parent
                name: "album"
                size: parent.width * 0.3
                color: Theme.m3onPrimaryContainer
                visible: sleeveImage.status !== Image.Ready
            }

            // The opening of the sleeve: a soft shade along the edge the record comes out of.
            Rectangle {
                anchors.right: parent.right
                width: parent.width * 0.06
                height: parent.height
                radius: art.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop {
                        position: 0
                        color: "transparent"
                    }
                    GradientStop {
                        position: 1
                        color: Qt.alpha(Theme.m3shadow, 0.35)
                    }
                }
            }
        }

        Rectangle {
            id: sleeveMask

            anchors.fill: art
            radius: art.radius
            visible: false
            layer.enabled: true
            layer.samples: 4
        }
    }

    // -------------------------------------------------------------- tonearm
    Item {
        id: arm

        objectName: "tonearm"
        readonly property real length: root.recordSize * 0.62
        readonly property real rest: -30
        // Over the lead-in at the start of the song, near the label at its end.
        readonly property real playing: -18 + 18 * Math.max(0, Math.min(1, root.progress))
        readonly property real lifted: 1 - root.armDown

        // The pivot stands on the plinth beyond the top right of the platter.
        x: root._outX + root.recordSize * 0.98
        y: (root.side - root.recordSize) / 2 + root.recordSize * 0.02
        width: 1
        height: 1
        z: 2
        rotation: rest + (playing - rest) * root.armSwing

        Behavior on rotation {
            enabled: !lower.running && !lift.running && !swap.running
            NumberAnimation {
                duration: 900
            }
        }

        // The arm and its head, raised towards the viewer while lifted: bigger, with a longer shadow.
        Item {
            id: wand

            // A square around the pivot big enough for the whole arm, so its shadow layer holds all of it.
            readonly property real reach: arm.length * 1.25

            x: -reach
            y: -reach
            width: reach * 2
            height: reach * 2
            scale: 1 + 0.07 * arm.lifted
            layer.enabled: !root._software
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowBlur: 0.5 + 0.4 * arm.lifted
                blurMax: 24
                shadowHorizontalOffset: 3 + 12 * arm.lifted
                shadowVerticalOffset: 4 + 16 * arm.lifted
                shadowColor: Qt.alpha(Theme.m3shadow, 0.55)
            }

            Rectangle {
                id: tube

                // The arm hangs down-left from the pivot, with a slight bend before the head.
                x: wand.reach - width / 2
                y: wand.reach
                width: root.recordSize * 0.022
                height: arm.length
                radius: width / 2
                transformOrigin: Item.Top
                rotation: 22
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop {
                        position: 0
                        color: Theme.m3onSurfaceVariant
                    }
                    GradientStop {
                        position: 0.5
                        color: Theme.m3onSurface
                    }
                    GradientStop {
                        position: 1
                        color: Theme.m3outline
                    }
                }

                // Headshell and cartridge in the record's colour; the stylus lights up on the groove.
                Rectangle {
                    id: head

                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.bottom
                    anchors.topMargin: -height * 0.25
                    width: parent.width * 3
                    height: parent.width * 4.4
                    radius: parent.width * 0.6
                    rotation: -14
                    color: root.tone
                    border.width: 1
                    border.color: Qt.alpha(Theme.m3onSurface, 0.25)

                    Rectangle {
                        // Finger lift.
                        x: parent.width * 0.85
                        y: parent.height * 0.12
                        width: parent.width * 0.7
                        height: parent.width * 0.18
                        radius: height / 2
                        color: Theme.m3onSurfaceVariant
                    }
                    Rectangle {
                        // Stylus.
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: -height * 0.4
                        width: parent.width * 0.32
                        height: width
                        radius: width / 2
                        color: root.turning ? Theme.m3primary : Theme.m3outline

                        Behavior on color {
                            CAnim {
                                kind: "defaultEffects"
                            }
                        }
                    }
                }
            }

            // Counterweight behind the pivot.
            Rectangle {
                x: wand.reach - width / 2
                y: wand.reach - height * 1.15
                width: root.recordSize * 0.07
                height: root.recordSize * 0.09
                radius: width * 0.3
                rotation: 22
                transformOrigin: Item.Bottom
                color: Theme.m3onSurfaceVariant
            }
        }

        // Pivot.
        Rectangle {
            anchors.centerIn: parent
            width: root.recordSize * 0.12
            height: width
            radius: width / 2
            color: Theme.m3surfaceContainerHighest
            border.width: root.recordSize * 0.012
            border.color: Theme.m3outline

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.4
                height: width
                radius: width / 2
                color: root.tone
            }
        }
    }

    // The arm rest.
    Rectangle {
        x: arm.x + root.recordSize * 0.065 - width / 2
        y: arm.y + root.recordSize * 0.46 - height / 2
        width: root.recordSize * 0.05
        height: width
        radius: width / 2
        z: 1
        color: Theme.m3surfaceContainerHighest
        border.width: 1
        border.color: Theme.m3outline
    }
}
