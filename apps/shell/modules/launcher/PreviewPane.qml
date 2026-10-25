pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtMultimedia
import Quickshell.Io
import M3Shapes
import Wysun.Config
import qs.components
import qs.services
import qs.modules.launcher.services
import "services/Files.js" as Files
import "services/Colour.js" as Colour
import "services/Content.js" as Content

// Type-aware preview of the selected file or clipboard entry. Each kind gets its own
// stage: images over a blurred copy of themselves, videos playing muted on a loop, a page for
// PDFs, numbered lines for code, rendered Markdown, a folder's contents, a colour swatch, a link
// card. Title and metadata chips sit underneath. Only the selected entry is ever inspected.
Item {
    id: root

    property var row: null
    property real scale: 1
    property bool expanded: false
    readonly property bool expandable: ["image", "video"].includes(mode)
    signal expandRequested()
    signal collapseRequested()
    property bool focusedPane
    // Final pixel size requested from the image decoder, independent of the open animation.
    property size decodeSize: Qt.size(640, 400)

    readonly property font small: Tokens.font.body.builders.small.size(9 * scale).weight(Font.Medium).build()
    readonly property font body: Tokens.font.body.builders.medium.size(10 * scale).build()

    readonly property alias stage: stage
    readonly property bool isFile: row?.kind === "file"
    readonly property bool isClip: row?.kind === "clip"
    readonly property string ext: isFile ? Files.extension(row.path) : ""
    readonly property string fileIcon: isFile ? Files.icon(row.path, row.isDir) : ""
    // One stage per kind of content.
    readonly property string mode: {
        if (!row)
            return "none";
        if (isFile) {
            if (row.isDir) return "folder";
            if (fileIcon === "image") return "image";
            if (fileIcon === "movie") return "video";
            if (fileIcon === "music_note") return "audio";
            if (fileIcon === "picture_as_pdf") return "page";
            if (ext === "md" || ext === "markdown") return "markdown";
            if (fileIcon === "code") return "code";
            if (fileIcon === "description") return "text";
            // Anything Neovim would open (unknown extensions, backups, dotfiles) previews as text when it is text.
            return row.editable ? "code" : "other";
        }
        if (isClip)
            return {image: "image", color: "color", url: "link"}[row.clip_kind] ?? Content.textKind(row.value);
        return "other";
    }

    property string imageSource
    property string bodyText
    // Neovim-coloured rendering of code files (from nvim_theme.py); empty when no Neovim theme is configured.
    property string codeHtml
    // Lines in the whole file; the preview itself stops after the first ones (code_preview.py).
    property int codeLines
    property color codeBg
    property color codeFg
    property color codeLineNr
    // NvChad's `transparency = true`: Neovim draws no background of its own, so neither does the preview.
    property bool codeTransparent
    readonly property bool nvimStyled: mode === "code" && codeHtml !== ""
    property var meta: ({})
    property var linkCache: ({})
    // Code previews already coloured this session, by path: {data, modified}. Arrowing back to a
    // file shows it at once; the stat answer re-runs the preview only if the file changed meanwhile.
    property var codeCache: ({})
    property var folderItems: []
    // Zoom of the picture stage: 1 = fit. panX/panY move the scaled picture inside the frame.
    // zoom/panX/panY are targets; the shown* copies glide to them on the same short curve.
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property real shownZoom: zoom
    property real shownPanX: panX
    property real shownPanY: panY

    Behavior on shownZoom {
        Anim {
            type: Anim.FastEffects
        }
    }
    Behavior on shownPanX {
        Anim {
            type: Anim.FastEffects
        }
    }
    Behavior on shownPanY {
        Anim {
            type: Anim.FastEffects
        }
    }

    // Keep the point under (cx, cy) still while scaling; never let the picture leave the frame.
    function zoomBy(factor: real, cx: real, cy: real): void {
        if (!["image", "page"].includes(mode))
            return;
        const old = zoom, next = Math.max(1, Math.min(8, old * factor));
        if (next === old)
            return;
        const x = cx ?? zoomArea.width / 2, y = cy ?? zoomArea.height / 2;
        zoom = next;
        panTo(x - (x - panX) * next / old, y - (y - panY) * next / old);
    }

    function panTo(x: real, y: real): void {
        panX = Math.min(0, Math.max(zoomArea.width - zoomArea.width * zoom, x));
        panY = Math.min(0, Math.max(zoomArea.height - zoomArea.height * zoom, y));
    }

    // Ctrl+Space / the play button: audio sounds or pauses; videos (always muted) pause too.
    function togglePlayback(): void {
        autoplay.stop();
        if (mode === "audio")
            sound.playbackState === MediaPlayer.PlayingState ? sound.pause() : sound.play();
        else if (mode === "video")
            video.playbackState === MediaPlayer.PlayingState ? video.pause() : video.play();
    }

    function resetZoom(): void {
        zoom = 1;
        panX = 0;
        panY = 0;
    }
    property int folderCount: -1
    property string stamp: row ? row.key : ""

    onStampChanged: {
        imageSource = "";
        bodyText = "";
        codeHtml = "";
        codeLines = 0;
        meta = mode === "link" ? (linkCache[row.value.trim()] || {}) : {};
        folderItems = [];
        folderCount = -1;
        resetZoom();
        webProc.running = false;
        autoplay.stop();
        sound.stop();
        sound.source = "";
        video.stop();
        video.source = "";
        contentIn.restart();
        debounce.restart();
    }

    function when(seconds: real): string {
        return Qt.formatDateTime(new Date(seconds * 1000), "d MMM yyyy · HH:mm");
    }

    function size(bytes: real): string {
        if (bytes < 1024)
            return bytes + " B";
        const units = ["KB", "MB", "GB", "TB"];
        let v = bytes / 1024, i = 0;
        while (v >= 1024 && i < units.length - 1) {
            v /= 1024;
            i++;
        }
        return v.toFixed(v < 10 ? 1 : 0) + " " + units[i];
    }

    function duration(seconds: real): string {
        const n = Math.max(0, Math.round(seconds || 0));
        const mm = Math.floor(n % 3600 / 60), ss = String(n % 60).padStart(2, "0");
        return n >= 3600 ? `${Math.floor(n / 3600)}:${String(mm).padStart(2, "0")}:${ss}` : `${mm}:${ss}`;
    }

    // Metadata chips: [icon, text] pairs, built from whatever is known for this kind.
    readonly property var chips: {
        const out = [], m = meta, r = row;
        if (!r)
            return out;
        if (m.width && m.height) out.push(["aspect_ratio", `${m.width} × ${m.height}`]);
        else if (r.width && r.height) out.push(["aspect_ratio", `${r.width} × ${r.height}`]);
        if (m.duration) out.push(["schedule", duration(m.duration)]);
        if (m.codec_name) out.push(["movie", String(m.codec_name).toUpperCase()]);
        if (m.audio_codec) out.push(["graphic_eq", String(m.audio_codec).toUpperCase()]);
        if (m.pages) out.push(["description", m.pages + (m.pages === 1 ? " page" : " pages")]);
        if (mode === "code" || mode === "text" || mode === "markdown")
            if (bodyText) out.push(["format_list_numbered", (codeLines || bodyText.split("\n").length) + " lines"]);
        if (mode === "folder" && folderCount >= 0) out.push(["folder", folderCount + (folderCount === 1 ? " item" : " items")]);
        if (m.size !== undefined) out.push(["save", size(m.size)]);
        if (m.modified) out.push(["edit_calendar", when(m.modified)]);
        if (isClip) {
            if (r.clip_kind !== "image" && r.value) out.push(["text_fields", r.value.length + " characters"]);
            out.push(["content_paste", when(r.stamp)]);
        }
        return out;
    }

    function describe(): void {
        const r = row;
        if (!r)
            return;
        if (isFile) {
            statProc.running = false;
            statProc.command = ["stat", "-L", "-c", "%s|%Y", r.path];
            statProc.running = true;
            if (mode === "image")
                imageSource = "file://" + r.path;
            else if (mode === "folder") {
                listProc.command = ["find", r.path, "-mindepth", "1", "-maxdepth", "1", "-not", "-name", ".*", "-printf", "%y\t%f\n"];
                listProc.running = true;
            } else if (mode === "code") {
                const hit = codeCache[r.path];
                if (hit)
                    showCode(hit.data);
                else
                    runCode(r.path);
            } else if (["text", "markdown"].includes(mode)) {
                headProc.running = false;
                headProc.command = ["head", "-c", "12000", r.path];
                headProc.running = true;
            } else if (["video", "audio", "page"].includes(mode)) {
                pyProc.command = ["python3", "-I", LauncherData.script, "preview", r.path];
                pyProc.running = true;
                if (mode === "video") {
                    video.source = "file://" + r.path;
                    video.play();
                } else if (mode === "audio") {
                    sound.source = "file://" + r.path;
                    autoplay.restart();
                }
            }
        } else if (isClip && r.clip_kind === "image") {
            if (r.thumb)
                imageSource = "file://" + r.thumb;
            else
                LauncherIndex.exportClip(r.id, path => {
                    if (root.row?.key === r.key)
                        root.imageSource = "file://" + path;
                });
        } else if (isClip) {
            bodyText = r.value ?? "";
            if (mode === "link") {
                if (linkCache[bodyText.trim()]) {
                    meta = linkCache[bodyText.trim()];
                    return;
                }
                webProc.requestKey = r.key;
                webProc.command = ["python3", "-I", LauncherData.script, "preview-url", bodyText.trim()];
                webProc.running = true;
            }
        }
    }

    function runCode(path: string): void {
        codeProc.running = false;
        codeProc.path = path;
        codeProc.command = LauncherData.codePreview(path);
        codeProc.running = true;
    }

    function showCode(d: var): void {
        bodyText = d.text ?? "";
        codeLines = d.lines ?? 0;
        if (d.html) {
            codeBg = d.bg;
            codeFg = d.fg;
            codeLineNr = d.lineNr;
            codeTransparent = !!d.transparent;
            codeHtml = d.html;
        }
    }

    Timer {
        id: debounce

        interval: root.mode === "link" ? 160 : 90
        onTriggered: root.describe()
    }

    Process {
        id: statProc

        stdout: StdioCollector {
            onStreamFinished: {
                const p = text.trim().split("|");
                if (p.length < 2 || !root.isFile)
                    return;
                const modified = parseInt(p[1]);
                root.meta = Object.assign({}, root.meta, {size: parseInt(p[0]), modified});
                const hit = root.mode === "code" ? root.codeCache[root.row.path] : null;
                if (hit && hit.modified !== modified)
                    root.runCode(root.row.path);
            }
        }
    }

    Process {
        id: headProc

        stdout: StdioCollector {
            onStreamFinished: root.bodyText = text
        }
    }

    Process {
        id: codeProc

        property string path

        stdout: StdioCollector {
            onStreamFinished: {
                let d;
                try {
                    d = JSON.parse(text);
                } catch (e) {
                    return;
                }
                const cache = root.codeCache;
                if (Object.keys(cache).length >= 40)
                    root.codeCache = {};
                root.codeCache[codeProc.path] = {data: d, modified: root.row?.path === codeProc.path ? root.meta.modified : undefined};
                if (root.row?.path === codeProc.path && root.mode === "code")
                    root.showCode(d);
            }
        }
    }

    Process {
        id: listProc

        stdout: StdioCollector {
            onStreamFinished: {
                const rows = text.split("\n").filter(l => l).map(l => {
                    const tab = l.indexOf("\t");
                    return {dir: l.slice(0, tab) === "d", name: l.slice(tab + 1)};
                });
                rows.sort((a, b) => (b.dir - a.dir) || a.name.localeCompare(b.name));
                root.folderCount = rows.length;
                root.folderItems = rows.slice(0, 60);
            }
        }
    }

    Process {
        id: pyProc

        environment: ({QT_QPA_PLATFORM: "offscreen"})
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse(text);
                    root.imageSource = d.image || "";
                    const m = d.meta || {};
                    delete m.size;
                    delete m.modified;
                    root.meta = Object.assign({}, root.meta, m);
                } catch (e) {}
            }
        }
    }

    Process {
        id: webProc
        property string requestKey
        stdout: SplitParser {
            onRead: line => {
                if (webProc.requestKey !== root.stamp || root.mode !== "link") return;
                try {
                    const data = JSON.parse(line);
                    if (data.url === root.row.value.trim()) {
                        root.meta = data;
                        if (data.status !== "loading-image") {
                            if (Object.keys(root.linkCache).length >= 20) root.linkCache = {};
                            root.linkCache[data.url] = data;
                        }
                    }
                } catch (e) {}
            }
        }
    }

    // Content fades and lifts in on every new selection.
    property real contentProgress: 1

    NumberAnimation {
        id: contentIn

        target: root
        property: "contentProgress"
        from: 0
        to: 1
        duration: Tokens.anim.durations.expressiveDefaultEffects
        easing: Tokens.anim.expressiveDefaultEffects
    }

    // Stage ---------------------------------------------------------------------------------------
    Rectangle {
        id: stage

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: root.expanded || root.mode === "link" ? parent.height : root.mode === "folder" || ["code", "text", "markdown"].includes(root.mode) ? parent.height - details.height - Tokens.spacing.medium : Math.min(parent.height * 0.62, parent.height - details.height - Tokens.spacing.medium)
        radius: Tokens.rounding.large
        color: root.nvimStyled ? (root.codeTransparent ? "transparent" : root.codeBg) : Colours.palette.m3surfaceContainerHigh
        border.width: root.focusedPane ? 2 : 0
        border.color: Colours.palette.m3primary
        clip: true

        Item {
            id: content

            anchors.fill: parent
            opacity: root.contentProgress
            transform: Translate {
                y: (1 - root.contentProgress) * 8
            }

            // Pictures and video posters: the frame floats over a blurred copy of itself.
            Image {
                id: backdrop

                anchors.fill: parent
                visible: ["image", "video", "page"].includes(root.mode) && root.imageSource !== "" && root.mode !== "page"
                source: visible ? root.imageSource : ""
                sourceSize: Qt.size(48, 48)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: false
                layer.enabled: visible
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: 1
                    blurMax: 32
                    saturation: 0.2
                    brightness: -0.12
                }
            }

            // Pictures and PDF pages zoom with the wheel towards the pointer, pan by dragging
            // and fit again on double click. Zoom and pan glide together (same short curve).
            Item {
                id: zoomArea

                readonly property bool zoomable: ["image", "page"].includes(root.mode) && picture.status === Image.Ready

                anchors.fill: parent
                anchors.margins: root.mode === "page" ? Tokens.padding.large : Tokens.padding.small
                clip: true

                Image {
                    id: picture

                    width: zoomArea.width
                    height: zoomArea.height
                    visible: ["image", "page"].includes(root.mode) || (root.mode === "video" && !videoOut.visible)
                    source: visible ? root.imageSource : ""
                    sourceSize: root.decodeSize
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    cache: false
                    opacity: status === Image.Ready ? 1 : 0
                    scale: status === Image.Ready ? 1 : 0.96
                    transform: [
                        Scale {
                            xScale: root.shownZoom
                            yScale: root.shownZoom
                        },
                        Translate {
                            x: root.shownPanX
                            y: root.shownPanY
                        }
                    ]

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                    Behavior on scale {
                        Anim {
                            type: Anim.DefaultSpatial
                        }
                    }
                }

                WheelHandler {
                    enabled: zoomArea.zoomable
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: event => root.zoomBy(Math.pow(1.0018, event.angleDelta.y), point.position.x, point.position.y)
                }
                DragHandler {
                    enabled: zoomArea.zoomable && root.zoom > 1
                    target: null
                    cursorShape: active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    property real startX
                    property real startY
                    onActiveChanged: if (active) {
                        startX = root.panX;
                        startY = root.panY;
                    }
                    onTranslationChanged: root.panTo(startX + translation.x, startY + translation.y)
                }
                TapHandler {
                    enabled: zoomArea.zoomable
                    onTapped: if (!root.expanded && root.expandable) root.expandRequested()
                    onDoubleTapped: root.resetZoom()
                }
            }

            // Video: plays muted on a loop while selected (no audio output is attached).
            MediaPlayer {
                id: video

                loops: MediaPlayer.Infinite
                videoOutput: videoOut
            }
            VideoOutput {
                id: videoOut

                anchors.fill: parent
                anchors.margins: Tokens.padding.small
                visible: root.mode === "video" && video.hasVideo
                fillMode: VideoOutput.PreserveAspectFit
                TapHandler {
                    onTapped: if (!root.expanded) root.expandRequested(); else root.togglePlayback()
                }
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Tokens.padding.medium
                height: 4
                radius: 2
                visible: videoOut.visible && video.duration > 0
                color: Qt.alpha(Colours.palette.m3onSurface, 0.2)

                Rectangle {
                    width: parent.width * Math.min(1, video.position / Math.max(1, video.duration))
                    height: parent.height
                    radius: 2
                    color: Colours.palette.m3primary
                }
            }

            // Audio: plays after a short dwell. The cover (or a note) sits in an M3 shape that
            // turns and breathes while it sounds and morphs between shapes when there is no cover.
            Item {
                id: audioStage

                readonly property bool playing: sound.playbackState === MediaPlayer.PlayingState
                readonly property bool hasCover: root.imageSource !== "" && cover.status === Image.Ready
                readonly property var shapes: [MaterialShape.SoftBurst, MaterialShape.Cookie9Sided, MaterialShape.Sunny, MaterialShape.Cookie12Sided, MaterialShape.Clover4Leaf]
                property int shapeIndex
                property real spin
                property real beat

                anchors.fill: parent
                visible: root.mode === "audio"

                // Only runs while audio plays and the stage is shown.
                FrameAnimation {
                    running: audioStage.visible && audioStage.playing
                    onTriggered: {
                        audioStage.spin = (audioStage.spin + frameTime * 24) % 360;
                        audioStage.beat = (audioStage.beat + frameTime * 2.2) % (Math.PI * 2);
                    }
                }
                Timer {
                    running: audioStage.visible && audioStage.playing && !audioStage.hasCover
                    interval: 1600
                    repeat: true
                    onTriggered: audioStage.shapeIndex = (audioStage.shapeIndex + 1) % audioStage.shapes.length
                }

                Item {
                    id: disc

                    readonly property real size: Math.min(parent.width * 0.62, parent.height - controls.height - Tokens.padding.extraLarge * 2)

                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: (parent.height - size - controls.height - Tokens.spacing.large) / 2
                    width: size
                    height: size
                    scale: audioStage.playing ? 1 + Math.sin(audioStage.beat) * 0.025 : 0.94

                    Behavior on scale {
                        enabled: !audioStage.playing
                        Anim {
                            type: Anim.DefaultSpatial
                        }
                    }

                    MaterialShape {
                        id: discShape

                        anchors.centerIn: parent
                        implicitSize: parent.width
                        shape: audioStage.hasCover ? MaterialShape.Cookie12Sided : audioStage.shapes[audioStage.shapeIndex]
                        color: Colours.palette.m3primaryContainer
                        rotation: audioStage.spin
                        animationEasing: Tokens.anim.expressiveDefaultSpatial
                        animationDuration: Tokens.anim.durations.expressiveDefaultSpatial
                    }

                    // The cover, masked by the same turning cookie.
                    Image {
                        id: cover

                        anchors.fill: parent
                        visible: audioStage.hasCover
                        source: root.mode === "audio" ? root.imageSource : ""
                        sourceSize: Qt.size(512, 512)
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        layer.enabled: visible
                        layer.effect: MultiEffect {
                            maskEnabled: true
                            maskSource: coverMask
                            maskThresholdMin: 0.5
                            maskSpreadAtMin: 1
                        }
                    }
                    MaterialShape {
                        id: coverMask

                        anchors.centerIn: parent
                        implicitSize: parent.width
                        visible: false
                        layer.enabled: true
                        shape: MaterialShape.Cookie12Sided
                        color: "black" // theme-exception: mask alpha only, never shown
                        rotation: audioStage.spin
                    }

                    MaterialIcon {
                        anchors.centerIn: parent
                        visible: !audioStage.hasCover
                        text: "music_note"
                        fill: 1
                        color: Colours.palette.m3onPrimaryContainer
                        fontStyle: Tokens.font.icon.builders.extraLarge.scale(1.4 * root.scale).build()
                    }
                }

                // Play button and a seekable progress line with times.
                Row {
                    id: controls

                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: disc.bottom
                    anchors.topMargin: Tokens.spacing.large
                    spacing: Tokens.spacing.medium
                    height: 44 * root.scale

                    Rectangle {
                        id: playButton

                        anchors.verticalCenter: parent.verticalCenter
                        width: 44 * root.scale
                        height: width
                        radius: audioStage.playing ? Tokens.rounding.medium : height / 2
                        color: Colours.palette.m3primary

                        Behavior on radius {
                            Anim {
                                type: Anim.FastSpatial
                            }
                        }

                        MaterialIcon {
                            anchors.centerIn: parent
                            text: audioStage.playing ? "pause" : "play_arrow"
                            fill: 1
                            color: Colours.palette.m3onPrimary
                            fontStyle: Tokens.font.icon.builders.medium.scale(root.scale).build()
                            animate: true
                        }
                        StateLayer {
                            radius: playButton.radius
                            color: Colours.palette.m3onPrimary
                            onClicked: root.togglePlayback()
                        }
                    }

                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.duration(sound.position / 1000)
                        font: root.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                    Item {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.max(80, audioStage.width * 0.42)
                        height: 20

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width
                            height: 4
                            radius: 2
                            color: Qt.alpha(Colours.palette.m3onSurface, 0.16)

                            Rectangle {
                                width: parent.width * Math.min(1, sound.position / Math.max(1, sound.duration))
                                height: parent.height
                                radius: 2
                                color: Colours.palette.m3primary
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: mouse => {
                                if (sound.duration > 0)
                                    sound.position = sound.duration * mouse.x / width;
                            }
                        }
                    }
                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.duration((sound.duration || (root.meta.duration ?? 0) * 1000) / 1000)
                        font: root.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }

            MediaPlayer {
                id: sound

                audioOutput: AudioOutput {
                    volume: 0.7
                }
            }
            // Dwell before sound: scrolling through a folder of songs stays silent.
            Timer {
                id: autoplay

                interval: 450
                onTriggered: if (root.mode === "audio" && root.visible) sound.play()
            }

            // Colour: a cookie filled with it, the three notations beside it.
            Row {
                anchors.centerIn: parent
                visible: root.mode === "color"
                spacing: Tokens.spacing.extraLarge

                MaterialShape {
                    anchors.verticalCenter: parent.verticalCenter
                    implicitSize: Math.min(stage.width * 0.4, stage.height * 0.6)
                    shape: MaterialShape.Cookie12Sided
                    color: root.mode === "color" ? Colour.parse(root.row.value) : "transparent" // theme-exception: user colour sample from clipboard
                    strokeColor: Colours.palette.m3outlineVariant
                    strokeWidth: 1
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Tokens.spacing.medium

                    Repeater {
                        model: {
                            if (root.mode !== "color")
                                return [];
                            const c = Colour.parse(root.row.value);
                            return [["HEX", c.toString().toUpperCase()],
                                ["RGB", `${Math.round(c.r * 255)}, ${Math.round(c.g * 255)}, ${Math.round(c.b * 255)}`],
                                ["HSL", `${Math.round(Math.max(0, c.hslHue) * 360)}°, ${Math.round(c.hslSaturation * 100)}%, ${Math.round(c.hslLightness * 100)}%`]];
                        }

                        Column {
                            id: notation

                            required property var modelData

                            StyledText {
                                text: notation.modelData[0]
                                font: root.small
                                color: Colours.palette.m3onSurfaceVariant
                            }
                            StyledText {
                                text: notation.modelData[1]
                                font: Tokens.font.title.medium
                                color: Colours.palette.m3onSurface
                            }
                        }
                    }
                }
            }

            // Compact clipboard content gets the whole stage, not a tiny line of prose.
            StyledText {
                anchors.fill: parent
                anchors.margins: Tokens.padding.extraLarge
                visible: root.mode === "emoji" || root.mode === "number"
                text: visible ? root.bodyText.trim() : ""
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font: Tokens.font.headline.builders.large.size(Math.min(stage.height * 0.45, stage.width * 0.27)).build()
                fontSizeMode: Text.Fit
                minimumPixelSize: Tokens.font.body.small.pixelSize
                color: Colours.palette.m3primary
                wrapMode: Text.WrapAnywhere
            }

            // A full-width editorial hero; text appears as soon as HTML metadata arrives.
            Item {
                anchors.fill: parent
                visible: root.mode === "link"

                ClipRect {
                    id: webHero
                    anchors.top: parent.top
                    width: parent.width
                    height: Math.min(width * 0.56, parent.height * 0.55)
                    radius: Tokens.rounding.large
                    color: Colours.palette.m3secondaryContainer
                    Image {
                        id: webImage
                        anchors.fill: parent
                        source: root.mode === "link" ? (root.meta.image ?? "") : ""
                        sourceSize: root.decodeSize
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        opacity: status === Image.Ready ? 1 : 0
                        Behavior on opacity { Anim { type: Anim.FastEffects } }
                    }
                    MaterialShape {
                        anchors.centerIn: parent
                        visible: webImage.status !== Image.Ready
                        implicitSize: parent.height * 0.5
                        shape: MaterialShape.Cookie6Sided
                        color: Colours.palette.m3primary
                        MaterialIcon {
                            anchors.centerIn: parent
                            text: "public"
                            color: Colours.palette.m3onPrimary
                            fontStyle: Tokens.font.icon.large
                        }
                    }
                }
                Column {
                    anchors.top: webHero.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.small
                    StyledText {
                        width: parent.width
                        text: root.mode === "link" ? (root.meta.domain || root.row.value.match(/^https?:\/\/([^\/?#]+)/i)?.[1] || "Link") : ""
                        font: root.small
                        color: Colours.palette.m3primary
                        elide: Text.ElideRight
                    }
                    StyledText {
                        width: parent.width
                        text: root.meta.title || "Web page"
                        font: Tokens.font.title.medium
                        color: Colours.palette.m3onSurface
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    StyledText {
                        width: parent.width
                        text: root.meta.description || (root.mode === "link" ? root.row.value : "")
                        font: root.body
                        color: Colours.palette.m3onSurfaceVariant
                        wrapMode: Text.WrapAnywhere
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                }
            }

            // Folder: its contents, folders first.
            ListView {
                id: folderList

                anchors.fill: parent
                anchors.margins: Tokens.padding.small
                visible: root.mode === "folder"
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: root.folderItems
                delegate: Item {
                    id: entry

                    required property var modelData

                    width: ListView.view.width
                    height: 34 * root.scale

                    MaterialIcon {
                        id: entryIcon

                        anchors.left: parent.left
                        anchors.leftMargin: Tokens.padding.small
                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.modelData.dir ? "folder" : Files.icon(entry.modelData.name, false)
                        fill: entry.modelData.dir ? 1 : 0
                        color: entry.modelData.dir ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
                        fontStyle: Tokens.font.icon.small
                    }
                    StyledText {
                        anchors.left: entryIcon.right
                        anchors.leftMargin: Tokens.spacing.medium
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.modelData.name
                        font: root.body
                        color: Colours.palette.m3onSurface
                        elide: Text.ElideMiddle
                    }
                }
            }
            StyledText {
                anchors.centerIn: parent
                visible: root.mode === "folder" && root.folderCount === 0
                text: "Empty folder"
                font: root.body
                color: Colours.palette.m3onSurfaceVariant
            }

            // Code: numbered lines, no wrapping; text and Markdown wrap.
            Flickable {
                id: textFlick

                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                visible: ["code", "text", "markdown"].includes(root.mode) && root.bodyText !== ""
                contentWidth: root.mode === "code" ? Math.max(width, codeRow.implicitWidth) : width
                contentHeight: root.mode === "code" ? codeRow.implicitHeight : prose.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Row {
                    id: codeRow

                    visible: root.mode === "code"
                    spacing: Tokens.spacing.medium

                    StyledText {
                        text: {
                            if (root.mode !== "code")
                                return "";
                            const n = root.bodyText.split("\n").length;
                            return Array.from({length: n}, (_, i) => i + 1).join("\n");
                        }
                        font: Tokens.font.mono.small
                        color: root.nvimStyled ? root.codeLineNr : Colours.palette.m3outline
                        horizontalAlignment: Text.AlignRight
                    }
                    StyledText {
                        text: root.mode !== "code" ? "" : root.nvimStyled ? root.codeHtml : root.bodyText
                        textFormat: root.nvimStyled ? Text.StyledText : Text.PlainText
                        font: Tokens.font.mono.small
                        color: root.nvimStyled ? root.codeFg : Colours.palette.m3onSurface
                    }
                }
                StyledText {
                    id: prose

                    visible: root.mode !== "code"
                    width: textFlick.width
                    text: root.mode === "code" ? "" : root.bodyText
                    textFormat: root.mode === "markdown" ? Text.MarkdownText : Text.PlainText
                    font: root.isClip ? Tokens.font.body.builders.large.size(11.5 * root.scale).build() : root.body
                    color: Colours.palette.m3onSurface
                    wrapMode: Text.Wrap
                    lineHeight: 1.15
                }
            }

            // Anything else, or still loading: the kind's glyph in a soft shape.
            MaterialShape {
                anchors.centerIn: parent
                implicitSize: Math.min(parent.width, parent.height) * 0.42
                visible: (root.mode === "other" || (["image", "video", "page"].includes(root.mode) && picture.status !== Image.Ready && !videoOut.visible)) && root.row !== null
                shape: MaterialShape.Cookie7Sided
                color: Colours.palette.m3surfaceContainerHighest

                MaterialIcon {
                    anchors.centerIn: parent
                    text: root.row?.icon ?? "draft"
                    color: Colours.palette.m3onSurfaceVariant
                    fontStyle: Tokens.font.icon.builders.extraLarge.scale(root.scale).build()
                }
            }
        }

        // Kind badge in the corner (language for code, "Video", "PDF"…).
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.margins: Tokens.padding.medium
            visible: badge.text !== "" && root.mode !== "folder" && root.mode !== "link" && !textFlick.visible
            width: badge.implicitWidth + Tokens.padding.medium * 1.5
            height: 24 * root.scale
            radius: height / 2
            color: Qt.alpha(Colours.palette.m3surfaceContainerHighest, 0.92)

            StyledText {
                id: badge

                anchors.centerIn: parent
                text: ({video: "Video", audio: "Audio", page: "PDF", image: root.isClip ? "Copied image" : (root.ext.toUpperCase() || "Image"), color: "Colour", link: "Link", emoji: "Emoji", number: "Number"})[root.mode] ?? ""
                font: root.small
                color: Colours.palette.m3onSurface
            }
        }
    }

    // Explicit expand/back control also makes the keyboard path discoverable.
    Rectangle {
        anchors.right: stage.right
        anchors.top: stage.top
        anchors.margins: Tokens.padding.small
        visible: root.expandable
        width: expandLabel.implicitWidth + Tokens.padding.large * 2
        height: Tokens.padding.extraLarge + Tokens.padding.small
        radius: height / 2
        color: Colours.palette.m3secondaryContainer
        StyledText {
            id: expandLabel
            anchors.centerIn: parent
            text: root.expanded ? "← Back · Esc" : "Expand · →"
            font: root.small
            color: Colours.palette.m3onSecondaryContainer
        }
        StateLayer {
            radius: parent.radius
            onClicked: root.expanded ? root.collapseRequested() : root.expandRequested()
        }
    }

    Rectangle {
        anchors.horizontalCenter: stage.horizontalCenter
        anchors.bottom: stage.bottom
        anchors.bottomMargin: Tokens.padding.extraLarge
        visible: root.expanded && root.mode === "video"
        width: playbackLabel.implicitWidth + Tokens.padding.large * 2
        height: Tokens.padding.extraLarge + Tokens.padding.small
        radius: height / 2
        color: Colours.palette.m3secondaryContainer
        StyledText {
            id: playbackLabel
            anchors.centerIn: parent
            text: (video.playbackState === MediaPlayer.PlayingState ? "Pause" : "Play") + " · Space · " + root.duration(video.position / 1000) + " / " + root.duration(video.duration / 1000)
            font: root.small
            color: Colours.palette.m3onSecondaryContainer
        }
        StateLayer {
            radius: parent.radius
            onClicked: root.togglePlayback()
        }
    }

    // Zoom level, while zoomed in.
    Rectangle {
        anchors.right: stage.right
        anchors.bottom: stage.bottom
        anchors.margins: Tokens.padding.medium
        width: zoomRow.implicitWidth + Tokens.padding.medium * 1.6
        height: 26 * root.scale
        radius: height / 2
        color: Qt.alpha(Colours.palette.m3surfaceContainerHighest, 0.92)
        opacity: root.zoom > 1.01 ? 1 : 0
        visible: opacity > 0.01

        Behavior on opacity {
            Anim {
                type: Anim.FastEffects
            }
        }

        Row {
            id: zoomRow

            anchors.centerIn: parent
            spacing: Tokens.spacing.extraSmall

            MaterialIcon {
                anchors.verticalCenter: parent.verticalCenter
                text: "zoom_in"
                color: Colours.palette.m3primary
                fontStyle: Tokens.font.icon.builders.small.scale(0.85 * root.scale).build()
            }
            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                text: Math.round(root.zoom * 100) + "% · double click to fit"
                font: root.small
                color: Colours.palette.m3onSurface
            }
        }
    }

    // Details -------------------------------------------------------------------------------------
    Column {
        id: details

        visible: !root.expanded && root.mode !== "link"

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: stage.bottom
        anchors.topMargin: Tokens.spacing.medium
        spacing: Tokens.spacing.small
        opacity: root.contentProgress

        StyledText {
            width: parent.width
            text: root.row ? (root.isFile ? root.row.title : ({image: "Image", color: "Colour", link: "Link", emoji: "Emoji", number: "Number"})[root.mode] ?? "Text") : ""
            font: Tokens.font.title.medium
            color: Colours.palette.m3onSurface
            elide: Text.ElideMiddle
        }
        StyledText {
            width: parent.width
            visible: root.isFile
            text: root.isFile ? (root.mode === "code" ? root.ext.toUpperCase() + " · " : "") + root.row.subtitle : ""
            font: root.small
            color: Colours.palette.m3onSurfaceVariant
            elide: Text.ElideMiddle
        }
        Flow {
            width: parent.width
            spacing: Tokens.spacing.small
            topPadding: Tokens.spacing.extraSmall

            Repeater {
                model: root.chips

                Rectangle {
                    id: chip

                    required property var modelData

                    width: chipRow.implicitWidth + Tokens.padding.medium * 1.6
                    height: 26 * root.scale
                    radius: height / 2
                    color: Colours.palette.m3surfaceContainerHighest

                    Row {
                        id: chipRow

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.extraSmall + 2

                        MaterialIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            text: chip.modelData[0]
                            color: Colours.palette.m3primary
                            fontStyle: Tokens.font.icon.builders.small.scale(0.85 * root.scale).build()
                        }
                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: chip.modelData[1]
                            font: root.small
                            color: Colours.palette.m3onSurface
                        }
                    }
                }
            }
        }
    }

    onVisibleChanged: if (!visible) {
        webProc.running = false;
        autoplay.stop();
        sound.stop();
        sound.source = "";
        video.stop();
        video.source = "";
    }

    function scrollBy(dy: real): void {
        const view = root.mode === "folder" ? folderList : textFlick;
        view.contentY = Math.max(0, Math.min(view.contentHeight - view.height, view.contentY + dy));
    }
}
