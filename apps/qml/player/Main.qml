// Wysun Player: one window per request. Python provides `player` (this window's PlayerController) and `bridge`
// (theme). A stage per kind (video with libmpv, picture, audio), the floating control bar that hides itself while
// a video plays or a picture is shown, menus, file information, short notices and every shortcut of the player.
import QtQuick
import WysunM3
import Wysun.Player

Window {
    id: window

    readonly property QtObject controller: player
    readonly property string kind: player.kindName
    readonly property bool timed: kind === "video" || kind === "audio"
    readonly property int hideAfter: 2500
    property bool barShown: true
    property bool menuOpen: menu.opened || info.opened
    readonly property bool hidesBar: (kind === "video" && player.state === "playing" || kind === "image") && !menuOpen && !barHover.hovered && player.error === ""

    function activity() {
        barShown = true;
        idle.restart();
    }

    function popup(which, anchor) {
        menu.which = which;
        menu.model = menus.model(which);
        menu.popup(anchor, 0, 0);
        idle.stop();
    }

    function showInfo() {
        info.open();
        idle.stop();
    }

    function releaseVideo() {
        if (videoLoader.item)
            videoLoader.item.release();
    }

    width: 960
    height: 600
    minimumWidth: Metrics.iconButtonSize * 8
    minimumHeight: Metrics.iconButtonSize * 6
    visible: false
    title: player.title !== "" ? player.title + " · Wysun Player" : "Wysun Player"
    color: kind === "video" ? Theme.m3scrim : Theme.m3surfaceContainerLowest

    onClosing: {
        releaseVideo();
        player.shutdown();
    }
    onVisibilityChanged: shown => {
        player.noteFullscreen(shown === Window.FullScreen);
        player.visibilityChanged();
    }
    onMenuOpenChanged: menuOpen ? idle.stop() : activity()

    Connections {
        target: player

        function onFullscreenRequested(on) {
            if (on)
                window.showFullScreen();
            else
                window.showNormal();
            window.activity();
        }
        function onToast(text, icon) {
            toast.say(text, icon);
        }
        function onCloseRequested() {
            window.close();
        }
        function onMediaChanged() {
            window.activity();
        }
        function onPlaybackChanged() {
            if (player.state !== "playing")
                window.activity();
        }
    }

    Timer {
        id: idle

        interval: window.hideAfter
        running: true
        onTriggered: {
            if (window.hidesBar)
                window.barShown = false;
            else
                restart();
        }
    }

    // A click on the video pauses after the double-click interval (a double click is full screen instead).
    Timer {
        id: click

        interval: Qt.styleHints.mouseDoubleClickInterval
        onTriggered: player.toggle()
    }

    Item {
        id: root

        objectName: "playerRoot"
        anchors.fill: parent
        focus: true

        ThemeFeed {
            scheme: bridge.scheme
            tokens: bridge.tokens
            reducedMotion: bridge.reducedMotion
        }

        HoverHandler {
            onPointChanged: window.activity()
        }

        Keys.onPressed: event => {
            window.activity();
            event.accepted = keys.handle(event);
        }

        QtObject {
            id: keys

            function handle(event) {
                const key = event.key, text = event.text.toLowerCase();
                const shift = event.modifiers & Qt.ShiftModifier, ctrl = event.modifiers & Qt.ControlModifier;
                if (key === Qt.Key_Escape && player.fullscreen)
                    player.setFullscreen(false);
                else if ((key === Qt.Key_F || key === Qt.Key_F11) && !ctrl && window.kind !== "audio")
                    player.toggleFullscreen();
                else if (ctrl && key === Qt.Key_C)
                    window.kind === "image" ? player.copyImage() : player.copyPath();
                else if (ctrl && (key === Qt.Key_Q || key === Qt.Key_W))
                    window.close();
                else if (key === Qt.Key_O && (ctrl || !event.modifiers))
                    player.chooseFiles();
                else if (key === Qt.Key_Delete)
                    player.trash();
                else if (key === Qt.Key_I && !ctrl)
                    window.showInfo();
                else if (window.timed && timedKey(key, text, shift, ctrl))
                    return true;
                else if (window.kind === "image" && imageKey(key, text, shift))
                    return true;
                else if (key === Qt.Key_PageDown || key === Qt.Key_N && !ctrl || key === Qt.Key_Right && window.kind === "image")
                    player.stepCollection(1);
                else if (key === Qt.Key_PageUp || key === Qt.Key_P && !ctrl || key === Qt.Key_Left && window.kind === "image")
                    player.stepCollection(-1);
                else
                    return false;
                return true;
            }

            function timedKey(key, text, shift, ctrl) {
                const step = ctrl ? 60 : shift ? 1 : 5;
                if (key === Qt.Key_Space || key === Qt.Key_K)
                    player.toggle();
                else if (key === Qt.Key_Left)
                    player.skip(-step);
                else if (key === Qt.Key_Right)
                    player.skip(step);
                else if (key === Qt.Key_Up)
                    player.nudgeVolume(5);
                else if (key === Qt.Key_Down)
                    player.nudgeVolume(-5);
                else if (key === Qt.Key_Home)
                    player.seek(0);
                else if (key === Qt.Key_End)
                    player.seekEnd();
                else if (text >= "0" && text <= "9" && text.length === 1 && !shift)
                    player.seekFraction(Number(text) / 10);
                else if (key === Qt.Key_Period)
                    player.step(1);
                else if (key === Qt.Key_Comma)
                    player.step(-1);
                else if (key === Qt.Key_BracketRight)
                    player.nudgeSpeed(1);
                else if (key === Qt.Key_BracketLeft)
                    player.nudgeSpeed(-1);
                else if (key === Qt.Key_Backspace)
                    player.setSpeed(1);
                else if (key === Qt.Key_M)
                    player.toggleMute();
                else if (key === Qt.Key_L && !shift)
                    player.markLoop();
                else if (key === Qt.Key_L && shift)
                    player.toggleLoop();
                else if (key === Qt.Key_C && window.kind === "video")
                    player.cycleSubtitles();
                else if (key === Qt.Key_A)
                    player.cycleAudio();
                else if (key === Qt.Key_S && window.kind === "video")
                    player.saveFrame();
                else
                    return false;
                return true;
            }

            function imageKey(key, text, shift) {
                if (key === Qt.Key_Space) {
                    if (imageStage.animated)
                        imageStage.toggleAnimation();
                    else
                        player.stepCollection(1);
                } else if (key === Qt.Key_Plus || key === Qt.Key_Equal || key === Qt.Key_Up)
                    imageStage.zoomBy(1.25);
                else if (key === Qt.Key_Minus || key === Qt.Key_Down)
                    imageStage.zoomBy(1 / 1.25);
                else if (text === "0")
                    imageStage.setMode("fit");
                else if (text === "1")
                    imageStage.setMode("actual");
                else if (key === Qt.Key_R)
                    imageStage.rotate(shift ? -1 : 1);
                else
                    return false;
                return true;
            }
        }

        // ------------------------------------------------------------------ stages
        Loader {
            id: videoLoader

            objectName: "videoStage"
            anchors.fill: parent
            visible: window.kind === "video" && player.error === ""
            sourceComponent: player.rendererName === "software" ? softwareVideo : glVideo
        }

        Component {
            id: glVideo

            MpvVideo {
                session: player.mediaSession
                onFailed: reason => player.renderFailed(reason)
            }
        }

        Component {
            id: softwareVideo

            MpvSoftwareVideo {
                session: player.mediaSession
                onFailed: reason => player.renderFailed(reason)
            }
        }

        MouseArea {
            anchors.fill: parent
            visible: window.timed && player.error === ""
            hoverEnabled: true
            cursorShape: window.kind === "video" && !window.barShown ? Qt.BlankCursor : Qt.ArrowCursor
            onPositionChanged: window.activity()
            onClicked: if (window.kind === "video")
                click.start()
            onDoubleClicked: {
                click.stop();
                if (window.kind === "video")
                    player.toggleFullscreen();
            }
            onWheel: wheel => player.nudgeVolume(wheel.angleDelta.y > 0 ? 5 : -5)
        }

        ImageStage {
            id: imageStage

            objectName: "imageStage"
            anchors.fill: parent
            visible: window.kind === "image" && player.error === ""
            source: window.kind === "image" ? player.url : ""
            naturalWidth: player.imageWidth
            naturalHeight: player.imageHeight
            neighbours: player.neighbours
            onLoaded: (w, h, frames) => player.setImageInfo(w, h, frames)
            onFailed: message => player.imageFailed(message)
        }

        AudioStage {
            objectName: "audioStage"
            anchors.fill: parent
            visible: window.kind === "audio" && player.error === ""
            cover: player.coverUrl
            title: player.audioTitle
            detail: player.audioDetail
            playing: player.state === "playing"
            reserve: bar.height + 2 * (Theme.padding.medium ?? 0)
        }

        // A file that could not be shown.
        Column {
            objectName: "note"
            anchors.centerIn: parent
            visible: player.error !== ""
            spacing: Theme.spacing.medium ?? 0
            width: Math.min(parent.width - 2 * (Theme.padding.extraLarge ?? 0), Metrics.textFieldMinWidth * 2)

            ShapeEmblem {
                anchors.horizontalCenter: parent.horizontalCenter
                shape: "cookie"
                color: Theme.m3errorContainer
                icon: "error"
                iconColor: Theme.m3onErrorContainer
            }
            Label {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                role: "body.large"
                color: Theme.m3onSurfaceVariant
                text: player.error
            }
        }

        // ------------------------------------------------------------------ control bar
        ControlBar {
            id: bar

            objectName: "controlBar"
            player: window.controller
            image: imageStage
            width: Math.min(parent.width - 2 * (Theme.padding.medium ?? 0), Metrics.iconButtonSize * 18)
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height - height - (Theme.padding.medium ?? 0) + (window.barShown ? 0 : height / 3)
            visible: opacity > 0 && window.kind !== "" && player.error === ""
            opacity: window.barShown ? 1 : 0
            onMenuRequested: (which, anchor) => window.popup(which, anchor)

            Behavior on opacity {
                Anim {
                    kind: "defaultEffects"
                }
            }
            Behavior on y {
                Anim {
                    kind: "defaultSpatial"
                }
            }

            HoverHandler {
                id: barHover
            }
        }

        // ------------------------------------------------------------------ notices
        Rectangle {
            id: toast

            property string text
            property string icon

            function say(text, icon) {
                toast.text = text;
                toast.icon = icon;
                toastTimer.restart();
            }

            objectName: "toast"
            anchors.horizontalCenter: parent.horizontalCenter
            y: Theme.padding.extraLarge ?? 0
            width: toastRow.implicitWidth + 2 * (Theme.padding.large ?? 0)
            height: Metrics.buttonHeight
            radius: height / 2
            color: Theme.m3inverseSurface
            opacity: toastTimer.running ? 1 : 0
            visible: opacity > 0

            Behavior on opacity {
                Anim {
                    kind: "fastEffects"
                }
            }

            Timer {
                id: toastTimer

                interval: Theme.duration("extraLarge") * 3
            }

            Row {
                id: toastRow

                anchors.centerIn: parent
                spacing: Theme.spacing.small ?? 0

                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: toast.icon
                    visible: toast.icon !== ""
                    color: Theme.m3inverseOnSurface
                }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    role: "label.large"
                    color: Theme.m3inverseOnSurface
                    text: toast.text
                }
            }
        }

        DropArea {
            anchors.fill: parent
            onDropped: drop => {
                if (drop.hasUrls) {
                    player.drop(drop.urls.map(u => String(u)));
                    drop.accept();
                }
            }
        }

        PlayerMenus {
            id: menus

            player: window.controller
            image: imageStage
            compact: bar.compact
            onSubmenu: which => Qt.callLater(window.popup, which, bar.moreButton)
            onInfoRequested: Qt.callLater(window.showInfo)
        }

        Menu {
            id: menu

            property string which

            objectName: "playerMenu"
            host: overlay
            onTriggered: id => menus.trigger(id)
        }

        Dialog {
            id: info

            objectName: "infoDialog"
            host: overlay
            modal: false
            title: "Información"
            icon: "info"
            actions: [{id: "close", text: "Cerrar", primary: true}]
            onAccepted: close()
            onRejected: close()

            Column {
                spacing: Theme.spacing.small ?? 0

                Repeater {
                    model: player.info

                    Row {
                        required property var modelData

                        spacing: Theme.spacing.medium ?? 0

                        Label {
                            width: Metrics.textFieldMinWidth * 0.7
                            role: "body.medium"
                            color: Theme.m3onSurfaceVariant
                            text: modelData.label
                        }
                        Label {
                            role: "body.medium"
                            text: modelData.value
                        }
                    }
                }
            }
        }

        OverlayLayer {
            id: overlay
        }
    }
}
