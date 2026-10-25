pragma ComponentBehavior: Bound

// Wysun lock · a refinement terminal. A box dragged with the mouse picks numbers; every keystroke
// agitates a cluster and sends a few digits into one of five bins; Enter sweeps the field, a refusal
// scrambles it red and empties the bins, acceptance drains it and the CRT powers off. Everything is
// drawn on an offscreen «screen» and shown through a CRT shader. Pure presentation: the password only
// leaves through ``submitted``.

import QtQuick
import QtQuick.Shapes

Item {
    id: root

    // locked | authenticating | success | failed | maxtries | error  (LockAuth.state)
    property string authState: "locked"
    property string detail: ""
    property bool leaving: false
    property string username: ""
    property string shaderDir: ""
    property bool reducedMotion: false
    property bool takesInput: true
    required property LockPalette scheme

    signal submitted(string password)
    // Greeter only: Tab / Shift+Tab (user), F2 (session), F10 / F12 (restart / power off).
    signal navigate(string action)

    readonly property bool shaders: shaderDir.length > 0
    readonly property int length: input.length
    readonly property string phase: leaving ? "leaving"
        : authState === "success" ? "granted"
        : authState === "authenticating" ? "verifying"
        : (deniedHold.running || authState === "maxtries") ? "denied"
        : length > 0 ? "typing" : "idle"

    readonly property color base: scheme.surface
    readonly property color ink: scheme.primary
    readonly property color danger: scheme.error
    readonly property color textColour: scheme.text
    readonly property color mutedColour: scheme.muted
    readonly property color tone: phase === "denied" ? danger : ink
    // The four tempers, in the scheme's semantic colours like the refiners' screen: WO, FC, DR, MA.
    readonly property var temperColours: [scheme.pick("success", ink), scheme.pick("warning", ink), danger, scheme.pick("info", ink)]
    readonly property real unit: Math.min(width, height)
    // The theme's mono family; the lock passes the token, the greeter the copy written at install.
    property string mono: "monospace"
    // How the screen leaves on success: «crt» powers off, «elevator» closes the doors (greeter).
    property string exitStyle: "crt"
    readonly property real stroke: Math.max(1, Math.round(unit * 0.0022))

    property real clock: 0
    property var bins: [0, 0, 0, 0, 0]
    property var lids: [0, 0, 0, 0, 0]
    property point focusPoint: Qt.point(0.5, 0.5)
    // The refiner's lens glides from cluster to cluster instead of jumping.
    Behavior on focusPoint {
        enabled: !root.reducedMotion
        PropertyAnimation {
            duration: 240
            easing.type: Easing.OutCubic
        }
    }
    // Typing, the lens scans the field by itself: a step per key, heading in a slowly turning direction
    // and bouncing off the edges. The mouse does not stir the field; it picks numbers with a box.
    property real scanHeading: Math.random() * 2 * Math.PI

    // While nobody types, a group of numbers somewhere in the field trembles, waiting to be refined.
    // Catching it in a box sends it to a bin; a new one turns up elsewhere a little later.
    property point target: Qt.point(0.2 + Math.random() * 0.6, 0.2 + Math.random() * 0.6)
    property bool targetCaught: false
    property real targetGlow: phase === "idle" && !targetCaught ? 1 : 0
    Behavior on targetGlow {
        NumberAnimation {
            duration: root.reducedMotion ? 0 : 700
            easing.type: Easing.InOutQuad
        }
    }

    Timer {
        id: respawn
        interval: 2600
        onTriggered: {
            let next;
            do {
                next = Qt.point(0.12 + Math.random() * 0.76, 0.15 + Math.random() * 0.7);
            } while (Math.abs(next.x - root.target.x) < 0.2 && Math.abs(next.y - root.target.y) < 0.2);
            root.target = next;
            root.targetCaught = false;
        }
    }

    function nextFocus(): point {
        root.scanHeading += (Math.random() - 0.5) * 1.1;
        const step = 0.06 + Math.random() * 0.06;
        let x = root.focusPoint.x + Math.cos(root.scanHeading) * step;
        let y = root.focusPoint.y + Math.sin(root.scanHeading) * step * 1.3;
        if (x < 0.08 || x > 0.92) {
            root.scanHeading = Math.PI - root.scanHeading;
            x = Math.max(0.08, Math.min(0.92, x));
        }
        if (y < 0.1 || y > 0.9) {
            root.scanHeading = -root.scanHeading;
            y = Math.max(0.1, Math.min(0.9, y));
        }
        return Qt.point(x, y);
    }
    property real agitation: 0
    property real alert: phase === "denied" ? 1 : 0
    property real scramble: 0
    property real tear: 0
    property real drain: 0
    property real power: 1
    property real shake: 0
    // Easter egg. Each full bin celebrates («QUOTA MET»); five full bins start the reward: the mascot
    // climbs out of the middle bin, announces it and dives back in; the terminal breaks into a pixel-art
    // film of the founder (summit.frag) and comes back with «100%».
    property var quotaAt: [-10, -10, -10, -10, -10]
    // The four tempers of each bin (Woe, Frolic, Dread, Malice), fed by every digit refined into it.
    property var tempers: [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    property real doors: 0
    // Unlocking as an elevator can open the doors again on the desktop: a snapshot of it taken when
    // locking (an image URL), so the real desktop appears exactly where the doors part.
    property string desktop: ""
    property real reveal: 0
    readonly property bool revealing: exitStyle === "elevator" && desktopImage.status === Image.Ready
    // How long leaving takes, so the lock unlocks when the animation ends.
    readonly property int leaveDuration: reducedMotion ? 0 : exitStyle !== "elevator" ? 650 : revealing ? 1300 + 250 + 1600 : 1400
    property real dance: 0
    // The summit film at 100 %: its dissolve, its progress through the shots and the closing «100%».
    property real summit: 0
    property real story: 0
    property real hundred: 0
    readonly property real complete: bins.reduce((sum, value) => sum + value, 0) / bins.length

    Behavior on alert { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    function setBin(index: int, value: real): void {
        const next = root.bins.slice();
        const before = next[index];
        next[index] = Math.max(0, Math.min(1, value));
        root.bins = next;
        if (before < 1 && next[index] >= 1 && (root.phase === "typing" || root.phase === "idle"))
            root.quotaMet(index);
    }

    function quotaMet(index: int): void {
        const stamps = root.quotaAt.slice();
        stamps[index] = root.clock;
        root.quotaAt = stamps;
        root.setLid(index, 1);
        if (!root.reducedMotion) {
            const bin = binRepeater.itemAt(index);
            for (let i = 0; i < 16; i++)
                fountain.createObject(screen, { originX: binsRow.x + bin.x + bin.width / 2, originY: binsRow.y + bin.height * 0.15,
                                                spreadX: (Math.random() - 0.5) * root.unit * 0.22,
                                                rise: root.unit * (0.08 + Math.random() * 0.14), delay: i * 25 });
        }
        if (root.bins.every(value => value >= 1))
            perfect.restart();
    }

    function glowOf(index: int): real {
        return Math.max(0, 1 - (root.clock - root.quotaAt[index]) / 1.6);
    }

    function setLid(index: int, value: real): void {
        const next = root.lids.slice();
        next[index] = value;
        root.lids = next;
    }

    // A keystroke: agitate a cluster, open a bin, send digits flying into it.
    function refine(): void {
        const open = [0, 1, 2, 3, 4].filter(i => root.bins[i] < 1);
        const bin = open.length ? open[Math.floor(Math.random() * open.length)] : Math.floor(Math.random() * 5);
        const point = root.nextFocus();
        root.focusPoint = point;
        root.setBin(bin, root.bins[bin] + 0.06 + Math.random() * 0.08);
        const moods = root.tempers.map(row => row.slice());
        const temper = Math.floor(Math.random() * 4);
        moods[bin][temper] = Math.min(1, moods[bin][temper] + 0.1 + Math.random() * 0.15);
        for (let k = 0; k < 4; k++)
            moods[bin][k] = Math.min(1, moods[bin][k] + Math.random() * 0.05);
        root.tempers = moods;
        if (root.reducedMotion)
            return;
        agitate.restart();
        lidTimer.open(bin);
        for (let i = 0; i < 5; i++)
            flyer.createObject(screen, { bin: bin, fromX: field.x + point.x * field.width + (Math.random() - 0.5) * field.width * 0.08,
                                         fromY: field.y + point.y * field.height + (Math.random() - 0.5) * field.height * 0.1,
                                         delay: i * 45 });
    }

    function unrefine(): void {
        for (let i = 4; i >= 0; i--) {
            if (root.bins[i] > 0) {
                root.setBin(i, root.bins[i] - 0.1);
                return;
            }
        }
    }

    onPhaseChanged: {
        if (phase === "denied")
            deniedAnim.restart();
        else if (phase === "granted")
            grantedAnim.restart();
        else if (phase === "leaving")
            leaveAnim.restart();
    }

    onAuthStateChanged: {
        if (authState === "failed" || authState === "error")
            deniedHold.restart();
        if (authState === "locked") {
            root.drain = 0;
            root.power = 1;
            root.bins = [0, 0, 0, 0, 0];
            root.lids = [0, 0, 0, 0, 0];
            root.tempers = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]];
            root.dance = 0;
            root.doors = 0;
            root.reveal = 0;
        }
        if (authState !== "authenticating" && authState !== "success")
            input.forceActiveFocus();
    }

    Timer {
        id: deniedHold
        interval: 2400
    }

    Timer {
        interval: 33
        repeat: true
        running: root.visible && !root.reducedMotion
        onTriggered: root.clock += 0.033
    }

    SequentialAnimation {
        id: agitate
        NumberAnimation { target: root; property: "agitation"; to: 1; duration: 90 }
        PauseAnimation { duration: 260 }
        NumberAnimation { target: root; property: "agitation"; to: 0; duration: 900; easing.type: Easing.OutCubic }
    }

    Timer {
        id: lidTimer

        property int bin: -1
        function open(index: int): void {
            if (bin >= 0 && bin !== index)
                root.setLid(bin, 0);
            bin = index;
            root.setLid(index, 1);
            restart();
        }
        interval: 650
        onTriggered: {
            if (bin >= 0 && root.bins[bin] < 1)
                root.setLid(bin, 0);
            bin = -1;
        }
    }

    SequentialAnimation {
        id: perfect
        ScriptAction {
            script: {
                root.lids = [1, 1, 1, 1, 1];
                mascot.reset();
            }
        }
        NumberAnimation { target: root; property: "dance"; to: 1; duration: 450; easing.type: Easing.OutCubic }
        // Out of the middle bin: a crouch, a leap with the legs tucked, a squashed landing.
        NumberAnimation { target: mascot; property: "squash"; to: -0.45; duration: 160; easing.type: Easing.OutQuad }
        ParallelAnimation {
            NumberAnimation { target: mascot; property: "sink"; to: 0; duration: 380; easing.type: Easing.OutQuad }
            NumberAnimation { target: mascot; property: "lift"; to: 0.55; duration: 380; easing.type: Easing.OutQuad }
            NumberAnimation { target: mascot; property: "squash"; to: 0.5; duration: 160 }
            NumberAnimation { target: mascot; property: "tuck"; to: 0.9; duration: 300 }
        }
        ParallelAnimation {
            NumberAnimation { target: mascot; property: "lift"; to: 0; duration: 330; easing.type: Easing.InQuad }
            NumberAnimation { target: mascot; property: "tuck"; to: 0; duration: 300 }
            NumberAnimation { target: mascot; property: "squash"; to: 0.15; duration: 330 }
        }
        NumberAnimation { target: mascot; property: "squash"; to: -0.55; duration: 90 }
        NumberAnimation { target: mascot; property: "squash"; to: 0; duration: 320; easing.type: Easing.OutBack }
        // «QUOTA MET!», with a big wave.
        ScriptAction { script: mascot.say("QUOTA MET!") }
        NumberAnimation { target: mascot; property: "waving"; to: 1; duration: 200 }
        NumberAnimation { target: mascot; property: "wave"; from: 0; to: 2; duration: 1300 }
        NumberAnimation { target: mascot; property: "waving"; to: 0; duration: 200 }
        // The mascot announces the reward and dives back into its bin…
        ScriptAction { script: { mascot.mood = 2; mascot.say("TIME FOR YOUR REWARD!"); } }
        PauseAnimation { duration: 1300 }
        ScriptAction { script: mascot.say("") }
        NumberAnimation { target: mascot; property: "squash"; to: -0.45; duration: 150 }
        ParallelAnimation {
            NumberAnimation { target: mascot; property: "lift"; to: 0.5; duration: 300; easing.type: Easing.OutQuad }
            NumberAnimation { target: mascot; property: "squash"; to: 0.55; duration: 150 }
            NumberAnimation { target: mascot; property: "tuck"; to: 1; duration: 250 }
        }
        ParallelAnimation {
            NumberAnimation { target: mascot; property: "lift"; to: 0; duration: 380; easing.type: Easing.InQuad }
            NumberAnimation { target: mascot; property: "sink"; to: 1.1; duration: 420; easing.type: Easing.InQuad }
        }
        // …and the terminal breaks into the founder's film (summit.frag): over the ranges, the lone peak,
        // the founder on the summit, his leap and flight into the sunset.
        ParallelAnimation {
            NumberAnimation { target: root; property: "summit"; to: 1; duration: 1500; easing.type: Easing.InOutQuad }
            NumberAnimation { target: root; property: "story"; from: 0; to: 1; duration: founderFilm.duration * 1000 }
        }
        // Back to the terminal, which shows the result.
        NumberAnimation { target: root; property: "summit"; to: 0; duration: 1300; easing.type: Easing.InOutQuad }
        NumberAnimation { target: root; property: "hundred"; to: 1; duration: 220; easing.type: Easing.OutBack }
        PauseAnimation { duration: 1600 }
        NumberAnimation { target: root; property: "hundred"; to: 0; duration: 300 }
        ScriptAction { script: root.lids = [0, 0, 0, 0, 0] }
        NumberAnimation { target: root; property: "dance"; to: 0; duration: 600; easing.type: Easing.InOutCubic }
    }

    SequentialAnimation {
        id: deniedAnim
        ScriptAction { script: { perfect.stop(); root.dance = 0; root.summit = 0; root.hundred = 0; mascot.reset(); } }
        ParallelAnimation {
            NumberAnimation { target: root; property: "tear"; to: 1; duration: 70 }
            NumberAnimation { target: root; property: "scramble"; to: 1; duration: 70 }
            NumberAnimation { target: root; property: "shake"; from: 0; to: 1; duration: 420 }
        }
        ScriptAction { script: root.lids = [1, 1, 1, 1, 1] }
        NumberAnimation { target: root; property: "tear"; to: 0.15; duration: 500; easing.type: Easing.OutCubic }
        ScriptAction {
            script: {
                root.bins = [0, 0, 0, 0, 0];
                root.lids = [0, 0, 0, 0, 0];
            }
        }
        NumberAnimation { target: root; property: "scramble"; to: 0; duration: 900; easing.type: Easing.OutCubic }
        NumberAnimation { target: root; property: "tear"; to: 0; duration: 300 }
    }

    SequentialAnimation {
        id: grantedAnim
        ScriptAction {
            script: {
                deniedAnim.stop();
                perfect.stop();
                root.summit = 0;
                root.hundred = 0;
                mascot.reset();
                root.tear = 0;
                root.scramble = 0;
                root.dance = 0;
                root.bins = [1, 1, 1, 1, 1];
                root.lids = [1, 1, 1, 1, 1];
            }
        }
        NumberAnimation { target: root; property: "drain"; from: 0; to: 1; duration: root.reducedMotion ? 0 : 1100; easing.type: Easing.InQuad }
    }

    SequentialAnimation {
        id: leaveAnim
        ScriptAction {
            script: root.reveal = root.revealing ? 0.5 : 0
        }
        NumberAnimation {
            target: root
            property: root.exitStyle === "elevator" ? "doors" : "power"
            from: root.exitStyle === "elevator" ? 0 : 1
            to: root.exitStyle === "elevator" ? 1 : 0
            duration: root.reducedMotion ? 0 : root.exitStyle !== "elevator" ? 650 : root.revealing ? 1300 : 1400
            easing.type: root.exitStyle === "elevator" ? Easing.InOutQuart : Easing.InCubic
        }
        // The car stops; then the doors open again, on the desktop this time.
        PauseAnimation {
            duration: root.revealing && !root.reducedMotion ? 250 : 0
        }
        ScriptAction {
            script: {
                if (root.revealing) {
                    root.reveal = 1;
                    openAnim.restart();
                }
            }
        }
    }
    NumberAnimation {
        id: openAnim
        target: root
        property: "doors"
        from: 1
        to: 0
        duration: root.reducedMotion ? 0 : 1600
        easing.type: Easing.InOutCubic
    }

    Image {
        id: desktopImage
        visible: false
        source: root.desktop
        asynchronous: true
        cache: false
    }

    // ---------------------------------------------------------------- the screen
    ShaderEffectSource {
        id: screenSource
        sourceItem: screen
        hideSource: root.shaders
        live: true
        visible: false
    }

    ShaderEffect {
        anchors.fill: parent
        visible: root.shaders
        property variant source: screenSource
        property real time: root.clock
        property real lines: root.height
        property real tear: root.tear
        property real power: root.power
        property real doors: root.doors
        property real reveal: root.reveal
        property real film: root.summit
        property variant desktop: desktopImage.status === Image.Ready ? desktopImage : screenSource
        property color ink: root.ink
        property real curve: 0.035
        property color base: root.base
        fragmentShader: root.shaders ? "file://" + root.shaderDir + "/screen.frag.qsb" : ""
    }

    Item {
        id: screen

        readonly property real margin: root.unit * 0.05

        width: root.width
        height: root.height
        x: Math.sin(root.shake * Math.PI * 9) * (1 - root.shake) * root.unit * 0.012

        Rectangle {
            anchors.fill: parent
            color: root.base
        }

        // Header: the file being refined, its progress, and the Wysun mark.
        Item {
            id: header

            x: screen.margin
            y: screen.margin * 0.8
            width: screen.width - screen.margin * 2
            height: root.unit * 0.075

            Rectangle {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - mark.width * 0.55
                height: parent.height * 0.72
                color: "transparent"
                border.color: root.tone
                border.width: root.stroke

                Rectangle {
                    x: root.stroke * 2
                    y: root.stroke * 2
                    height: parent.height - root.stroke * 4
                    width: (parent.width - root.stroke * 4) * root.complete
                    color: Qt.alpha(root.tone, 0.18)
                    Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: parent.height * 0.4
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.dance > 0.5 ? "REFINEMENT COMPLETE" : root.username
                    color: root.tone
                    font.family: root.mono
                    font.pixelSize: parent.height * 0.48
                    font.letterSpacing: root.dance > 0.5 ? parent.height * 0.08 : 0
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: mark.width * 0.55 + parent.height * 0.4
                    anchors.verticalCenter: parent.verticalCenter
                    text: Math.round(root.complete * 100) + "% Complete"
                    color: root.tone
                    font.family: root.mono
                    font.pixelSize: parent.height * 0.42
                }
            }

            WysunMark {
                id: mark
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height * 1.25
                width: height * 1.9
                colour: root.tone
                fill: root.base
                stroke: root.stroke
                spin: root.clock * (1 + root.dance * 7)
                family: root.mono
            }
        }

        DoubleRule {
            y: header.y + header.height + root.unit * 0.018
        }

        // The field.
        Item {
            id: field

            readonly property real rows: Math.max(6, Math.round(height / (root.unit * 0.062)))
            readonly property real cols: Math.max(8, Math.round(rows * width / Math.max(1, height) * 1.35))

            x: screen.margin
            y: header.y + header.height + root.unit * 0.045
            width: screen.width - screen.margin * 2
            height: binsRow.y - y - root.unit * 0.04

            ShaderEffect {
                anchors.fill: parent
                visible: root.shaders
                property variant atlas: atlasSource
                property real time: root.clock
                property real cols: field.cols
                property real rows: field.rows
                property real aspect: width / Math.max(1, height)
                property rect selection: Qt.rect(pointer.fromU, pointer.fromV, pointer.u, pointer.v)
                property real selecting: pointer.dragging ? 1 : 0
                property point target: root.target
                property real targetGlow: root.targetGlow
                property point cluster: root.focusPoint
                property real agitation: root.agitation
                property real sweep: root.phase === "verifying" ? (root.clock * 0.65) % 1.3 - 0.15 : -1
                property real alert: root.alert
                property real scramble: root.scramble
                property real drain: root.drain
                property real dance: root.dance
                property color base: root.base
                property color ink: root.ink
                property color danger: root.danger
                fragmentShader: root.shaders ? "file://" + root.shaderDir + "/field.frag.qsb" : ""
            }

            // The box being dragged over the numbers.
            Rectangle {
                visible: pointer.dragging
                x: Math.min(pointer.fromU, pointer.u) * field.width
                y: Math.min(pointer.fromV, pointer.v) * field.height
                width: Math.abs(pointer.u - pointer.fromU) * field.width
                height: Math.abs(pointer.v - pointer.fromV) * field.height
                color: Qt.alpha(root.ink, 0.06)
                border.color: root.tone
                border.width: root.stroke
            }

            // Without shaders: a quiet static grid.
            Grid {
                anchors.centerIn: parent
                visible: !root.shaders
                columns: field.cols
                Repeater {
                    model: root.shaders ? 0 : field.cols * field.rows
                    delegate: Text {
                        required property int index
                        width: field.width / field.cols
                        height: field.height / field.rows
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        text: String((index * 7919) % 10)
                        color: Qt.alpha(root.tone, 0.6)
                        font.family: root.mono
                        font.pixelSize: height * 0.45
                    }
                }
            }
        }

        DoubleRule {
            y: binsRow.y - root.unit * 0.022
        }

        // The Music Dance Experience's host: the office mascot climbs out of the middle bin, celebrates
        // and dives back in (mascot.frag, the same character as the farewell). Behind the bins.
        ShaderEffect {
            id: mascot

            readonly property Item home: binRepeater.itemAt(2)
            property real shift: 0      // side to side, in field widths
            property real lift: 0       // above the bins, in its own heights
            property real sink: 1       // 1 hidden in the bin, 0 standing on it
            property string speech: ""
            property real aspect: width / Math.max(1, height)
            property real turn: 0
            property real walk: 0
            property real stride: 0
            property real wave: 0
            property real waving: 0
            property real squash: 0
            property real tuck: 0
            property real talk: speech.length > 0 ? 0.5 + 0.5 * Math.sin(root.clock * 14) : 0
            property real blink: root.clock % 3.1 < 0.12 ? 1 : 0
            property real mood: 0
            property color ink: root.ink
            property color core: root.textColour
            property color base: root.base

            function reset(): void {
                shift = 0; lift = 0; sink = 1; speech = ""; turn = 0; walk = 0; stride = 0;
                wave = 0; waving = 0; squash = 0; tuck = 0; mood = 0;
            }
            function say(text: string): void {
                speech = text;
                if (text.length > 0)
                    balloonPop.restart();
            }

            visible: root.shaders && root.dance > 0.01 && sink < 1
            height: root.unit * 0.3
            width: height * 0.9
            x: (home ? binsRow.x + home.x + home.width / 2 : screen.width / 2) + shift * field.width - width / 2
            // The feet stand on top of the bins row; sinking puts it behind the bin.
            y: binsRow.y - height * (0.94 + lift) + sink * height * 0.95
            fragmentShader: root.shaders ? "file://" + root.shaderDir + "/mascot.frag.qsb" : ""
        }

        // What the mascot says.
        Rectangle {
            id: balloon

            visible: mascot.visible && mascot.speech.length > 0
            x: Math.min(screen.width - width - screen.margin, mascot.x + mascot.width * 0.62)
            y: mascot.y - height * 0.45
            width: balloonText.implicitWidth + root.unit * 0.05
            height: balloonText.implicitHeight + root.unit * 0.03
            radius: root.unit * 0.012
            color: root.base
            border.color: root.tone
            border.width: root.stroke * 1.5
            transformOrigin: Item.BottomLeft

            Rectangle {
                x: root.unit * 0.02
                y: parent.height - height / 2
                width: root.unit * 0.022
                height: width
                rotation: 45
                color: root.base
                border.color: root.tone
                border.width: root.stroke * 1.5
                z: -1
            }
            Text {
                id: balloonText
                anchors.centerIn: parent
                text: mascot.speech
                color: root.tone
                font.family: root.mono
                font.pixelSize: root.unit * 0.026
                font.bold: true
            }
            SequentialAnimation {
                id: balloonPop
                NumberAnimation { target: balloon; property: "scale"; from: 0.3; to: 1.12; duration: 160; easing.type: Easing.OutQuad }
                NumberAnimation { target: balloon; property: "scale"; to: 1; duration: 140; easing.type: Easing.InOutQuad }
            }
        }

        // The founder's film (FounderFilm.qml), breaking through the terminal in blots (summit.frag).
        FounderFilm {
            id: founderFilm
            anchors.fill: parent
            seconds: root.story * duration
        }
        ShaderEffect {
            anchors.fill: parent
            z: 10
            visible: root.shaders && root.summit > 0
            property real aspect: width / Math.max(1, height)
            property real reveal: root.summit
            property var source: ShaderEffectSource {
                sourceItem: founderFilm
                hideSource: true
                live: root.summit > 0
            }
            fragmentShader: root.shaders ? "file://" + root.shaderDir + "/summit.frag.qsb" : ""
        }

        // The result, as the terminal reassembles.
        Rectangle {
            z: 14
            visible: root.hundred > 0
            anchors.centerIn: parent
            width: hundredText.implicitWidth + root.unit * 0.12
            height: hundredText.implicitHeight + root.unit * 0.06
            scale: 0.6 + 0.4 * root.hundred
            opacity: root.hundred
            color: root.base
            border.color: root.tone
            border.width: root.stroke * 2

            Rectangle {
                anchors.fill: parent
                anchors.margins: root.stroke * 4
                color: "transparent"
                border.color: root.tone
                border.width: root.stroke
            }
            Text {
                id: hundredText
                anchors.centerIn: parent
                text: "100%"
                color: root.tone
                font.family: root.mono
                font.pixelSize: root.unit * 0.08
                font.bold: true
            }
        }

        // Five bins: each lid opens when digits arrive, each bar fills with them.
        Row {
            id: binsRow

            readonly property real binWidth: Math.min(width / 6.2, root.unit * 0.24)

            x: screen.margin
            y: screen.height - screen.margin * 0.9 - height
            width: screen.width - screen.margin * 2
            height: root.unit * 0.105
            spacing: (width - binWidth * 5) / 4

            Repeater {
                id: binRepeater
                model: 5
                delegate: Item {
                    id: binItem

                    required property int index
                    width: binsRow.binWidth
                    height: binsRow.height

                    Item {
                        id: box
                        width: parent.width
                        height: parent.height * 0.48
                        y: parent.height * 0.12

                        // Lid flaps swing open.
                        Rectangle {
                            width: box.width / 2
                            height: root.stroke
                            color: root.tone
                            transform: Rotation {
                                origin.x: 0
                                origin.y: 0
                                angle: -70 * Math.min(1, root.lids[binItem.index] * (1 - root.dance) + root.dance * (0.5 + 0.5 * Math.sin(root.clock * 9 + binItem.index)))
                                Behavior on angle { NumberAnimation { duration: 220; easing.type: Easing.OutBack } }
                            }
                        }
                        Rectangle {
                            x: box.width / 2
                            width: box.width / 2
                            height: root.stroke
                            color: root.tone
                            transform: Rotation {
                                origin.x: box.width / 2
                                origin.y: 0
                                angle: 70 * Math.min(1, root.lids[binItem.index] * (1 - root.dance) + root.dance * (0.5 + 0.5 * Math.sin(root.clock * 9 + binItem.index)))
                                Behavior on angle { NumberAnimation { duration: 220; easing.type: Easing.OutBack } }
                            }
                        }
                        Rectangle {
                            y: root.stroke * 2
                            width: box.width
                            height: box.height - root.stroke * 2
                            color: Qt.alpha(root.tone, 0.06 + root.lids[binItem.index] * 0.12 + root.glowOf(binItem.index) * 0.6)
                            border.color: root.tone
                            border.width: root.stroke

                            Text {
                                anchors.centerIn: parent
                                text: "0" + (binItem.index + 1)
                                color: root.tone
                                font.family: root.mono
                                font.pixelSize: parent.height * 0.5
                            }
                        }
                    }

                    // Tempers panel: rises above an open bin, hidden while «QUOTA MET» is shown.
                    Rectangle {
                        readonly property real lift: root.phase === "typing" && root.lids[binItem.index] > 0.5 && root.glowOf(binItem.index) <= 0 ? 1 : 0
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: -height - root.unit * 0.012
                        width: parent.width * 0.86
                        height: root.unit * 0.075
                        visible: opacity > 0.01
                        opacity: lift
                        color: root.base
                        border.color: root.tone
                        border.width: root.stroke
                        Behavior on opacity { NumberAnimation { duration: 180 } }

                        Column {
                            anchors.fill: parent
                            anchors.margins: root.unit * 0.008
                            spacing: root.unit * 0.004

                            Repeater {
                                model: ["WO", "FC", "DR", "MA"]
                                delegate: Row {
                                    id: mood
                                    required property string modelData
                                    required property int index
                                    spacing: root.unit * 0.006
                                    height: root.unit * 0.012

                                    Text {
                                        text: mood.modelData
                                        width: root.unit * 0.022
                                        color: root.phase === "denied" ? root.tone : root.temperColours[mood.index]
                                        font.family: root.mono
                                        font.pixelSize: root.unit * 0.0095
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: (binItem.width * 0.86 - root.unit * 0.05) * Math.max(0.04, root.tempers[binItem.index][mood.index])
                                        height: root.unit * 0.008
                                        color: root.phase === "denied" ? root.tone : root.temperColours[mood.index]
                                        Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        readonly property real glow: root.glowOf(binItem.index)
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: -height - root.unit * 0.012 - glow * root.unit * 0.02
                        width: quotaText.implicitWidth + root.unit * 0.024
                        height: quotaText.implicitHeight + root.unit * 0.01
                        visible: glow > 0
                        opacity: Math.min(1, glow * 2)
                        color: root.base
                        border.color: root.tone
                        border.width: root.stroke

                        Text {
                            id: quotaText
                            anchors.centerIn: parent
                            text: "QUOTA MET"
                            color: root.tone
                            font.family: root.mono
                            font.pixelSize: root.unit * 0.012
                            font.letterSpacing: root.unit * 0.004
                        }
                    }

                    Rectangle {
                        y: box.y + box.height + parent.height * 0.1
                        width: parent.width
                        height: parent.height * 0.24
                        color: "transparent"
                        border.color: root.tone
                        border.width: root.stroke

                        Rectangle {
                            x: root.stroke * 2
                            y: root.stroke * 2
                            height: parent.height - root.stroke * 4
                            width: (parent.width - root.stroke * 4) * root.bins[binItem.index]
                            color: Qt.alpha(root.tone, 0.85)
                            Behavior on width { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(root.bins[binItem.index] * 100) + "%"
                            color: root.bins[binItem.index] > 0.55 ? root.base : root.tone
                            font.family: root.mono
                            font.pixelSize: parent.height * 0.62
                        }
                    }
                }
            }
        }

        // Footer: the pointer's coordinates in hex (they follow you), and the time.
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: screen.height - screen.margin * 0.62
            text: "0x" + Math.floor(pointer.u * 0xFFFFFF).toString(16).toUpperCase().padStart(6, "0")
                + " : 0x" + Math.floor(pointer.v * 0xFFFFFF).toString(16).toUpperCase().padStart(6, "0")
            color: Qt.alpha(root.tone, 0.7)
            font.family: root.mono
            font.pixelSize: root.unit * 0.012
            font.letterSpacing: root.unit * 0.002
        }

        Text {
            id: stamp
            property date now: new Date()
            x: screen.width - screen.margin - width
            y: screen.height - screen.margin * 0.62
            text: Qt.locale("en_US").toString(now, "MMM dd  HH:mm").toUpperCase()
            color: Qt.alpha(root.tone, 0.7)
            font.family: root.mono
            font.pixelSize: root.unit * 0.012
            font.letterSpacing: root.unit * 0.003
            Timer {
                interval: 1000
                repeat: true
                running: true
                onTriggered: stamp.now = new Date()
            }
        }

        Text {
            x: screen.margin
            y: screen.height - screen.margin * 0.62
            text: "WYSUN · MACRODATA"
            color: Qt.alpha(root.tone, 0.7)
            font.family: root.mono
            font.pixelSize: root.unit * 0.012
            font.letterSpacing: root.unit * 0.003
        }

        // Status plate over the field while something happens.
        Rectangle {
            id: plate

            readonly property string message: root.phase === "verifying" ? "VERIFYING"
                : root.phase === "denied" ? (root.authState === "maxtries" ? "ACCESS LOCKED" : "ACCESS DENIED")
                : root.phase === "granted" || root.phase === "leaving" ? "REFINEMENT COMPLETE" : ""
            x: field.x + (field.width - width) / 2
            y: field.y + (field.height - height) / 2
            width: plateText.implicitWidth + root.unit * 0.08
            height: plateText.implicitHeight + root.unit * 0.04
            visible: message.length > 0
            color: root.base
            border.color: root.tone
            border.width: root.stroke
            opacity: root.phase === "verifying" ? 0.75 + 0.25 * Math.sin(root.clock * 6) : 1

            Text {
                id: plateText
                anchors.centerIn: parent
                text: plate.message
                color: root.tone
                font.family: root.mono
                font.pixelSize: root.unit * 0.026
                font.letterSpacing: root.unit * 0.008
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: header.y + header.height + root.unit * 0.026
            visible: text.length > 0
            text: root.detail
            color: Qt.alpha(root.tone, 0.75)
            font.family: root.mono
            font.pixelSize: root.unit * 0.012
        }
    }

    // Glyph atlas for the field shader: the ten digits in the shell's mono font.
    Row {
        id: atlas
        Repeater {
            model: 10
            delegate: Text {
                required property int index
                width: 64
                height: 96
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: String(index)
                color: root.textColour
                font.family: root.mono
                font.pixelSize: 80
            }
        }
    }

    ShaderEffectSource {
        id: atlasSource
        sourceItem: atlas
        hideSource: true
        live: false
        smooth: true
        visible: false
    }

    // Pointer, in field coordinates. Dragging draws a box like the refiners' and the numbers inside it
    // fly into a bin on release; it is only for show: the password and the progress are untouched.
    // A click gives focus back to the input.
    MouseArea {
        id: pointer

        property real u: 0.5
        property real v: 0.5
        property real fromU: 0.5
        property real fromV: 0.5
        property bool dragging: false

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        onPositionChanged: mouse => {
            u = Math.max(0, Math.min(1, (mouse.x - field.x) / field.width));
            v = Math.max(0, Math.min(1, (mouse.y - field.y) / field.height));
        }
        onPressed: mouse => {
            input.forceActiveFocus();
            fromU = u;
            fromV = v;
            dragging = root.phase !== "leaving" && mouse.y >= field.y && mouse.y <= field.y + field.height;
        }
        onReleased: {
            if (dragging)
                root.harvest(Math.min(fromU, u), Math.min(fromV, v), Math.max(fromU, u), Math.max(fromV, v));
            dragging = false;
        }
        onCanceled: dragging = false
    }

    // The numbers picked with the box fly into a bin, a few at a time.
    function harvest(u0: real, v0: real, u1: real, v1: real): void {
        const cells = [];
        for (let r = 0; r < field.rows; r++) {
            for (let c = 0; c < field.cols; c++) {
                const u = (c + 0.5) / field.cols;
                const v = (r + 0.5) / field.rows;
                if (u >= u0 && u <= u1 && v >= v0 && v <= v1)
                    cells.push(Qt.point(u, v));
            }
        }
        const caught = !root.targetCaught && root.targetGlow > 0.5 && root.target.x >= u0 && root.target.x <= u1
                && root.target.y >= v0 && root.target.y <= v1;
        if (caught) {
            root.targetCaught = true;
            respawn.restart();
        }
        if (cells.length === 0)
            return;
        // Refining with the mouse fills the bins too (only for show: the password is not involved), so
        // the 100 % can be reached this way; catching the trembling group counts much more.
        const open = [0, 1, 2, 3, 4].filter(i => root.bins[i] < 1);
        const bin = open.length ? open[Math.floor(Math.random() * open.length)] : Math.floor(Math.random() * 5);
        root.setBin(bin, root.bins[bin] + (caught ? 0.26 : Math.min(0.1, cells.length * 0.006)));
        if (root.reducedMotion)
            return;
        const stride = Math.max(1, Math.ceil(cells.length / 24));
        lidTimer.open(bin);
        for (let i = 0; i < cells.length; i += stride)
            flyer.createObject(screen, { bin: bin, fromX: field.x + cells[i].x * field.width,
                                         fromY: field.y + cells[i].y * field.height, delay: (i / stride) * 35 });
    }

    // ---------------------------------------------------------------- input
    TextInput {
        id: input

        property int previous: 0
        width: 0
        height: 0
        opacity: 0
        echoMode: TextInput.Password
        focus: root.takesInput
        enabled: root.takesInput && root.authState !== "authenticating" && root.authState !== "success" && root.authState !== "maxtries" && !root.leaving
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhHiddenText

        onTextChanged: {
            if (text.length > 0 && deniedHold.running)
                deniedHold.stop();
            if (text.length > previous)
                root.refine();
            else if (text.length === 0)
                root.bins = [0, 0, 0, 0, 0];
            else if (text.length < previous)
                root.unrefine();
            previous = text.length;
        }
        onAccepted: {
            if (text.length === 0)
                return;
            const password = text;
            previous = 0;
            text = "";
            root.submitted(password);
        }
        Keys.onEscapePressed: text = ""
        Keys.onPressed: event => {
            const actions = { [Qt.Key_Tab]: "next", [Qt.Key_Backtab]: "previous", [Qt.Key_F2]: "session",
                              [Qt.Key_F10]: "reboot", [Qt.Key_F12]: "poweroff" };
            if (actions[event.key] !== undefined) {
                root.navigate(actions[event.key]);
                event.accepted = true;
            }
        }
    }

    function focusInput(): void {
        input.forceActiveFocus();
    }

    // Keys typed on another monitor's lock surface (the scene only lives on one), handled as if typed here.
    function relay(event: var): void {
        if (!input.enabled)
            return;
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
            input.accepted();
        else if (event.key === Qt.Key_Backspace)
            input.text = input.text.slice(0, -1);
        else if (event.key === Qt.Key_Escape)
            input.text = "";
        else if (event.text.length > 0 && event.text >= " ")
            input.text += event.text;
    }

    function clearForPreview(): void {
        input.text = "";
    }

    // Vista previa only: drags a box over the numbers, then lets go of it.
    function selectForPreview(u0: real, v0: real, u1: real, v1: real): void {
        pointer.fromU = u0;
        pointer.fromV = v0;
        pointer.u = u1;
        pointer.v = v1;
        pointer.dragging = true;
    }

    function selectTargetForPreview(): void {
        root.selectForPreview(root.target.x - 0.1, root.target.y - 0.12, root.target.x + 0.1, root.target.y + 0.12);
    }

    function releaseForPreview(): void {
        pointer.dragging = false;
        root.harvest(Math.min(pointer.fromU, pointer.u), Math.min(pointer.fromV, pointer.v),
                     Math.max(pointer.fromU, pointer.u), Math.max(pointer.fromV, pointer.v));
    }

    // Vista previa only: fills the field with placeholder characters to show the typing state.
    function typeForPreview(count: int): void {
        for (let i = 0; i < count; i++)
            input.text += "x";
    }

    // ---------------------------------------------------------------- pieces
    Component {
        id: flyer

        Text {
            id: digit

            required property int bin
            required property real fromX
            required property real fromY
            required property real delay
            property real t: 0
            readonly property var target: binRepeater.itemAt(bin)
            readonly property real toX: target ? binsRow.x + target.x + target.width / 2 : fromX
            readonly property real toY: target ? binsRow.y + target.height * 0.3 : fromY

            text: String(Math.floor(Math.random() * 10))
            color: root.tone
            font.family: root.mono
            font.pixelSize: root.unit * 0.03 * (1.4 - t * 0.8)
            x: fromX + (toX - fromX) * t - width / 2
            y: fromY + (toY - fromY) * t * t - root.unit * 0.08 * Math.sin(t * Math.PI) - height / 2
            opacity: 1 - t * 0.6

            SequentialAnimation {
                running: true
                PauseAnimation { duration: digit.delay }
                NumberAnimation { target: digit; property: "t"; to: 1; duration: 620; easing.type: Easing.InOutCubic }
                ScriptAction { script: digit.destroy() }
            }
        }
    }

    Component {
        id: fountain

        Text {
            id: spark

            required property real originX
            required property real originY
            required property real spreadX
            required property real rise
            required property real delay
            property real t: 0

            text: String(Math.floor(Math.random() * 10))
            color: root.tone
            font.family: root.mono
            font.pixelSize: root.unit * 0.026
            x: originX + spreadX * Math.sin(t * Math.PI * 0.5) - width / 2
            // Up and back down into the bin.
            y: originY - rise * 4 * t * (1 - t) - height / 2
            opacity: t < 0.85 ? 1 : (1 - t) / 0.15

            SequentialAnimation {
                running: true
                PauseAnimation { duration: spark.delay }
                NumberAnimation { target: spark; property: "t"; to: 1; duration: 900; easing.type: Easing.Linear }
                ScriptAction { script: spark.destroy() }
            }
        }
    }

    component DoubleRule: Item {
        x: screen.margin
        width: screen.width - screen.margin * 2
        height: root.stroke * 4

        Rectangle {
            width: parent.width
            height: root.stroke
            color: root.tone
        }
        Rectangle {
            y: root.stroke * 3
            width: parent.width
            height: root.stroke
            color: root.tone
        }
    }
}
