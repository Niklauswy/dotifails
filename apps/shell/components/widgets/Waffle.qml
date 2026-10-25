pragma ComponentBehavior: Bound

import QtQuick
import qs.services
import "WaffleMoves.js" as Moves

// The waffle, Wysun's office-clock mascot, drawn live with the lock's mascot shader (bundled in the
// shell plugin as qrc:/shaders/mascot.frag.qsb): crisp at any size and always in the current theme's
// colours. Two acts:
//   dance  headphones on, 32 beats at `bpm` with music notes; while nothing plays it naps standing up
//   story  a 16 s loop (waves, yawns, sleeps standing, wakes, stretches, waves)
Item {
    id: root

    property string act: "dance"
    property bool playing: true
    property real bpm: 120

    property real beat: 0
    property real seconds: 0
    readonly property bool dancing: act === "dance"
    readonly property bool napping: dancing && !playing
    readonly property var pose: napping ? Moves.nap(seconds) : dancing ? Moves.dance(beat) : Moves.story(seconds)

    // The character's shade follows the scheme; in a light scheme the ink lines turn dark.
    readonly property color ink: Colours.palette.m3primary
    readonly property color core: Colours.light ? Colours.palette.m3surface : Colours.palette.m3onSurface
    readonly property color line: Colours.light ? Colours.palette.m3onSurface : Colours.palette.m3surface

    implicitWidth: 180
    implicitHeight: 200

    NumberAnimation on beat {
        from: 0
        to: 32
        loops: Animation.Infinite
        running: root.visible && root.dancing && root.playing
        duration: 32 * 60000 / Math.max(40, Math.min(220, root.bpm || 120))
    }

    NumberAnimation on seconds {
        from: 0
        to: 16
        loops: Animation.Infinite
        running: root.visible && (!root.dancing || root.napping)
        duration: 16000
    }

    ShaderEffect {
        id: body

        // The shader's frame is 0.9 wide for 1 tall; the feet stand near its bottom.
        height: Math.min(root.height / (1 + 0.12), root.width / 0.9)
        width: height * 0.9
        x: (root.width - width) / 2
        y: root.height - height * 0.97 - root.pose.hop * height * 0.12

        property real aspect: width / Math.max(1, height)
        property real turn: root.pose.turn
        property real walk: root.pose.walk
        property real stride: root.pose.stride
        property real wave: root.pose.wave
        property real waving: root.pose.waving
        property real squash: root.pose.squash
        property real tuck: root.pose.tuck
        property real talk: root.pose.talk
        property real blink: root.pose.blink
        property real mood: root.pose.mood
        property real headphones: root.dancing ? 1 : 0
        property real plain: 0
        property color ink: root.ink
        property color core: root.core
        property color base: root.line
        fragmentShader: "qrc:/shaders/mascot.frag.qsb"
    }

    // Music notes floating up from the headphones, one every two beats.
    Repeater {
        model: root.dancing ? 4 : 0

        Text {
            required property int index
            readonly property real age: ((root.beat - index * 2) % 8 + 8) % 8 / 3.2

            visible: root.playing && age < 1
            text: index % 2 ? "♫" : "♪"
            color: index % 2 ? root.ink : root.core
            font.pixelSize: body.height * 0.11
            font.bold: true
            x: root.width / 2 + (index % 2 ? 0.34 : -0.46) * body.height + 0.04 * body.height * Math.sin(age * 4 + index)
            y: body.y + body.height * (0.3 - age * 0.32)
            opacity: age < 0.15 ? age / 0.15 : 1 - Math.max(0, age - 0.6) / 0.4
        }
    }

    // Zzz while it sleeps.
    Repeater {
        model: root.dancing && !root.napping ? 0 : 3

        Text {
            required property int index
            readonly property real age: root.napping ? ((root.seconds - index * 1.1) % 3.3 + 3.3) % 3.3 / 2.2
                                                     : (root.seconds - 5.4 - index * 0.9) / 2.2

            visible: age > 0 && age < 1 && (root.napping || root.seconds > 5.4 && root.seconds < 9.5)
            text: "Z"
            color: root.ink
            font.pixelSize: body.height * (0.08 + index * 0.02)
            font.bold: true
            x: root.width / 2 + body.height * (0.22 + age * 0.14)
            y: body.y + body.height * (0.3 - age * 0.25)
            opacity: age < 0.2 ? age / 0.2 : 1 - Math.max(0, age - 0.6) / 0.4
        }
    }
}
