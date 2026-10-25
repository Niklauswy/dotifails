pragma ComponentBehavior: Bound

// Renders the boot screens' art for system/boot/render_assets.py (a development tool, never part of a
// running screen). It walks its targets, saves PNGs into WYSUN_BOOT_ART_OUT and quits.
//   grub-background       the training tape's title card (CardMark, vhs.frag); GRUB lists the programs on it
//   plymouth-background   the office terminal (crt.frag) with the file's header on its glass
//   card-N, flip-N-K      the project index: card N resting, then card N falling to uncover N+1 (filebox.frag)
//   click, fade-K         Cold Harbor chosen: its card lights up, then the folder dissolves
//   dialog, pass-K        the terminal's own passphrase program: the window and the field with K bullets
//   field-a, field-b      the sparse data left on the glass once the file is open
//   pointer               the terminal's cursor, which Plymouth moves around the file
//   status-*, glyph-*     the status lines and the address digits, already in phosphor
//   mascot-*, balloon-*   the farewell: the mascot's walk, turn, wave, idle and hop poses, its speech
//   shadow                balloons and its shadow; Plymouth moves them around the glass
// Everything Plymouth shows goes through phosphor.frag: coarse pixels, dithered levels, scanlines.

import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Quickshell
import "../lockscreen"

Item {
    id: root

    required property LockPalette scheme
    property string out: Quickshell.env("WYSUN_BOOT_ART_OUT") || ""
    property string shaderDir: Quickshell.env("WYSUN_BOOT_ART_SHADERS") || ""
    property string mono: Quickshell.env("WYSUN_BOOT_ART_MONO") || "monospace"
    property string sans: Quickshell.env("WYSUN_BOOT_ART_SANS") || "sans-serif"
    property string target: ""
    readonly property color base: scheme.surface
    readonly property color ink: scheme.pick("info", scheme.primary)
    readonly property color text: scheme.text
    readonly property color card: scheme.pick("card", scheme.primary)

    // Frames per falling card, of the dissolve and bullets of the passphrase; orbit.script.in expects them.
    readonly property int flipFrames: 4
    readonly property int fadeFrames: 4
    readonly property int passFrames: 17
    // The glass on the 1920x1080 canvas; orbit.script.in places its sprites from the same numbers.
    readonly property point glassCentre: Qt.point(930, 540)
    readonly property size glassHalf: Qt.size(585, 395)

    width: 1920
    height: 1080

    // The old tube: every Plymouth piece is rendered through it (cell size and brightness steps).
    component Phosphor: ShaderEffect {
        property vector2d res: Qt.vector2d(width, height)
        property real cell: 3
        property real levels: 5
        fragmentShader: "file://" + root.shaderDir + "/phosphor.frag.qsb"
    }

    readonly property var statuses: ({
            "browsing": "BROWSING PROJECT FILES",
            "opening": "OPENING FILE  ·  COLD HARBOR",
            "loading": "LOADING FILE  ·  PLEASE WAIT",
            "ready": "FILE READY",
            "closing": "GOOD WORK.  HAVE A GREAT DAY.",
            "reboot": "GOOD WORK.  SEE YOU IN A MOMENT.",
            "maintenance": "MAINTENANCE IN PROGRESS",
            "skip": "PRESS ANY KEY TO SKIP"
        })
    // The farewell: frames per motion (orbit.script.in expects the same numbers) and what the balloon says.
    readonly property int walkFrames: 12
    readonly property real walkTurn: 0.3
    readonly property int turnFrames: 4
    readonly property int waveFrames: 16
    readonly property int idleFrames: 8
    readonly property int hopFrames: 10
    readonly property var moods: ["cheer", "woe", "frolic", "dread"]
    readonly property var balloons: ({
            "goodbye": "GOODBYE!",
            "tomorrow": "SEE YOU TOMORROW!",
            "thanks": "THANK YOU FOR YOUR WORK",
            "back": "BE RIGHT BACK!",
            "miss": "I'LL MISS YOU...",
            "dark": "LIGHTS OUT?!",
            "moment": "JUST A MOMENT..."
        })
    readonly property var glyphs: ({
            "x": "x",
            "colon": ":"
        })

    component Glow: MultiEffect {
        shadowEnabled: true
        shadowColor: root.ink
        shadowBlur: 0.7
        shadowOpacity: 0.9
        shadowHorizontalOffset: 0
        shadowVerticalOffset: 0
    }

    // ---------------------------------------------------------------- the training tape (GRUB)
    Item {
        id: tape
        width: 1920
        height: 1080
        visible: root.target === "grub-background"

        Item {
            id: titleCard
            anchors.fill: parent
            visible: false

            Rectangle {
                anchors.fill: parent
                color: root.card
            }
            CardMark {
                x: 960 - width / 2
                y: 110
                width: 470
                height: 250
                colour: root.text
                fill: root.card
                family: root.sans
            }
            Text {
                x: 0
                y: 400
                width: 1920
                horizontalAlignment: Text.AlignHCenter
                text: "WYSUN MANAGEMENT PROGRAM"
                color: root.text
                font.family: root.sans
                font.pixelSize: 50
                font.weight: Font.Bold
                font.letterSpacing: -0.5
            }
            Rectangle {
                x: 960 - width / 2
                y: 474
                width: 760
                height: 4
                color: Qt.alpha(root.text, 0.55)
            }
            Text {
                x: 0
                y: 930
                width: 1920
                horizontalAlignment: Text.AlignHCenter
                text: "THE FOLLOWING SESSION IS INTENDED FOR SEVERED STAFF ONLY.\nPLEASE SELECT A PROGRAM.  ↑ ↓ CHOOSE   ·   ENTER BEGIN   ·   E EDIT   ·   C CONSOLE"
                color: root.text
                font.family: root.sans
                font.pixelSize: 22
                font.weight: Font.Bold
                lineHeight: 1.15
            }
        }

        ShaderEffect {
            anchors.fill: parent
            property vector2d res: Qt.vector2d(width, height)
            property var source: ShaderEffectSource {
                sourceItem: titleCard
                hideSource: true
                live: true
            }
            fragmentShader: "file://" + root.shaderDir + "/vhs.frag.qsb"
        }
    }

    // ---------------------------------------------------------------- the terminal (Plymouth)
    Item {
        id: terminal
        width: 1920
        height: 1080
        visible: stage.scene === terminal

        ShaderEffect {
            anchors.fill: parent
            property vector2d res: Qt.vector2d(width, height)
            property vector2d glassCentre: Qt.vector2d(root.glassCentre.x, root.glassCentre.y)
            property vector2d glassHalf: Qt.vector2d(root.glassHalf.width, root.glassHalf.height)
            property color room: Qt.tint(Qt.darker(root.base, 1.5), Qt.alpha(root.scheme.pick("success", root.ink), 0.16))
            property color shell: Qt.tint(root.text, Qt.alpha(root.scheme.pick("warning", root.text), 0.14))
            property color bezel: Qt.tint(root.base, Qt.alpha(root.text, 0.1))
            property color glass: Qt.tint(Qt.darker(root.base, 1.15), Qt.alpha(root.ink, 0.16))
            property color glare: root.text
            fragmentShader: "file://" + root.shaderDir + "/crt.frag.qsb"
        }

        // The file's header on the glass: its name, the progress gauge (filled by Plymouth) and the mark.
        Item {
            anchors.fill: parent
            layer.enabled: true
            layer.effect: Glow {}

            Text {
                x: 420
                y: 195 - height / 2
                text: "Project Files"
                color: root.ink
                font.family: root.sans
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Rectangle {
                x: 640
                y: 182
                width: 620
                height: 26
                color: "transparent"
                border.color: root.ink
                border.width: 2
                radius: 3
            }
            WysunMark {
                x: 1305
                y: 195 - height / 2
                height: 54
                width: height * 1.9
                colour: root.ink
                fill: "transparent"
                stroke: 2
                spin: 0.5
                family: root.mono
            }
            Rectangle {
                x: 420
                y: 236
                width: 1020
                height: 2
                color: Qt.alpha(root.ink, 0.55)
            }
        }
    }

    // ---------------------------------------------------------------- the file
    Item {
        id: file

        property real flip: 0
        property real lit: 0
        property real fade: 0
        property string name: ""
        property string nextName: ""
        // filebox.frag's units in pixels, its hinge line, and the falling card's angle.
        readonly property real unit: height
        readonly property real hinge: height / 2 - 0.03 * unit
        readonly property real angle: flip * Math.PI
        readonly property real labelX: width / 2 - 0.2 * unit
        readonly property real labelY: hinge - 0.24 * unit
        width: 440
        height: 440
        visible: stage.scene === file

        ShaderEffect {
            anchors.fill: parent
            property real aspect: width / height
            property real flip: file.flip
            property real lit: file.lit
            property real fade: file.fade
            property color ink: root.ink
            property color core: root.text
            fragmentShader: "file://" + root.shaderDir + "/filebox.frag.qsb"
        }

        component Label: Text {
            color: Qt.tint(root.ink, Qt.alpha(root.text, 0.3 + 0.5 * file.lit))
            opacity: 1 - file.fade
            font.family: root.sans
            font.pixelSize: 0.068 * file.unit
            font.weight: Font.DemiBold
            layer.enabled: true
            layer.effect: Glow {}
        }

        // The card underneath (the next project), hidden below the falling card's free edge.
        Item {
            width: file.width
            height: file.flip > 0 && file.flip < 0.5 ? file.hinge - 0.33 * file.unit * Math.cos(file.angle) : file.height
            clip: true

            Label {
                x: file.labelX
                y: file.labelY
                text: file.flip > 0 ? file.nextName : file.name
            }
        }

        // The falling card's name, squashed towards the hinge with it (same motion as filebox.frag).
        Label {
            id: fallingLabel
            x: file.labelX
            y: file.labelY
            visible: file.flip > 0 && file.flip < 0.5
            text: file.name
            transform: Scale {
                origin.x: file.width / 2 - fallingLabel.x
                origin.y: file.hinge - fallingLabel.y
                xScale: 1 + 0.18 * Math.sin(file.angle) * 0.7
                yScale: Math.max(Math.cos(file.angle), 0.02)
            }
        }
    }

    // ---------------------------------------------------------------- the farewell
    // The mascot, one pose per frame (mascot.frag); Plymouth moves it around the glass.
    ShaderEffect {
        id: mascot
        width: 360
        height: 400
        visible: stage.scene === mascot
        property real aspect: width / height
        property real turn: 0
        property real walk: 0
        property real stride: 0
        property real wave: 0
        property real waving: 0
        property real squash: 0
        property real tuck: 0
        property real talk: 0
        property real blink: 0
        property real mood: 0
        property color ink: root.ink
        property color core: root.text
        property color base: root.base
        fragmentShader: "file://" + root.shaderDir + "/mascot.frag.qsb"

        function pose(name: string): void {
            const parts = name.split("-");
            const kind = parts[1];
            const n = parseInt(parts[parts.length - 1]);
            turn = 0; walk = 0; stride = 0; wave = 0; waving = 0; squash = 0; tuck = 0; talk = 0; blink = 0; mood = 0;
            if (kind === "walk") {
                turn = (parts[2] === "r" ? 1 : -1) * root.walkTurn;
                walk = n / root.walkFrames;
                stride = 1;
            } else if (kind === "turn") {
                // From the walking three-quarter view (0) to facing the viewer (last).
                turn = (parts[2] === "r" ? 1 : -1) * root.walkTurn * (1 - (n + 1) / (root.turnFrames + 1));
            } else if (kind === "wave") {
                waving = Math.min(1, n / 3, (root.waveFrames - n) / 3 + 0.4);
                wave = n / root.waveFrames * 2;
                talk = 0.5 + 0.5 * Math.sin(n * 1.9);
            } else if (kind === "idle") {
                // Breathing in a temper: idle-woe-N, idle-dread-N…
                mood = root.moods.indexOf(parts[2]);
                squash = (mood === 1 ? 0.03 : 0.05) * Math.sin(n / root.idleFrames * 2 * Math.PI);
                blink = n === 5 ? 1 : n === 4 || n === 6 ? 0.5 : 0;
                talk = mood === 0 ? 0.5 + 0.5 * Math.sin(n * 1.7) : 0;
            } else if (kind === "hop") {
                // Anticipation, launch, air, landing, recovery.
                const squashes = [-0.35, -0.6, 0.55, 0.25, 0.1, 0.15, 0.4, -0.55, -0.25, 0];
                const tucks = [0, 0, 0.2, 0.8, 1, 0.8, 0.3, 0, 0, 0];
                squash = squashes[n];
                tuck = tucks[n];
                mood = n >= 2 ? 2 : 0;
                talk = n >= 2 && n <= 6 ? 1 : 0.2;
            }
        }
    }

    // A speech balloon with its tail towards the mascot's head.
    Item {
        id: balloon

        property string content: ""
        width: balloonText.implicitWidth + 80
        height: 130
        visible: stage.scene === balloon
        layer.enabled: true
        layer.effect: Glow {}

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: root.ink
                strokeWidth: 4
                fillColor: Qt.darker(root.base, 1.3)
                joinStyle: ShapePath.RoundJoin
                startX: 24; startY: 6
                PathLine { x: balloon.width - 24; y: 6 }
                PathQuad { x: balloon.width - 6; y: 24; controlX: balloon.width - 6; controlY: 6 }
                PathLine { x: balloon.width - 6; y: 76 }
                PathQuad { x: balloon.width - 24; y: 94; controlX: balloon.width - 6; controlY: 94 }
                PathLine { x: 70; y: 94 }
                PathLine { x: 22; y: 124 }
                PathLine { x: 40; y: 94 }
                PathLine { x: 24; y: 94 }
                PathQuad { x: 6; y: 76; controlX: 6; controlY: 94 }
                PathLine { x: 6; y: 24 }
                PathQuad { x: 24; y: 6; controlX: 6; controlY: 6 }
            }
        }
        Text {
            id: balloonText
            x: 40
            y: 50 - height / 2
            text: balloon.content
            color: Qt.tint(root.ink, Qt.alpha(root.text, 0.4))
            font.family: root.mono
            font.pixelSize: 32
            font.bold: true
        }
    }

    // The mascot's shadow on the floor of the glass.
    Item {
        id: shadow
        width: 220
        height: 50
        visible: stage.scene === shadow

        Rectangle {
            anchors.centerIn: parent
            width: 180
            height: 26
            radius: 13
            color: Qt.alpha(root.ink, 0.35)
            layer.enabled: true
            layer.effect: MultiEffect {
                blurEnabled: true
                blur: 0.6
                blurMax: 16
            }
        }
    }

    // ---------------------------------------------------------------- the passphrase program
    Item {
        id: dialog

        property int bullets: -1
        width: bullets < 0 ? 760 : 680
        height: bullets < 0 ? 260 : 50
        visible: stage.scene === dialog

        // The window: a double frame, a title bar in reverse video, the request and an empty field.
        Item {
            anchors.fill: parent
            visible: dialog.bullets < 0
            layer.enabled: true
            layer.effect: Glow {}

            Rectangle {
                anchors.fill: parent
                anchors.margins: 4
                color: "transparent"
                border.color: root.ink
                border.width: 3
            }
            Rectangle {
                anchors.fill: parent
                anchors.margins: 12
                color: "transparent"
                border.color: Qt.alpha(root.ink, 0.6)
                border.width: 2
            }
            Rectangle {
                x: 12
                y: 12
                width: parent.width - 24
                height: 44
                color: root.ink
                Text {
                    anchors.centerIn: parent
                    text: "WYSUN  ·  ENCRYPTED VOLUME"
                    color: Qt.darker(root.base, 1.2)
                    font.family: root.mono
                    font.pixelSize: 24
                    font.bold: true
                }
            }
            Text {
                x: 40
                y: 88
                text: "ENTER PASSPHRASE TO CONTINUE"
                color: root.ink
                font.family: root.mono
                font.pixelSize: 26
                font.bold: true
            }
            Rectangle {
                x: 40
                y: 176
                width: 680
                height: 50
                color: "transparent"
                border.color: root.ink
                border.width: 2
            }
        }

        // The field's content: K bullets and the cursor.
        Text {
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            visible: dialog.bullets >= 0
            text: "• ".repeat(Math.max(dialog.bullets, 0)) + "█"
            color: root.ink
            font.family: root.mono
            font.pixelSize: 26
            layer.enabled: true
            layer.effect: Glow {}
        }
    }

    // ---------------------------------------------------------------- the data field
    // Sparse phosphor dots left on the glass once the file is open; Plymouth crossfades two of them.
    Item {
        id: field

        property int seed: 1
        width: 1060
        height: 500
        visible: stage.scene === field
        layer.enabled: true
        layer.effect: Glow {}

        Repeater {
            model: 70
            Rectangle {
                required property int index
                readonly property real a: Math.abs(Math.sin((index + 1) * 12.9898 * field.seed) * 43758.5453) % 1
                readonly property real b: Math.abs(Math.sin((index + 1) * 78.233 * field.seed) * 24634.6345) % 1
                x: a * (field.width - 12) + 4
                y: b * (field.height - 12) + 4
                width: index % 7 === 0 ? 6 : 4
                height: width
                color: root.ink
                opacity: 0.45 + 0.55 * ((a + b) % 1)
            }
        }
    }

    // ---------------------------------------------------------------- the cursor
    Item {
        id: pointer
        width: 48
        height: 60
        visible: stage.scene === pointer

        Shape {
            layer.enabled: true
            layer.effect: Glow {}
            x: 12
            y: 10
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Qt.tint(root.ink, Qt.alpha(root.text, 0.3))
                strokeColor: "transparent"
                startX: 0; startY: 0
                PathLine { x: 0; y: 30 }
                PathLine { x: 8; y: 23 }
                PathLine { x: 13; y: 34 }
                PathLine { x: 18; y: 32 }
                PathLine { x: 13; y: 21 }
                PathLine { x: 22; y: 21 }
                PathLine { x: 0; y: 0 }
            }
        }
    }

    // ---------------------------------------------------------------- status lines and digits
    Item {
        id: caption

        property string content: ""
        property bool small: false
        width: small ? 20 : captionText.implicitWidth + 30
        height: small ? 34 : 48
        visible: stage.scene === caption

        Text {
            id: captionText
            anchors.centerIn: parent
            text: caption.content
            color: caption.small ? Qt.alpha(root.ink, 0.8) : root.ink
            font.family: root.mono
            font.pixelSize: caption.small ? 26 : 28
            font.bold: !caption.small
            layer.enabled: true
            layer.effect: Glow {}
        }
    }

    // ---------------------------------------------------------------- the tube
    // The piece being rendered, seen through phosphor.frag; this is what gets saved.
    Item {
        id: stage

        property Item scene: null
        property real levels: 5
        width: scene ? scene.width : 1
        height: scene ? scene.height : 1
        visible: scene !== null

        Phosphor {
            anchors.fill: parent
            levels: stage.levels
            property var source: ShaderEffectSource {
                sourceItem: stage.scene
                hideSource: true
                live: true
            }
        }
    }

    // ---------------------------------------------------------------- walk
    function frameName(prefix: string, index: int): string {
        return prefix + (index < 10 ? "0" : "") + index;
    }

    readonly property var projects: ["Allentown", "Astoria", "Bellingham", "Cielo", "Tumwater", "Cold Harbor"]

    readonly property var targets: {
        const list = ["grub-background", "plymouth-background", "pointer", "field-a", "field-b", "dialog"];
        for (const key in statuses)
            list.push("status-" + key);
        for (const digit of "0123456789ABCDEF")
            list.push("glyph-" + digit);
        for (const key in glyphs)
            list.push("glyph-" + key);
        for (let i = 0; i < projects.length; i++)
            list.push("card-" + i);
        for (let i = 0; i + 1 < projects.length; i++)
            for (let k = 1; k <= flipFrames; k++)
                list.push("flip-" + i + "-" + k);
        list.push("click");
        for (let k = 1; k <= fadeFrames; k++)
            list.push("fade-" + k);
        for (let k = 0; k < passFrames; k++)
            list.push("pass-" + k);
        for (const side of ["r", "l"]) {
            for (let k = 0; k < walkFrames; k++)
                list.push("mascot-walk-" + side + "-" + k);
            for (let k = 0; k < turnFrames; k++)
                list.push("mascot-turn-" + side + "-" + k);
        }
        for (let k = 0; k < waveFrames; k++)
            list.push("mascot-wave-" + k);
        for (const mood of moods)
            for (let k = 0; k < idleFrames; k++)
                list.push("mascot-idle-" + mood + "-" + k);
        for (let k = 0; k < hopFrames; k++)
            list.push("mascot-hop-" + k);
        for (const key in balloons)
            list.push("balloon-" + key);
        list.push("shadow");
        const only = Quickshell.env("WYSUN_BOOT_FAREWELL_ONLY") === "1";
        return only ? list.filter(name => /^(mascot-|balloon-|shadow|status-closing|status-reboot|status-skip)/.test(name)) : list;
    }
    property int step: -1

    function next(): void {
        step++;
        if (step >= targets.length) {
            Qt.quit();
            return;
        }
        target = targets[step];
        const isFile = /^(card|flip|click|fade)/.test(target);
        stage.scene = target.startsWith("mascot-") ? mascot : target.startsWith("balloon-") ? balloon : target === "shadow" ? shadow : target === "grub-background" ? null : target === "plymouth-background" ? terminal : target === "pointer" ? pointer : target.indexOf("field-") === 0 ? field : target === "dialog" || target.indexOf("pass-") === 0 ? dialog : isFile ? file : caption;
        stage.levels = target === "plymouth-background" ? 14 : 5;
        if (target.startsWith("mascot-")) {
            mascot.pose(target);
        } else if (target.startsWith("balloon-")) {
            balloon.content = balloons[target.slice(8)];
        } else if (isFile) {
            const parts = target.split("-");
            const last = projects.length - 1;
            file.lit = target === "click" || target.indexOf("fade-") === 0 ? 1 : 0;
            file.fade = target.indexOf("fade-") === 0 ? parseInt(parts[1]) / fadeFrames : 0;
            file.flip = target.indexOf("flip-") === 0 ? parseInt(parts[2]) / (flipFrames + 1) : 0;
            const index = target.indexOf("card-") === 0 || target.indexOf("flip-") === 0 ? parseInt(parts[1]) : last;
            file.name = projects[index];
            file.nextName = projects[Math.min(index + 1, last)];
        } else if (target === "dialog") {
            dialog.bullets = -1;
        } else if (target.indexOf("pass-") === 0) {
            dialog.bullets = parseInt(target.slice(5));
        } else if (target.indexOf("field-") === 0) {
            field.seed = target === "field-a" ? 1 : 2;
        } else if (target.indexOf("status-") === 0) {
            caption.small = false;
            caption.content = statuses[target.slice(7)];
        } else if (target.indexOf("glyph-") === 0) {
            const key = target.slice(6);
            caption.small = true;
            caption.content = glyphs[key] || key;
        }
        settle.restart();
    }

    Timer {
        id: settle
        interval: root.target.startsWith("mascot-") ? 60 : 300
        onTriggered: {
            const item = root.target === "grub-background" ? tape : stage;
            item.grabToImage(result => {
                result.saveToFile(root.out + "/" + root.target + ".png");
                root.next();
            });
        }
    }

    Component.onCompleted: next()
}
