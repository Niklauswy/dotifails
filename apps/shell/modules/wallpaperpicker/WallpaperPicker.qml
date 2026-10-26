pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Wysun.Config
import Wysun.I18n
import Wysun.Images
import Wysun.Shaders
import qs.components
import qs.components.controls
import qs.components.filedialog
import qs.modules.background
import qs.services
import qs.utils

// Orbit wallpaper picker. Original Wysun code. The wallpapers turn on a tilted ring;
// the front card is the selection, the backdrop is that wallpaper blurred, and the
// accent follows its dominant colour. Opening drops the ring in spinning. Applying
// flings the other cards away and throws the chosen one into the desktop, where it
// lands and swells into the new wallpaper (Shaders.cardBloom); the background then
// takes over underneath without a transition of its own.
Scope {
    id: root

    Variants {
        model: Quickshell.screens

        delegate: OverlayWindow {
            id: win

            surface: "wallpapers"
            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }

            property bool libraryOpen

            function sync(): void {
                if (state.wallpapers) {
                    filter.text = "";
                    if (!libraryOpen)
                        WallpaperLibrary.open();
                    libraryOpen = true;
                    carousel.reset();
                    carousel.enter();
                    Qt.callLater(() => filter.forceActiveFocus());
                } else if (libraryOpen) {
                    libraryOpen = false;
                    WallpaperLibrary.close();
                }
            }

            Component.onDestruction: {
                if (libraryOpen)
                    WallpaperLibrary.close();
            }

            // The state survives shell reloads, so a picker left open comes back populated.
            Component.onCompleted: {
                if (state.wallpapers)
                    sync();
            }

            Connections {
                target: win.state

                function onWallpapersChanged(): void {
                    win.sync();
                }
            }

            Connections {
                target: WallpaperLibrary

                function onEntriesChanged(): void {
                    if (win.state.wallpapers)
                        carousel.reset();
                }
            }

            // Scriptable control of the open picker (`wysun-shell` IPC: wallpapers go|select|filter|apply|state).
            IpcHandler {
                enabled: win.state.wallpapers
                target: "wallpapers"

                function go(delta: int): void {
                    carousel.go(delta);
                }

                function select(position: int): void {
                    carousel.move(position);
                }

                function filter(text: string): void {
                    filter.text = text;
                }

                function apply(): void {
                    carousel.apply();
                }

                function random(): void {
                    carousel.random();
                }

                function state(): string {
                    return JSON.stringify({ settled: carousel.settled, query: filter.text, index: carousel.index, count: carousel.items.length, cards: cards.count, selected: carousel.items[carousel.index]?.path ?? "" });
                }
            }

            // The selected wallpaper, heavily blurred, cross-fading as the ring turns.
            Item {
                id: backdrop

                property Image front: backA

                function show(thumb: string): void {
                    const next = front === backA ? backB : backA;
                    next.source = thumb ? `file://${thumb}` : "";
                    front = next;
                }

                anchors.fill: parent
                // Gone while the card is thrown, so the real desktop takes the impact.
                opacity: Math.max(0, Math.min(1, win.reveal)) * (1 - carousel.outro)
                layer.enabled: true
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blur: 1
                    blurMax: 64
                    saturation: 0.25
                }

                Image {
                    id: backA

                    anchors.fill: parent
                    asynchronous: true
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: 480
                    opacity: backdrop.front === this && status === Image.Ready ? 1 : 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.SlowEffects
                        }
                    }
                }

                Image {
                    id: backB

                    anchors.fill: parent
                    asynchronous: true
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: 480
                    opacity: backdrop.front === this && status === Image.Ready ? 1 : 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.SlowEffects
                        }
                    }
                }
            }

            // A veil in the surface colour keeps text legible in light and dark mode.
            Rectangle {
                anchors.fill: parent
                color: Colours.palette.m3surface
                opacity: 0.55 * Math.max(0, Math.min(1, win.reveal)) * (1 - carousel.outro)

                MouseArea {
                    anchors.fill: parent
                    onClicked: win.close()
                    onWheel: wheel => carousel.wheelStep(wheel.angleDelta.y)
                }
            }

            Item {
                id: carousel

                // Ring positions; with more wallpapers than this, only the nearest are drawn.
                readonly property int slots: 12
                readonly property int count: items.length
                readonly property real step: 360 / Math.max(1, Math.min(count, slots))
                // Proportions of the approved mockup: card 15% of the width, ring twice its width.
                readonly property real cardWidth: Math.min(win.width * 0.15, win.height * 0.2666)
                readonly property real cardHeight: cardWidth * 30 / 19
                readonly property real ringRadius: cardWidth * 2
                readonly property string query: filter.text.trim().toLowerCase()
                readonly property var items: {
                    const all = WallpaperLibrary.entries;
                    return query ? all.filter(e => e.name.toLowerCase().includes(query) || (query === "animated" && e.animated)) : all;
                }
                readonly property string currentPath: Wallpapers.forOutput(win.modelData.name)
                readonly property string selectedThumb: WallpaperLibrary.thumbFor(items[index]?.path ?? "")
                // The ring turns without end: `target` counts whole turns, `index` wraps it.
                property int target: 0
                readonly property int index: wrap(target)
                property real pos: 0
                property real intro: 1
                property real outro: 0
                property real toss: 0
                property real bloom: 0
                property real bloomFade: 1
                property string applying
                property bool landed
                property bool leaving
                property bool settled
                property real wheelAcc

                // Derived from the selection's dominant colour (wallpaper-driven, like the scheme);
                // greys fall back to the scheme's primary.
                property color accent: {
                    const c = analyser.dominantColour;
                    if (!selectedThumb || c.hslSaturation < 0.15)
                        return Colours.palette.m3primary;
                    return Qt.hsla(c.hslHue, Math.max(0.45, c.hslSaturation), Colours.light ? 0.38 : 0.78, 1); // theme-exception: accent derived from the selected wallpaper's dominant colour
                }

                Behavior on accent {
                    CAnim {}
                }

                function wrap(i: int): int {
                    return count ? ((i % count) + count) % count : 0;
                }

                // Signed distance around the ring, in cards.
                function around(d: real): real {
                    return count ? d - count * Math.round(d / count) : d;
                }

                function reset(): void {
                    const found = items.findIndex(e => e.path === currentPath);
                    target = Math.max(found, 0);
                    snap.restart();
                    pos = target;
                    syncWindow();
                    settled = false;
                    settle.restart();
                }

                function enter(): void {
                    leaving = false;
                    outroAnim.stop();
                    throwAnim.stop();
                    bloomAnim.stop();
                    finishAnim.stop();
                    bloomWait.stop();
                    shownWait.stop();
                    outro = 0;
                    if (Wallpapers.handoffScreen === win.modelData.name)
                        Wallpapers.endHandoff();
                    landed = false;
                    toss = 0;
                    bloom = 0;
                    bloomFade = 1;
                    intro = 0;
                    introAnim.restart();
                }

                function go(delta: int): void {
                    if (!count || leaving || delta === 0)
                        return;
                    target += delta;
                    settled = false;
                    settle.restart();
                    pos = target;
                }

                function move(position: int): void {
                    const next = Math.max(0, Math.min(count - 1, position));
                    go(Math.round(around(next - index)));
                }

                function wheelStep(delta: real): void {
                    wheelAcc += delta;
                    while (Math.abs(wheelAcc) >= 120) {
                        go(wheelAcc > 0 ? -1 : 1);
                        wheelAcc -= wheelAcc > 0 ? 120 : -120;
                    }
                }

                // Throw the chosen card into the desktop. The wallpaper is set just before the
                // impact so its transition opens where the card lands, in plain sight.
                function apply(): void {
                    const entry = items[index];
                    if (!entry || leaving)
                        return;
                    leaving = true;
                    randomApply.stop();
                    applying = entry.path;
                    if (entry.path === currentPath)
                        outroAnim.restart();
                    else
                        throwAnim.restart();
                }

                // Swell the landed card into the new wallpaper once its picture is decoded
                // (or when `force`d, so a slow decode never strands the card).
                function startBloom(force: bool): void {
                    if (!landed || bloom > 0 || bloomAnim.running)
                        return;
                    if (!force && !bloomVisual.ready)
                        return;
                    bloomWait.stop();
                    bloomAnim.start();
                }

                // The card covers the screen: let the background switch underneath, then
                // drop the card once the background shows the new wallpaper.
                function finish(): void {
                    if (finishAnim.running || bloomFade < 1)
                        return;
                    shownWait.stop();
                    finishAnim.start();
                }

                // Spin to a wallpaper other than the current one, picked at random from what
                // the filter shows, then apply it.
                function random(): void {
                    const pool = [];
                    for (let i = 0; i < count; i++)
                        if (items[i].path !== currentPath && i !== index)
                            pool.push(i);
                    if (pool.length === 0 || leaving)
                        return;
                    move(pool[Math.floor(Math.random() * pool.length)]);
                    randomApply.restart();
                }

                // The picker covers the screen, so it steps aside while the file dialog is open.
                function add(): void {
                    addDialog.open();
                    win.close();
                }

                // Keep only the cards near the front alive (virtualised ring).
                function syncWindow(): void {
                    const wanted = {};
                    if (count <= slots) {
                        for (let i = 0; i < count; i++)
                            wanted[i] = true;
                    } else {
                        const base = Math.round(pos), half = slots / 2 - 1;
                        for (let k = -half; k <= half; k++)
                            wanted[wrap(base + k)] = true;
                    }
                    for (let i = cards.count - 1; i >= 0; i--) {
                        const idx = cards.get(i).idx;
                        if (wanted[idx])
                            delete wanted[idx];
                        else
                            cards.remove(i);
                    }
                    for (const idx of Object.keys(wanted).map(Number).sort((x, y) => Math.abs(around(x - pos)) - Math.abs(around(y - pos))))
                        cards.append({ idx });
                }

                anchors.fill: parent
                opacity: Math.max(0, Math.min(1, win.reveal))
                onPosChanged: syncWindow()
                onSelectedThumbChanged: backdrop.show(selectedThumb)
                onItemsChanged: {
                    cards.clear();
                    const found = query ? -1 : items.findIndex(e => e.path === currentPath);
                    target = found >= 0 ? found : query ? 0 : Math.min(index, Math.max(count - 1, 0));
                    snap.restart();
                    pos = target;
                    syncWindow();
                    settled = false;
                    settle.restart();
                }

                // Spring towards the selected card; `snap` jumps without animating.
                Behavior on pos {
                    enabled: !snap.running

                    SpringAnimation {
                        spring: 3.6
                        damping: 0.32
                        epsilon: 0.0005
                    }
                }

                Anim {
                    id: introAnim

                    target: carousel
                    property: "intro"
                    to: 1
                    duration: Tokens.anim.durations.extraLarge
                    easing: Tokens.anim.expressiveSlowSpatial
                }

                Anim {
                    id: outroAnim

                    target: carousel
                    property: "outro"
                    to: 1
                    duration: Tokens.anim.durations.large
                    easing: Tokens.anim.emphasizedAccel
                    onFinished: win.close()
                }

                // The throw: the card lifts and dives into the desktop, landing at the screen's
                // centre. The wallpaper is handed off mid-flight so it decodes while the card
                // flies; the background holds it back until the bloom covers the screen.
                ParallelAnimation {
                    id: throwAnim

                    onFinished: {
                        carousel.landed = true;
                        carousel.startBloom(false);
                        bloomWait.restart();
                    }

                    Anim {
                        target: carousel
                        property: "outro"
                        to: 1
                        duration: Tokens.anim.durations.large
                        easing: Tokens.anim.emphasizedAccel
                    }
                    Anim {
                        target: carousel
                        property: "toss"
                        to: 1
                        duration: Tokens.anim.durations.extraLarge * 0.85
                        easing: Tokens.anim.emphasized
                    }
                    SequentialAnimation {
                        PauseAnimation {
                            duration: Tokens.anim.durations.extraLarge * 0.3
                        }
                        ScriptAction {
                            script: Wallpapers.setWallpaperHandedOff(carousel.applying, win.modelData.name)
                        }
                    }
                }

                Anim {
                    id: bloomAnim

                    target: carousel
                    property: "bloom"
                    to: 1
                    duration: Shaders.cardBloom.duration * 1.3 * Tokens.anim.durations.scale
                    easing: Shaders.cardBloom.easing
                    onFinished: {
                        Wallpapers.releaseHandoff();
                        shownWait.restart();
                    }
                }

                SequentialAnimation {
                    id: finishAnim

                    Anim {
                        target: carousel
                        property: "bloomFade"
                        to: 0
                        type: Anim.DefaultEffects
                    }
                    ScriptAction {
                        script: {
                            Wallpapers.endHandoff();
                            win.close();
                        }
                    }
                }

                Timer {
                    id: bloomWait

                    interval: Tokens.anim.durations.extraLarge * 1.5
                    onTriggered: carousel.startBloom(true)
                }

                Timer {
                    id: shownWait

                    interval: Tokens.anim.durations.extraLarge * 2.5
                    onTriggered: carousel.finish()
                }

                Connections {
                    target: Wallpapers

                    function onShown(screen: string, path: string): void {
                        if (screen === win.modelData.name && carousel.bloom >= 1)
                            carousel.finish();
                    }
                }

                // The new wallpaper at full size, decoded during the throw; the bloom samples it.
                WallpaperVisual {
                    id: bloomVisual

                    anchors.fill: parent
                    source: carousel.leaving ? carousel.applying : ""
                    playing: true
                    animate: true
                    onReadyChanged: carousel.startBloom(false)
                }

                ShaderEffectSource {
                    id: bloomSource

                    anchors.fill: parent
                    sourceItem: carousel.leaving ? bloomVisual : null
                    hideSource: true
                    live: true
                    visible: false
                }

                ImageAnalyser {
                    id: analyser

                    source: carousel.selectedThumb
                }

                Timer {
                    id: snap

                    interval: 50
                }

                Timer {
                    id: settle

                    interval: 450
                    onTriggered: carousel.settled = true
                }

                Timer {
                    id: randomApply

                    interval: Tokens.anim.durations.large
                    onTriggered: carousel.apply()
                }

                FileDialog {
                    id: addDialog

                    title: Tr.tr("Select a wallpaper")
                    filterLabel: Tr.tr("Images and videos")
                    filters: Images.validImageExtensions.concat(["bmp", "gif", "mp4", "webm", "mkv"])
                    onAccepted: path => Wallpapers.setWallpaper(path)
                }

                ListModel {
                    id: cards
                }

                Item {
                    id: ring

                    anchors.fill: parent

                    Repeater {
                        model: cards

                        delegate: WallpaperCard {
                            required property int idx

                            entry: carousel.items[idx] ?? ({ path: "", animated: false })
                            t: carousel.around(idx - carousel.pos)
                            step: carousel.step
                            span: carousel.count <= carousel.slots ? carousel.slots : carousel.slots / 2 - 1.5
                            ringRadius: carousel.ringRadius
                            cardWidth: carousel.cardWidth
                            cardHeight: carousel.cardHeight
                            centre: Qt.point(ring.width / 2, ring.height * 0.46)
                            selected: idx === carousel.index
                            current: entry.path === carousel.currentPath
                            accent: carousel.accent
                            intro: carousel.intro
                            outro: carousel.outro
                            toss: carousel.toss
                            bloomed: carousel.bloom > 0
                            impact: Qt.point(ring.width / 2, ring.height / 2)
                            settled: carousel.settled
                            onClicked: idx === carousel.index ? carousel.apply() : carousel.move(idx)
                        }
                    }
                }

                // The landed card swelling into the new wallpaper, over the desktop.
                ShaderEffect {
                    // The card's size where it lands (see WallpaperCard: lift, then half size).
                    readonly property real landedScale: 1.08 * 0.5

                    property real progress: carousel.bloom
                    property real cornerRadius: Tokens.rounding.extraLarge * landedScale
                    property vector4d cardRect: {
                        const w = carousel.cardWidth * landedScale, h = carousel.cardHeight * landedScale * Math.cos(14 * Math.PI / 180);
                        return Qt.vector4d(width / 2 - w / 2, height / 2 - h / 2, w, h);
                    }
                    property size screenSize: Qt.size(width, height)
                    property color tint: carousel.accent
                    property Item source: bloomSource

                    anchors.fill: parent
                    visible: carousel.bloom > 0
                    opacity: carousel.bloomFade
                    fragmentShader: Shaders.cardBloom.url
                }

                // Number, name and kind of the selection.
                Column {
                    id: info

                    readonly property var entry: carousel.items[carousel.index]

                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: Tokens.padding.extraExtraLarge * 1.5
                    anchors.bottomMargin: Tokens.padding.extraExtraLarge * 1.5
                    width: Math.min(implicitWidth, parent.width * 0.3)
                    spacing: Tokens.spacing.small
                    visible: !!entry
                    opacity: 1 - carousel.outro

                    transform: Translate {
                        x: -carousel.outro * info.anchors.leftMargin
                    }

                    Row {
                        spacing: Tokens.spacing.medium

                        StyledText {
                            id: number

                            text: String(carousel.index + 1).padStart(2, "0")
                            color: carousel.accent
                            font: Tokens.font.headline.builders.large.size(carousel.cardHeight * 0.2).weight(Font.Light).build()
                        }

                        StyledText {
                            anchors.baseline: number.baseline
                            text: `/ ${String(carousel.count).padStart(2, "0")}`
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.title.small
                        }
                    }

                    Item {
                        width: Math.min(name.implicitWidth, win.width * 0.3)
                        height: name.implicitHeight
                        clip: true

                        StaggerText {
                            id: name

                            text: info.entry?.name ?? ""
                        }
                    }

                    Row {
                        spacing: Tokens.spacing.small

                        Chip {
                            accent: carousel.accent
                            icon: info.entry?.animated ? "animation" : "image"
                            text: info.entry?.animated ? Tr.tr("Animated") : Tr.tr("Image")
                            font: Tokens.font.label.small
                        }

                        Chip {
                            accent: carousel.accent
                            visible: info.entry?.path === carousel.currentPath
                            icon: "check_circle"
                            text: Tr.tr("In use")
                            font: Tokens.font.label.small
                        }
                    }
                }

                Column {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: Tokens.padding.extraExtraLarge
                    spacing: Tokens.spacing.medium
                    opacity: 1 - carousel.outro

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: carousel.count === 0
                        text: WallpaperLibrary.scanning ? "Loading wallpapers…" : "No wallpapers found"
                        color: Colours.palette.m3onSurface
                        font: Tokens.font.title.small
                    }

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: Tokens.spacing.small

                        IconButton {
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "add_photo_alternate"
                            type: IconButton.Tonal
                            isRound: true
                            onClicked: carousel.add()
                        }

                        SearchBar {
                            id: filter

                            anchors.verticalCenter: parent.verticalCenter
                            implicitWidth: Tokens.sizes.launcher.itemWidth * 0.6
                            placeholderText: "Filter wallpapers"
                            bg.border.width: 1
                            bg.border.color: filter.activeFocus ? carousel.accent : Colours.palette.m3outlineVariant
                            focus: true

                            Keys.priority: Keys.BeforeItem
                            Keys.onPressed: event => {
                                const key = event.key;
                                if ((event.modifiers & Qt.ControlModifier) && key === Qt.Key_R)
                                    carousel.random();
                                else if (key === Qt.Key_Left || key === Qt.Key_Up)
                                    carousel.go(-1);
                                else if (key === Qt.Key_Right || key === Qt.Key_Down)
                                    carousel.go(1);
                                else if (key === Qt.Key_PageUp)
                                    carousel.go(-5);
                                else if (key === Qt.Key_PageDown)
                                    carousel.go(5);
                                else if (key === Qt.Key_Home)
                                    carousel.move(0);
                                else if (key === Qt.Key_End)
                                    carousel.move(carousel.count - 1);
                                else if (key === Qt.Key_Return || key === Qt.Key_Enter)
                                    carousel.apply();
                                else
                                    return;
                                event.accepted = true;
                            }
                        }

                        IconButton {
                            anchors.verticalCenter: parent.verticalCenter
                            icon: "shuffle"
                            type: IconButton.Tonal
                            isRound: true
                            onClicked: carousel.random()
                        }
                    }

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: carousel.count > 0
                        text: "← → spin  ·  Enter apply  ·  Ctrl+R random  ·  Esc close"
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.label.small
                    }
                }
            }
        }
    }
}
