// Apps: the open windows by Hyprland workspace (the current one marked) with a live thumbnail from the shell, the
// app's real icon and its CPU and memory; apps without a window in a row underneath. A window opens into a sheet
// with a container transform (bigger thumbnail, rolling figures, chart and its processes); Escape shrinks it back.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: page

    property bool shown
    property int selected: 0
    readonly property var flat: {
        const out = [];
        for (const space of procs.workspaces)
            for (const w of space.windows)
                out.push(Object.assign({kind: "window", ws: space.id}, w));
        for (const b of procs.background)
            out.push(Object.assign({kind: "background"}, b));
        return out;
    }
    readonly property var stats: procs.stats

    signal showProcesses(string app)

    function tileFor(index) {
        return column.findTile(index);
    }
    function openSheet(index) {
        const entry = flat[index];
        if (!entry || entry.kind !== "window")
            return;
        const tile = tileFor(index);
        if (tile)
            sheetHost.open(tile, sheetComponent, {entry: entry});
    }
    function handleKey(event) {
        if (sheetHost.opened) {
            if (event.key === Qt.Key_Escape) {
                sheetHost.close();
                return true;
            }
            return false;
        }
        const perRow = Math.max(1, Math.floor((column.width + spacingH) / (tileWidth + spacingH)));
        const step = {[Qt.Key_Right]: 1, [Qt.Key_Left]: -1, [Qt.Key_Down]: perRow, [Qt.Key_Up]: -perRow}[event.key]
            ?? {j: perRow, k: -perRow}[event.text];
        if (step !== undefined) {
            selected = Math.max(0, Math.min(flat.length - 1, selected + step));
            return true;
        }
        const entry = flat[selected];
        if (!entry)
            return false;
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (entry.kind === "window")
                openSheet(selected);
            else
                showProcesses(entry.app);
            return true;
        }
        if (event.key === Qt.Key_Delete) {
            procs.closeApp(entry.app, event.modifiers & Qt.ShiftModifier);
            return true;
        }
        if (event.text === "l" || event.text === "L") {
            procs.locateApp(entry.app);
            return true;
        }
        if (event.text === "w") {
            procs.focusApp(entry.app);
            return true;
        }
        if (event.text === "i") {
            showProcesses(entry.app);
            return true;
        }
        return false;
    }

    readonly property real spacingH: Theme.spacing.medium ?? 0
    readonly property real tileWidth: Metrics.drawerWidth

    visible: opacity > 0
    opacity: shown ? 1 : 0

    Behavior on opacity {
        Anim {
            kind: "defaultEffects"
        }
    }

    Flickable {
        id: flick

        anchors.fill: parent
        anchors.margins: Theme.spacing.medium ?? 0
        contentHeight: column.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: column

            width: flick.width
            spacing: Theme.spacing.large ?? 0

            function findTile(index) {
                for (let i = 0; i < spaces.count; i++) {
                    const found = spaces.itemAt(i).tileAt(index);
                    if (found)
                        return found;
                }
                return null;
            }

            Row {
                spacing: Theme.spacing.medium ?? 0

                Label {
                    text: "Ventanas abiertas"
                    role: "headline.small"
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Por espacio de trabajo · flechas para moverte · Enter abre · L localiza · Supr cierra"
                    role: "body.small"
                    color: Theme.m3onSurfaceVariant
                }
            }

            Repeater {
                id: spaces

                model: procs.workspaces

                Column {
                    id: space

                    required property var modelData
                    required property int index
                    readonly property int base: {
                        let n = 0;
                        for (let i = 0; i < index; i++)
                            n += procs.workspaces[i].windows.length;
                        return n;
                    }

                    function tileAt(i) {
                        const local = i - base;
                        return local >= 0 && local < tiles.count ? tiles.itemAt(local) : null;
                    }

                    width: column.width
                    spacing: Theme.spacing.small ?? 0

                    Row {
                        spacing: Theme.spacing.small ?? 0

                        Rectangle {
                            width: Metrics.chipHeight
                            height: width
                            radius: Theme.rounding.medium ?? 0
                            color: space.modelData.current ? Theme.m3primary : Theme.m3secondaryContainer

                            Label {
                                anchors.centerIn: parent
                                text: space.modelData.id
                                role: "label.large"
                                color: space.modelData.current ? Theme.m3onPrimary : Theme.m3onSecondaryContainer
                            }
                        }

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Espacio " + space.modelData.id
                            role: "title.medium"
                        }

                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: space.modelData.windows.length + (space.modelData.windows.length === 1 ? " ventana" : " ventanas") + (space.modelData.current ? " · estás aquí" : "")
                            role: "body.small"
                            color: Theme.m3onSurfaceVariant
                        }
                    }

                    Flow {
                        width: parent.width
                        spacing: page.spacingH

                        Repeater {
                            id: tiles

                            model: space.modelData.windows

                            WindowTile {
                                required property var modelData
                                required property int index
                                readonly property int flatIndex: space.base + index

                                width: page.tileWidth
                                entry: modelData
                                stat: page.stats[modelData.app] ?? ({})
                                selected: page.selected === flatIndex
                                onClicked: {
                                    page.selected = flatIndex;
                                    page.openSheet(flatIndex);
                                }
                                onLocate: procs.locateApp(modelData.app)
                                onCloseApp: procs.closeApp(modelData.app, false)
                            }
                        }
                    }
                }
            }

            Column {
                width: column.width
                spacing: Theme.spacing.small ?? 0
                visible: procs.background.length > 0

                Label {
                    text: "En segundo plano · sin ventana"
                    role: "title.medium"
                }

                Flow {
                    width: parent.width
                    spacing: Theme.spacing.small ?? 0

                    Repeater {
                        model: procs.background

                        Rectangle {
                            id: pill

                            required property var modelData
                            required property int index
                            readonly property int flatIndex: page.flat.length - procs.background.length + index
                            readonly property var stat: page.stats[modelData.app] ?? ({})

                            width: pillRow.implicitWidth + (Theme.padding.medium ?? 0) * 2
                            height: Metrics.iconButtonSize
                            radius: height / 2
                            color: page.selected === flatIndex ? Theme.m3secondaryContainer : Theme.m3surfaceContainerLow
                            border.width: page.selected === flatIndex ? Metrics.textFieldFocusWidth : 0
                            border.color: Theme.m3primary

                            Row {
                                id: pillRow

                                anchors.centerIn: parent
                                spacing: Theme.spacing.small ?? 0

                                AppIcon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    source: pill.modelData.icon
                                    tint: pill.modelData.tint
                                    label: pill.modelData.name
                                    size: Metrics.chipAvatarSize
                                }

                                Label {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: pill.modelData.name
                                    role: "label.large"
                                }

                                Label {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Fmt.pct(pill.stat.cpu ?? 0) + " · " + Fmt.mem(pill.stat.mem ?? 0)
                                    role: "label.small"
                                    color: Theme.m3onSurfaceVariant
                                    font.family: Theme.font.family?.mono ?? ""
                                }
                            }

                            TapHandler {
                                onTapped: page.selected = pill.flatIndex
                                onDoubleTapped: page.showProcesses(pill.modelData.app)
                            }
                        }
                    }
                }
            }
        }
    }

    ScrollIndicator {
        anchors.right: parent.right
        height: parent.height
        flickable: flick
    }

    EmptyState {
        anchors.centerIn: parent
        visible: page.flat.length === 0
        icon: "web_asset_off"
        title: "No hay ventanas abiertas"
        message: "Aquí aparecerán las ventanas de Hyprland con lo que gasta cada una"
    }

    ContainerTransform {
        id: sheetHost

        objectName: "appSheetHost"
        anchors.fill: parent
        containerColor: Theme.m3surfaceContainer
        endRadius: Theme.rounding.extraLarge ?? 0
    }

    Component {
        id: sheetComponent

        AppSheet {
            onCloseRequested: sheetHost.close()
            onShowProcesses: app => {
                sheetHost.close();
                page.showProcesses(app);
            }
        }
    }
}
