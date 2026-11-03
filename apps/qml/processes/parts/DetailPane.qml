// The selected process or app: its state shape and real icon, actions, a live chart (CPU, memory, GPU, disk) with a
// scrub guide and peaks marked with the process that caused them, six quick figures and tabs with details,
// threads, open files and network connections (or the processes of an app).
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Rectangle {
    id: pane

    readonly property var item: procs.selected
    readonly property bool has: !!item.key
    readonly property bool group: !!item.group
    readonly property var hist: procs.history
    readonly property var info: procs.details
    property bool live: true          // the page and the window can be seen: only then do its animations run
    property string metric: "cpu"
    property string tab: group ? "children" : "info"
    readonly property var groupTabs: [{id: "children", text: "Procesos"}, {id: "info", text: "Detalles"}]
    readonly property var processTabs: [{id: "info", text: "Detalles"}, {id: "threads", text: "Hilos"},
                                         {id: "files", text: "Archivos"}, {id: "net", text: "Red"}]
    // Stable arrays: a new `tabs` identity every tick rebuilt the TabBar and restarted its indicator springs forever.
    readonly property var tabs: group ? groupTabs : processTabs
    readonly property color tintColour: (item.tint ?? "") !== "" ? Qt.color(item.tint) : Theme.m3primary
    readonly property color lineColour: Qt.tint(Theme.m3primary, Qt.alpha(tintColour, 0.6))
    readonly property var series: hist[metric] ?? []

    signal closeRequested

    function cycleTab(step) {
        const ids = tabs.map(t => t.id);
        tab = ids[(Math.max(0, ids.indexOf(tab)) + step + ids.length) % ids.length];
    }

    function metricValue() {
        if (metric === "cpu")
            return Fmt.pct(item.cpu ?? 0);
        if (metric === "mem")
            return Fmt.mem(item.mem ?? 0);
        if (metric === "gpu")
            return (item.gpu ?? -1) < 0 ? "—" : Math.round(item.gpu) + " %";
        return Fmt.rate(item.io ?? 0);
    }

    onGroupChanged: tab = group ? "children" : "info"

    radius: Theme.rounding.extraLarge ?? 0
    color: Theme.m3surfaceContainer

    EmptyState {
        anchors.centerIn: parent
        visible: !pane.has
        icon: "touch_app"
        title: "Elige un proceso"
        message: "Verás su actividad, sus hilos y sus archivos"
    }

    Item {
        id: body

        anchors.fill: parent
        anchors.margins: Theme.padding.large ?? 0
        visible: pane.has

        // Header: state shape with the icon, name, PID and state.
        Row {
            id: head

            width: parent.width
            spacing: Theme.spacing.medium ?? 0

            StateShape {
                id: stateShape

                state: pane.group ? "G" : (pane.item.state ?? "")
                size: Metrics.emblemSize
                color: Qt.tint(Theme.m3surfaceContainerHighest, Qt.alpha(pane.tintColour, 0.32))

                // One lobe per new sample while the process works: the pane idles between samples.
                Connections {
                    target: procs
                    enabled: !procs.frozen && pane.visible

                    function onSampled() {
                        stateShape.nudge();
                    }
                }

                AppIcon {
                    anchors.centerIn: parent
                    source: pane.item.icon ?? ""
                    tint: pane.item.tint ?? ""
                    label: pane.item.title ?? ""
                    size: Metrics.iconButtonSize
                    color: Qt.alpha(Theme.m3surface, 0)
                }
            }

            Column {
                width: parent.width - x - closeButton.width
                spacing: Theme.spacing.extraSmall ?? 0

                Label {
                    width: parent.width
                    text: pane.item.title ?? ""
                    role: "title.large"
                    elide: Text.ElideRight
                }

                Label {
                    width: parent.width
                    text: pane.group ? (pane.item.kids ?? 0) + " procesos · " + (pane.item.user ?? "")
                                     : "PID " + (pane.item.pid ?? "") + " · " + (pane.item.user ?? "")
                    role: "label.medium"
                    color: Theme.m3onSurfaceVariant
                    font.family: Theme.font.family?.mono ?? ""
                    elide: Text.ElideRight
                }

                Rectangle {
                    width: pillRow.implicitWidth + (Theme.padding.medium ?? 0) * 2
                    height: Metrics.chipHeight * 0.75
                    radius: height / 2
                    color: pane.group ? Theme.m3secondaryContainer : Qt.alpha(Theme["m3" + Fmt.stateColourRole(pane.item.state)], 0.22)

                    Row {
                        id: pillRow

                        anchors.centerIn: parent
                        spacing: Theme.spacing.extraSmall ?? 0

                        Rectangle {
                            visible: !pane.group
                            anchors.verticalCenter: parent.verticalCenter
                            width: Theme.spacing.small ?? 0
                            height: width
                            radius: width / 2
                            color: Theme["m3" + Fmt.stateColourRole(pane.item.state)]
                        }

                        Label {
                            text: pane.group ? "Aplicación" : (pane.item.stateLabel ?? "")
                            role: "label.medium"
                        }
                    }
                }
            }

            IconButton {
                id: closeButton

                icon: "close"
                onClicked: pane.closeRequested()
            }
        }

        // Actions.
        Flow {
            id: actionsRow

            anchors.top: head.bottom
            anchors.topMargin: Theme.spacing.medium ?? 0
            width: parent.width
            spacing: Theme.spacing.small ?? 0

            Button {
                objectName: "terminateButton"
                type: "tonal"
                icon: "cancel"
                text: pane.group ? "Cerrar app" : "Terminar"
                containerColor: Theme.m3errorContainer
                contentRestColor: Theme.m3onErrorContainer
                onClicked: procs.act("terminate")
            }

            IconButton {
                type: "tonal"
                icon: "bolt"
                onClicked: procs.act("kill")
            }

            IconButton {
                type: "tonal"
                icon: (pane.item.state ?? "") === "T" ? "play_arrow" : "pause"
                onClicked: procs.act("pause")
            }

            IconButton {
                type: "tonal"
                icon: "swap_vert"
                onClicked: procs.act("priority")
            }

            IconButton {
                type: "tonal"
                icon: "my_location"
                enabled: (pane.item.windowAddress ?? "") !== ""
                onClicked: procs.locate()
            }

            IconButton {
                type: "tonal"
                icon: "open_in_new"
                enabled: (pane.item.windowAddress ?? "") !== ""
                onClicked: procs.focusWindow()
            }
        }

        // Live chart.
        Rectangle {
            id: chartCard

            anchors.top: actionsRow.bottom
            anchors.topMargin: Theme.spacing.medium ?? 0
            width: parent.width
            height: Metrics.topAppBarLarge + Metrics.listItemTwoLine + Metrics.tabHeight
            radius: Theme.rounding.large ?? 0
            color: Theme.m3surfaceContainerHigh

            Row {
                id: chartHead

                x: Theme.padding.medium ?? 0
                y: Theme.padding.medium ?? 0
                spacing: Theme.spacing.small ?? 0

                RollingNumber {
                    objectName: "detailFigure"
                    text: pane.metricValue()
                    role: "headline.medium"
                    active: pane.live
                }

                Label {
                    anchors.bottom: parent.bottom
                    text: pane.metric === "cpu" ? "de un núcleo" : pane.metric === "mem" ? "residente" : pane.metric === "gpu" ? "motores" : "lectura + escritura"
                    role: "label.medium"
                    color: Theme.m3onSurfaceVariant
                }
            }

            TabBar {
                id: metricSwitch

                anchors.top: chartHead.bottom
                anchors.topMargin: Theme.spacing.small ?? 0
                x: Theme.padding.medium ?? 0
                width: parent.width - x * 2
                variant: "secondary"
                tabs: [{id: "cpu", text: "CPU"}, {id: "mem", text: "Memoria"}, {id: "gpu", text: "GPU"}, {id: "io", text: "Disco"}]
                currentId: pane.metric
                onActivated: id => pane.metric = id
            }

            LiveChart {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: metricSwitch.bottom
                anchors.bottom: parent.bottom
                anchors.margins: Theme.padding.medium ?? 0
                series: [pane.series]
                colors: [pane.lineColour]
                active: pane.live
                interval: procs.interval
                scrub: true
                maxValue: pane.metric === "gpu" ? 100 : 0
                formatValue: v => pane.metric === "cpu" || pane.metric === "gpu" ? Fmt.pct(v) : pane.metric === "mem" ? Fmt.mem(v) : Fmt.rate(v)
                labelAt: i => {
                    const ago = Math.round((pane.series.length - 1 - i) * procs.interval / 1000);
                    const top = pane.group && pane.metric === "cpu" ? (pane.hist.top ?? [])[i] ?? "" : "";
                    return (ago ? "hace " + ago + " s" : "ahora") + (top ? " · " + top : "");
                }
                markers: pane.group && pane.metric === "cpu" ? Fmt.peaks(pane.series, 3).map(i => ({index: i, glyph: ((pane.hist.top ?? [])[i] ?? "?").charAt(0).toUpperCase(), color: Theme.m3tertiaryContainer})) : []
            }
        }

        // Quick figures.
        Grid {
            id: figures

            anchors.top: chartCard.bottom
            anchors.topMargin: Theme.spacing.small ?? 0
            width: parent.width
            columns: 3
            spacing: Theme.spacing.small ?? 0

            Repeater {
                model: [
                    ["Hilos", String(pane.item.threads ?? 0)],
                    [pane.group ? "Procesos" : "Prioridad", pane.group ? String(pane.item.kids ?? 0) : ((pane.item.nice ?? 0) > 0 ? "+" : "") + (pane.item.nice ?? 0)],
                    ["Activo hace", Fmt.age(pane.item.age ?? 0)],
                    ["Disco", Fmt.rate(pane.item.io ?? 0)],
                    ["Memoria", Fmt.mem(pane.item.mem ?? 0)],
                    ["Archivos", pane.group ? "—" : String(pane.info.file_count ?? "—")]
                ]

                Rectangle {
                    required property var modelData

                    width: (figures.width - figures.spacing * 2) / 3
                    height: Metrics.listItemOneLine
                    radius: Theme.rounding.medium ?? 0
                    color: Theme.m3surfaceContainerLow

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        x: Theme.padding.medium ?? 0

                        Label {
                            text: parent.parent.modelData[0]
                            role: "label.small"
                            color: Theme.m3onSurfaceVariant
                        }

                        Label {
                            text: parent.parent.modelData[1]
                            role: "title.small"
                        }
                    }
                }
            }
        }

        TabBar {
            id: tabBar

            anchors.top: figures.bottom
            anchors.topMargin: Theme.spacing.small ?? 0
            width: parent.width
            variant: "secondary"
            tabs: pane.tabs
            currentId: pane.tab
            onActivated: id => pane.tab = id
        }

        ListView {
            id: tabList

            anchors.top: tabBar.bottom
            anchors.bottom: parent.bottom
            width: parent.width
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: pane.tab === "children" ? (pane.info.children ?? [])
                 : pane.tab === "threads" ? (pane.info.threads ?? [])
                 : pane.tab === "files" ? (pane.info.files ?? [])
                 : pane.tab === "net" ? (pane.info.connections ?? [])
                 : pane.infoRows()
            delegate: Item {
                id: entry

                required property var modelData
                required property int index

                width: tabList.width
                height: Metrics.chipHeight + (Theme.spacing.small ?? 0)

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.rounding.small ?? 0
                    color: Theme.m3onSurface
                    opacity: rowHover.hovered ? Metrics.stateHover : 0
                }

                HoverHandler {
                    id: rowHover
                }

                TapHandler {
                    enabled: pane.tab === "children" || (pane.tab === "info" && !!entry.modelData.key)
                    onTapped: procs.select(entry.modelData.key)
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Theme.padding.small ?? 0
                    width: parent.width - x * 2
                    elide: Text.ElideMiddle
                    role: pane.tab === "info" ? "body.small" : "label.medium"
                    font.family: pane.tab === "files" || pane.tab === "net" ? (Theme.font.family?.mono ?? "") : (Theme.font.family?.sans ?? "")
                    color: pane.tab === "info" && entry.modelData.key ? Theme.m3primary : Theme.m3onSurface
                    text: pane.tab === "children" ? entry.modelData.name + "  ·  " + entry.modelData.pid + "  ·  " + Fmt.pct(entry.modelData.cpu) + "  ·  " + Fmt.mem(entry.modelData.mem)
                        : pane.tab === "threads" ? entry.modelData.tid + "  " + entry.modelData.name + "  ·  " + entry.modelData.state + "  ·  " + Number(entry.modelData.cpu_time).toFixed(1) + " s"
                        : pane.tab === "files" ? entry.modelData[0] + "  " + entry.modelData[1]
                        : pane.tab === "net" ? entry.modelData[0] + "  " + entry.modelData[1] + " → " + entry.modelData[2] + "  " + entry.modelData[3]
                        : entry.modelData.label + ":  " + entry.modelData.value
                }
            }

            Label {
                anchors.centerIn: parent
                visible: tabList.count === 0
                text: pane.tab === "net" ? "Sin conexiones abiertas" : pane.info.error ? pane.info.error : "Sin datos"
                role: "body.small"
                color: Theme.m3onSurfaceVariant
            }
        }

        ScrollIndicator {
            anchors.right: parent.right
            anchors.top: tabList.top
            anchors.bottom: tabList.bottom
            flickable: tabList
        }
    }

    function infoRows() {
        const d = info;
        const rows = [];
        if (group) {
            rows.push({label: "Aplicación", value: item.app ?? ""});
            rows.push({label: "Procesos", value: String(item.kids ?? 0)});
            rows.push({label: "Usuario", value: item.user ?? ""});
            return rows;
        }
        rows.push({label: "Comando", value: d.command || "—"});
        rows.push({label: "Ejecutable", value: d.exe || "—"});
        rows.push({label: "Directorio", value: d.cwd || "—"});
        rows.push({label: "Proceso padre", value: String(item.ppid ?? "—")});
        rows.push({label: "Usuario", value: item.user ?? ""});
        rows.push({label: "cgroup", value: (d.cgroup || "—").replace(/^0::/, "")});
        if (d.context_switches)
            rows.push({label: "Cambios de contexto", value: (d.context_switches.voluntary_ctxt_switches ?? "") + " / " + (d.context_switches.nonvoluntary_ctxt_switches ?? "")});
        return rows;
    }
}
