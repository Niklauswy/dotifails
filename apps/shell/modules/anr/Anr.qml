pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services
import "AnrLogic.js" as Logic

// A Wysun card for windows that stop responding. Hyprland still detects it and opens its own dialog
// (its ANR option is left as it is); when that dialog appears the shell reads which window hung, shows this
// card over it (the window greyed with a sheen), and only then moves Hyprland's dialog out of sight
// (special:wysun-anr). Esperar closes the dialog; Forzar cierre kills the hung client. If anything fails before the
// card shows, Hyprland's dialog stays visible.
Scope {
    id: root

    property string dialog                      // address of Hyprland's dialog, no 0x
    property var hung: null                     // {address, cls, title, pid}
    property var place: null                    // {monitor, x, y, width, height}
    readonly property bool showing: hung !== null

    function reset(): void {
        hung = null;
        place = null;
        dialog = "";
    }

    function wait(): void {
        if (dialog)
            Hypr.dispatch(Hypr.usingLua ? `hl.dsp.window.close({window="address:0x${dialog}"})` : `closewindow address:0x${dialog}`);
        reset();
    }

    function forceQuit(): void {
        if (hung && hung.pid > 1)
            Quickshell.execDetached(["kill", "-KILL", String(hung.pid)]);
        if (dialog)
            Hypr.dispatch(Hypr.usingLua ? `hl.dsp.window.close({window="address:0x${dialog}"})` : `closewindow address:0x${dialog}`);
        reset();
    }

    Connections {
        target: Hyprland

        function onRawEvent(event: HyprlandEvent): void {
            if (event.name === "openwindow") {
                const parts = event.data.split(",");
                if (parts.length >= 4 && Logic.isAnrDialog(parts[2], parts.slice(3).join(","))) {
                    root.dialog = parts[0].replace(/^0x/, "");
                    clients.running = true;
                }
            } else if (event.name === "closewindow" && root.dialog && event.data.replace(/^0x/, "") === root.dialog) {
                root.reset();          // the app answered again, or someone closed the dialog
            }
        }
    }

    // Who hung: the dialog's command line names the window; hyprctl knows the windows.
    Process {
        id: clients

        property var windows: []

        command: ["hyprctl", "-j", "clients"]
        stdout: StdioCollector {
            onStreamFinished: {
                let list = [];
                try {
                    list = JSON.parse(text);
                } catch (e) {
                    return;
                }
                clients.windows = list;
                const box = list.find(c => String(c.address).replace(/^0x/, "") === root.dialog);
                if (box) {
                    cmdline.path = "/proc/" + box.pid + "/cmdline";
                    cmdline.reload();
                }
            }
        }
    }

    FileView {
        id: cmdline

        blockLoading: true
        onLoaded: {
            const wanted = Logic.parseCmdline(text());
            const windows = clients.windows.map(c => ({address: c.address, cls: c.class, title: c.title, pid: c.pid,
                                                        at: c.at, size: c.size, monitor: c.monitor}));
            const found = Logic.matchWindow(windows, wanted);
            if (!found)
                return;
            const full = windows.find(w => w.address === found.address);
            const monitor = Hypr.monitors.values.find(m => m.id === full.monitor) ?? null;
            root.place = monitor ? {monitor: monitor.name, x: full.at[0] - monitor.x, y: full.at[1] - monitor.y,
                                    width: full.size[0], height: full.size[1]} : null;
            root.hung = found;
        }
    }

    LazyLoader {
        active: root.showing && root.place !== null

        Variants {
            model: Quickshell.screens.filter(s => s.name === root.place?.monitor)

            StyledWindow {
                id: win

                required property ShellScreen modelData
                readonly property var entry: DesktopEntries.heuristicLookup(root.hung?.cls ?? "")
                readonly property string appName: entry?.name ?? root.hung?.cls ?? ""

                screen: modelData
                name: "anr"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                mask: Region {
                    item: card
                }

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                Component.onCompleted: {
                    // The card is up: now Hyprland's own dialog can step aside.
                    if (root.dialog)
                        Hypr.dispatch(Hypr.usingLua ? `hl.dsp.window.move({workspace="special:wysun-anr",follow=false,window="address:0x${root.dialog}"})`
                                                    : `movetoworkspacesilent special:wysun-anr,address:0x${root.dialog}`);
                }

                // The hung window, greyed, with a sheen sweeping across.
                Item {
                    x: root.place?.x ?? 0
                    y: root.place?.y ?? 0
                    width: root.place?.width ?? 0
                    height: root.place?.height ?? 0
                    clip: true

                    Rectangle {
                        anchors.fill: parent
                        radius: Tokens.rounding.large
                        color: Qt.alpha(Colours.palette.m3scrim, 0.62)
                    }

                    Rectangle {
                        id: sheen

                        width: parent.width * 0.4
                        height: parent.height
                        x: -width
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: "transparent" }
                            GradientStop { position: 0.5; color: Qt.alpha(Colours.palette.m3onSurface, 0.08) }
                            GradientStop { position: 1; color: "transparent" }
                        }

                        NumberAnimation on x {
                            from: -sheen.width
                            to: sheen.parent.width
                            duration: Tokens.anim.durations.extraLarge * 2
                            loops: Animation.Infinite
                            running: root.showing
                        }
                    }
                }

                StyledRect {
                    id: card

                    x: (root.place?.x ?? 0) + ((root.place?.width ?? 0) - width) / 2
                    y: (root.place?.y ?? 0) + ((root.place?.height ?? 0) - height) / 2
                    implicitWidth: Tokens.padding.extraExtraLarge * 8
                    implicitHeight: content.implicitHeight + Tokens.padding.extraLarge * 2
                    radius: Tokens.rounding.extraLarge
                    color: Colours.palette.m3surfaceContainerHigh
                    scale: root.showing ? 1 : 0.94
                    opacity: root.showing ? 1 : 0

                    Behavior on scale {
                        Anim {
                            type: Anim.DefaultSpatial
                        }
                    }
                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }

                    Column {
                        id: content

                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Tokens.padding.extraLarge
                        spacing: Tokens.spacing.medium

                        StyledRect {
                            implicitWidth: Tokens.padding.extraExtraLarge
                            implicitHeight: implicitWidth
                            radius: Tokens.rounding.large
                            color: Colours.palette.m3errorContainer

                            Image {
                                id: appImage

                                anchors.centerIn: parent
                                width: parent.width * 0.6
                                height: width
                                visible: status === Image.Ready
                                source: win.entry?.icon ? Quickshell.iconPath(win.entry.icon, true) : ""
                                sourceSize: Qt.size(width * 2, height * 2)
                            }

                            MaterialIcon {
                                anchors.centerIn: parent
                                visible: appImage.status !== Image.Ready
                                text: "hourglass_top"
                                color: Colours.palette.m3onErrorContainer
                            }
                        }

                        StyledText {
                            width: parent.width
                            text: win.appName + " no responde"
                            font: Tokens.font.headline.small
                            wrapMode: Text.Wrap
                        }

                        StyledText {
                            width: parent.width
                            text: "Puede que se recupere sola. Si fuerzas el cierre se perderá lo que no hayas guardado."
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.body.medium
                            wrapMode: Text.Wrap
                        }

                        Row {
                            width: parent.width
                            spacing: Tokens.spacing.small

                            StyledText {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Esperando respuesta"
                                color: Colours.palette.m3onSurfaceVariant
                                font: Tokens.font.label.medium
                            }

                            StyledRect {
                                id: track

                                anchors.verticalCenter: parent.verticalCenter
                                implicitWidth: parent.width - x
                                implicitHeight: Tokens.padding.extraSmall
                                radius: height / 2
                                clip: true
                                color: Colours.palette.m3surfaceContainerHighest

                                StyledRect {
                                    implicitHeight: parent.height
                                    radius: height / 2
                                    color: Colours.palette.m3tertiary
                                    implicitWidth: 0

                                    NumberAnimation on implicitWidth {
                                        from: 0
                                        to: track.width
                                        duration: Tokens.anim.durations.extraLarge * 8
                                        running: root.showing
                                    }
                                }
                            }
                        }

                        Row {
                            anchors.right: parent.right
                            spacing: Tokens.spacing.small

                            StyledRect {
                                implicitWidth: waitLabel.implicitWidth + Tokens.padding.large * 2
                                implicitHeight: waitLabel.implicitHeight + Tokens.padding.medium * 2
                                radius: height / 2
                                color: Colours.palette.m3secondaryContainer

                                StyledText {
                                    id: waitLabel

                                    anchors.centerIn: parent
                                    text: "Esperar"
                                    color: Colours.palette.m3onSecondaryContainer
                                    font: Tokens.font.label.large
                                }

                                StateLayer {
                                    color: Colours.palette.m3onSecondaryContainer
                                    onClicked: root.wait()
                                }
                            }

                            StyledRect {
                                implicitWidth: killRow.implicitWidth + Tokens.padding.large * 2
                                implicitHeight: killRow.implicitHeight + Tokens.padding.medium * 2
                                radius: height / 2
                                color: Colours.palette.m3errorContainer

                                Row {
                                    id: killRow

                                    anchors.centerIn: parent
                                    spacing: Tokens.spacing.extraSmall

                                    MaterialIcon {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "bolt"
                                        color: Colours.palette.m3onErrorContainer
                                    }

                                    StyledText {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "Forzar cierre"
                                        color: Colours.palette.m3onErrorContainer
                                        font: Tokens.font.label.large
                                    }
                                }

                                StateLayer {
                                    color: Colours.palette.m3onErrorContainer
                                    onClicked: root.forceQuit()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
