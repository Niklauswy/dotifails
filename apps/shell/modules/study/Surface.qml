pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// The one object of study mode: it is the setup panel, grows into the full-screen entry, collapses into the
// pill, unfolds into its cards and finally opens as the summary. Only its geometry and face change.
StyledRect {
    id: root

    required property var ui
    property bool msgShown
    property string msgApp
    property string msgIcon
    property string msgText
    // Apps closed at the start wait for the entry to finish before the pill says so.
    property var pendingNotice: null
    property bool askExit
    property bool forceCard
    property real flash

    readonly property string view: {
        switch (ui.mode) {
        case "setup":
            return "setup";
        case "takeover":
            return "takeover";
        case "summary":
            return "summary";
        case "study":
            break;
        default:
            return "hidden";
        }
        if (!Study.active)
            return "pill";
        if (askExit)
            return "exit";
        if (msgShown)
            return "msg";
        if (Study.phase === "break" || Study.phase === "ready")
            return "break";
        return hover.hovered || forceCard ? "card" : "pill";
    }
    readonly property bool attached: view === "setup" || view === "summary" || view === "hidden"
    readonly property bool slim: view === "pill" || view === "msg"
    readonly property real areaWidth: parent ? parent.width : 0
    readonly property real areaHeight: parent ? parent.height : 0
    readonly property int pillHeight: Tokens.padding.extraLarge + Tokens.padding.small - 2
    readonly property Item face: view === "setup" ? setup : view === "summary" ? summary : view === "card" ? card
        : view === "pill" ? pill : view === "msg" || view === "break" || view === "exit" ? cards : null

    x: (areaWidth - width) / 2
    y: attached || view === "takeover" ? 0 : Tokens.spacing.small + 2
    width: view === "takeover" ? areaWidth : view === "hidden" ? setup.implicitWidth : face?.implicitWidth ?? 0
    height: view === "takeover" ? areaHeight : view === "hidden" ? 0 : slim ? pillHeight : face?.implicitHeight ?? 0
    // Corners animate through these (a spring overshoots below zero; the rectangle must not).
    property real corner: view === "takeover" ? 0 : slim ? pillHeight / 2 : view === "card" || view === "exit" ? Tokens.rounding.largeIncreased : Tokens.rounding.extraLarge
    property real topCorner: attached || view === "takeover" ? 0 : corner
    radius: Math.max(0, corner)
    topLeftRadius: Math.max(0, topCorner)
    topRightRadius: topLeftRadius
    opacity: view === "hidden" ? 0 : 1
    clip: true
    color: view === "break" ? Colours.palette.m3tertiaryContainer
        : slim || view === "card" ? Colours.palette.m3surfaceContainerHigh : Colours.palette.m3surfaceContainer
    border.width: flash > 0 ? Tokens.padding.extraSmall / 2 : 0
    border.color: Qt.alpha(Colours.palette.m3tertiary, flash)

    component Morph: Anim {
        type: root.ui.slowMorph ? Anim.SlowSpatial : Anim.DefaultSpatial
    }

    Behavior on y {
        Morph {}
    }
    Behavior on width {
        Morph {}
    }
    Behavior on height {
        Morph {}
    }
    Behavior on corner {
        Morph {}
    }
    Behavior on topCorner {
        Morph {}
    }
    Behavior on opacity {
        Anim {
            type: Anim.DefaultEffects
        }
    }

    component Face: Item {
        required property bool on

        anchors.horizontalCenter: parent.horizontalCenter
        opacity: on ? 1 : 0
        visible: opacity > 0

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    HoverHandler {
        id: hover
    }

    Takeover {
        anchors.fill: parent
        shown: root.view === "takeover"
        config: root.ui.pending
    }

    Face {
        on: root.view === "setup"
        implicitWidth: setup.implicitWidth
        implicitHeight: setup.implicitHeight

        SetupPanel {
            id: setup

            onStart: config => root.ui.start(config)
        }
    }

    Face {
        on: root.view === "pill"
        anchors.verticalCenter: parent.verticalCenter
        implicitWidth: pill.implicitWidth
        implicitHeight: pill.implicitHeight

        PillCompact {
            id: pill

            showTime: !(Study.session?.config?.hideTime ?? true) || root.ui.revealTime
        }
    }

    Face {
        on: root.view === "card"
        implicitWidth: card.implicitWidth
        implicitHeight: card.implicitHeight

        PillCard {
            id: card

            ui: root.ui
            onStopRequested: root.askExit = true
        }
    }

    Cards {
        id: cards

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: root.slim ? parent.verticalCenter : undefined
        view: root.view
        appName: root.msgApp
        appIcon: root.msgIcon
        appText: root.msgText
        onKeepStudying: root.askExit = false
        onNextBlock: {
            Study.startNext();
            root.ui.sweep(true);
        }
    }

    Face {
        on: root.view === "summary"
        implicitWidth: summary.implicitWidth
        implicitHeight: summary.implicitHeight

        Summary {
            id: summary

            onAgain: {
                Study.clear();
                root.ui.mode = "setup";
            }
            onCloseRequested: root.ui.close()
        }
    }

    EdgeSweep {
        id: sweep

        anchors.fill: parent
        radius: root.radius
    }

    SequentialAnimation {
        id: flashAnim

        loops: 2

        Anim {
            target: root
            property: "flash"
            to: 1
            type: Anim.DefaultEffects
        }
        Anim {
            target: root
            property: "flash"
            to: 0
            type: Anim.SlowEffects
        }
    }

    Timer {
        id: msgTimer

        interval: Tokens.anim.durations.extraLarge * 2.5
        onTriggered: root.msgShown = false
    }

    Timer {
        id: cardTimer

        interval: Tokens.anim.durations.extraLarge * 3.5
        onTriggered: root.forceCard = false
    }

    function showMessage(app: string, icon: string, text: string): void {
        msgApp = app;
        msgIcon = icon;
        msgText = text;
        msgShown = true;
        msgTimer.restart();
        sweep.tick++;
    }

    Timer {
        id: noticeTimer

        interval: Tokens.anim.durations.expressiveSlowSpatial + Tokens.anim.durations.large
        onTriggered: {
            if (root.pendingNotice)
                root.showMessage(root.pendingNotice.app, root.pendingNotice.icon, "se cerró para la sesión");
            root.pendingNotice = null;
        }
    }

    Connections {
        target: root.ui

        function onModeChanged(): void {
            if (root.ui.mode === "setup")
                setup.reset();
            root.askExit = false;
            if (root.ui.mode === "study" && root.pendingNotice)
                noticeTimer.restart();
        }

        function onPillRequested(): void {
            root.forceCard = true;
            cardTimer.restart();
        }
    }

    Connections {
        target: Study

        function onDistraction(appName: string, iconName: string): void {
            root.showMessage(appName, iconName, "está bloqueado hasta el final");
        }

        function onClosedAtStart(appNames: string, iconName: string): void {
            if (root.ui.mode === "study")
                root.showMessage(appNames, iconName, "se cerró para la sesión");
            else
                root.pendingNotice = {app: appNames, icon: iconName};
        }

        function onPhaseEnded(from: string): void {
            if (from === "focus")
                flashAnim.restart();
        }

        function onFinished(): void {
            root.askExit = false;
            root.msgShown = false;
        }
    }
}
