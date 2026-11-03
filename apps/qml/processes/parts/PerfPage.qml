// Rendimiento: a diagnosis card that breathes faster and warms when the system is under pressure (PSI), five
// tiles with a rolling figure over the last minute's chart, the chosen resource's chart (compare with others,
// scrub, peaks marked with the app that caused them), what is using it, and its facts. No circular gauges.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: page

    property bool shown
    property bool live: true          // the page and the window can be seen: only then do its animations run
    property string resource: "cpu"
    property var compare: []
    readonly property var sum: procs.summary
    readonly property var hist: procs.systemHistory
    readonly property var resources: [
        {id: "cpu", label: "CPU", sub: (sum.cores_count ?? 0) + " hilos", role: "primary"},
        {id: "mem", label: "Memoria", sub: Fmt.mem(sum.total_memory ?? 0) + " en total", role: "tertiary"},
        {id: "gpu", label: "GPU", sub: sum.gpu === undefined || sum.gpu === null ? "sin datos" : "uso de motores", role: "secondary"},
        {id: "disk", label: "Disco", sub: "lectura + escritura", role: "success"},
        {id: "net", label: "Red", sub: "recibido + enviado", role: "primary"}
    ]
    readonly property real memPct: (sum.total_memory ?? 0) > 0 ? 100 * (sum.memory ?? 0) / sum.total_memory : 0
    readonly property var psi: sum.pressure ?? ({})
    readonly property bool hot: (sum.cpu ?? 0) > 60 || memPct > 85 || (sum.gpu ?? 0) > 70 || (psi.cpu ?? 0) > 20 || (psi.memory ?? 0) > 10 || (psi.io ?? 0) > 40
    readonly property var topCpu: { procs.stats; return procs.topApps("cpu"); }

    function value(id) {
        if (id === "cpu")
            return Fmt.pct(sum.cpu ?? 0);
        if (id === "mem")
            return Fmt.mem(sum.memory ?? 0);
        if (id === "gpu")
            return Fmt.pct(sum.gpu ?? -1);
        if (id === "disk")
            return Fmt.rate((sum.disk_read ?? 0) + (sum.disk_write ?? 0));
        return Fmt.rate((sum.net_rx ?? 0) + (sum.net_tx ?? 0));
    }
    function percentSeries(id) {
        const data = hist[id] ?? [];
        if (id === "cpu" || id === "gpu")
            return data;
        if (id === "mem")
            return data.map(v => (sum.total_memory ?? 0) > 0 ? 100 * v / sum.total_memory : 0);
        const top = Math.max(1, ...data);
        return data.map(v => 100 * v / top);
    }
    function diagnosis() {
        const t = topCpu.length ? topCpu[0] : null;
        if (!hot)
            return ["Todo va fluido", t ? "Nada compite por recursos · lo más activo es " + t.name + " (" + Fmt.pct(t.value) + " de un núcleo)" : "Nada compite por recursos"];
        const what = (sum.cpu ?? 0) > 60 || (psi.cpu ?? 0) > 20 ? "la CPU" : memPct > 85 || (psi.memory ?? 0) > 10 ? "la memoria" : (psi.io ?? 0) > 40 ? "el disco" : "la GPU";
        return ["Algo está exigiendo " + what, t ? t.name + " es lo que más pide ahora mismo · " + Fmt.pct(t.value) + " de un núcleo" : ""];
    }
    function handleKey(event) {
        const ids = resources.map(r => r.id);
        const i = ids.indexOf(resource);
        if (event.key === Qt.Key_Right || event.key === Qt.Key_Down || event.text === "j") {
            resource = ids[(i + 1) % ids.length];
            return true;
        }
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Up || event.text === "k") {
            resource = ids[(i + ids.length - 1) % ids.length];
            return true;
        }
        return false;
    }

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
            spacing: Theme.spacing.medium ?? 0

            // Diagnosis.
            Rectangle {
                id: hero

                width: parent.width
                height: Metrics.topAppBarMedium
                radius: Theme.rounding.extraLarge ?? 0
                clip: true
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop {
                        position: 0
                        color: page.hot ? Qt.tint(Theme.m3primaryContainer, Qt.alpha(Theme.m3error, 0.45)) : Theme.m3primaryContainer
                        Behavior on color { ColorAnimation { duration: Motion.ms("slowEffects") } }
                    }
                    GradientStop {
                        position: 1
                        color: page.hot ? Qt.tint(Theme.m3tertiaryContainer, Qt.alpha(Theme.m3error, 0.3)) : Theme.m3tertiaryContainer
                        Behavior on color { ColorAnimation { duration: Motion.ms("slowEffects") } }
                    }
                }

                ShapeEmblem {
                    id: orb

                    x: Theme.padding.large ?? 0
                    anchors.verticalCenter: parent.verticalCenter
                    shape: page.hot ? "burst" : "cookie"
                    color: Qt.alpha(Theme.m3onPrimaryContainer, 0.14)
                    icon: page.hot ? "bolt" : "monitoring"
                    iconColor: Theme.m3onPrimaryContainer

                    SequentialAnimation on scale {
                        running: !Motion.reduced && page.shown && page.live
                        loops: Animation.Infinite
                        NumberAnimation { to: 1.06; duration: Theme.duration(page.hot ? "normal" : "extraLarge") * 2; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bezier("standard") }
                        NumberAnimation { to: 1; duration: Theme.duration(page.hot ? "normal" : "extraLarge") * 2; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bezier("standard") }
                    }
                }

                Column {
                    anchors.left: orb.right
                    anchors.leftMargin: Theme.spacing.large ?? 0
                    anchors.right: pills.left
                    anchors.verticalCenter: parent.verticalCenter

                    Label {
                        width: parent.width
                        text: page.diagnosis()[0]
                        role: "headline.small"
                        color: Theme.m3onPrimaryContainer
                        elide: Text.ElideRight
                    }

                    Label {
                        width: parent.width
                        text: page.diagnosis()[1]
                        role: "body.medium"
                        color: Theme.m3onPrimaryContainer
                        opacity: 0.8
                        elide: Text.ElideRight
                    }
                }

                Row {
                    id: pills

                    anchors.right: parent.right
                    anchors.rightMargin: Theme.padding.large ?? 0
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacing.small ?? 0

                    Repeater {
                        model: [[(page.psi.cpu ?? 0).toFixed(1) + " %", "espera CPU"], [(page.psi.memory ?? 0).toFixed(1) + " %", "espera RAM"],
                                [(page.psi.io ?? 0).toFixed(1) + " %", "espera E/S"], [Fmt.age(page.sum.uptime ?? 0), "encendido"]]

                        Rectangle {
                            required property var modelData

                            width: Math.max(Metrics.listItemThreeLine, pillCol.implicitWidth + (Theme.padding.medium ?? 0) * 2)
                            height: Metrics.listItemOneLine
                            radius: Theme.rounding.large ?? 0
                            color: Qt.alpha(Theme.m3onPrimaryContainer, 0.12)

                            Column {
                                id: pillCol

                                anchors.centerIn: parent

                                Label {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: parent.parent.modelData[0]
                                    role: "title.medium"
                                    color: Theme.m3onPrimaryContainer
                                }

                                Label {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: parent.parent.modelData[1]
                                    role: "label.small"
                                    color: Theme.m3onPrimaryContainer
                                }
                            }
                        }
                    }
                }
            }

            // Tiles.
            Row {
                id: tiles

                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Repeater {
                    model: page.resources

                    Rectangle {
                        id: tile

                        required property var modelData
                        readonly property bool on: page.resource === modelData.id
                        readonly property color tone: Theme["m3" + modelData.role]

                        objectName: "tile-" + modelData.id
                        width: (tiles.width - tiles.spacing * 4) / 5
                        height: Metrics.topAppBarLarge - (Theme.spacing.small ?? 0)
                        radius: tileArea.pressed ? Theme.rounding.large ?? 0 : Theme.rounding.extraLarge ?? 0
                        color: Theme.m3surfaceContainerLow
                        border.width: on ? Metrics.textFieldFocusWidth : 0
                        border.color: tone
                        clip: true

                        Behavior on radius {
                            Anim {
                                kind: "fastSpatial"
                            }
                        }

                        LiveChart {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: parent.height * 0.62
                            series: [page.percentSeries(tile.modelData.id)]
                            colors: [tile.tone]
                            active: page.shown && page.live
                            maxValue: 105
                            grid: false
                            dot: false
                            pad: 0
                            lineWidth: 2
                            interval: procs.interval
                        }

                        Column {
                            x: Theme.padding.large ?? 0
                            y: Theme.padding.medium ?? 0

                            Row {
                                spacing: Theme.spacing.extraSmall ?? 0

                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Theme.spacing.small ?? 0
                                    height: width
                                    radius: width / 2
                                    color: tile.tone
                                }

                                Label {
                                    text: tile.modelData.label
                                    role: "label.large"
                                    color: Theme.m3onSurfaceVariant
                                }
                            }

                            RollingNumber {
                                text: page.value(tile.modelData.id)
                                role: "headline.small"
                                active: page.shown && page.live
                            }

                            Label {
                                text: tile.modelData.sub
                                role: "label.small"
                                color: Theme.m3onSurfaceVariant
                            }
                        }

                        MouseArea {
                            id: tileArea

                            anchors.fill: parent
                            onClicked: {
                                page.resource = tile.modelData.id;
                                page.compare = page.compare.filter(c => c !== tile.modelData.id);
                            }
                        }
                    }
                }
            }

            // The chosen resource and what uses it.
            Row {
                width: parent.width
                spacing: Theme.spacing.medium ?? 0

                Rectangle {
                    id: chartCard

                    readonly property var current: page.resources.find(r => r.id === page.resource)

                    width: (parent.width - parent.spacing) * 0.6
                    height: Math.max(chartColumn.implicitHeight, usage.implicitHeight) + (Theme.padding.large ?? 0) * 2
                    radius: Theme.rounding.extraLarge ?? 0
                    color: Theme.m3surfaceContainerLow

                    Column {
                        id: chartColumn

                        x: Theme.padding.large ?? 0
                        y: Theme.padding.large ?? 0
                        width: parent.width - x * 2
                        spacing: Theme.spacing.medium ?? 0

                        Label {
                            text: chartCard.current.label + " · último minuto"
                            role: "title.medium"
                        }

                        Flow {
                            width: parent.width
                            spacing: Theme.spacing.small ?? 0

                            Label {
                                height: Metrics.chipHeight
                                verticalAlignment: Text.AlignVCenter
                                text: "Comparar con"
                                role: "label.medium"
                                color: Theme.m3onSurfaceVariant
                            }

                            Repeater {
                                model: page.resources.filter(r => r.id !== page.resource)

                                Chip {
                                    required property var modelData

                                    kind: "filter"
                                    text: modelData.label
                                    selected: page.compare.indexOf(modelData.id) >= 0
                                    onClicked: page.compare = selected ? page.compare.filter(c => c !== modelData.id) : page.compare.concat([modelData.id])
                                }
                            }
                        }

                        LiveChart {
                            objectName: "perfChart"
                            width: parent.width
                            height: Metrics.topAppBarLarge * 1.6
                            active: page.shown && page.live
                            series: [page.percentSeries(page.resource)].concat(page.compare.map(c => page.percentSeries(c)))
                            colors: [Theme["m3" + chartCard.current.role]].concat(page.compare.map(c => Theme["m3" + page.resources.find(r => r.id === c).role]))
                            maxValue: 105
                            scrub: true
                            interval: procs.interval
                            formatValue: v => Math.round(v) + " %"
                            labelAt: i => {
                                const ago = Math.round(((page.hist.cpu ?? []).length - 1 - i) * procs.interval / 1000);
                                const top = page.resource === "cpu" ? (page.hist.top ?? [])[i] ?? "" : "";
                                return (ago ? "hace " + ago + " s" : "ahora") + (top ? " · " + top : "");
                            }
                            markers: page.resource === "cpu" ? Fmt.peaks(page.hist.cpu ?? [], 3).map(i => ({index: i, glyph: ((page.hist.top ?? [])[i] ?? "?").charAt(0).toUpperCase(), color: Theme.m3tertiaryContainer})) : []
                        }

                        // CPU: every thread as a dot that grows with its load.
                        Flow {
                            width: parent.width
                            visible: page.resource === "cpu"
                            spacing: Theme.spacing.small ?? 0

                            Repeater {
                                model: page.sum.cores ?? []

                                Rectangle {
                                    required property real modelData

                                    width: Metrics.chipHeight * 0.7
                                    height: width
                                    radius: width / 2
                                    color: Theme.m3primary
                                    opacity: 0.15 + Math.min(100, modelData) / 100 * 0.85
                                    scale: 0.55 + Math.min(100, modelData) / 100 * 0.45

                                    Behavior on scale {
                                        Anim {
                                            kind: "defaultSpatial"
                                        }
                                    }
                                    Behavior on opacity {
                                        Anim {
                                            kind: "slowEffects"
                                        }
                                    }
                                }
                            }
                        }

                        // Memory: in use, modified and cache.
                        Column {
                            width: parent.width
                            visible: page.resource === "mem"
                            spacing: Theme.spacing.small ?? 0

                            Row {
                                width: parent.width
                                height: Metrics.progressThickness * 3
                                spacing: Metrics.progressGap

                                Repeater {
                                    model: [[page.sum.memory ?? 0, Theme.m3tertiary], [page.sum.modified ?? 0, Theme.m3tertiaryContainer], [page.sum.cached ?? 0, Theme.m3secondaryContainer]]

                                    Rectangle {
                                        required property var modelData

                                        height: parent.height
                                        radius: height / 2
                                        width: Math.max(0, parent.width * modelData[0] / Math.max(1, page.sum.total_memory ?? 1))
                                        color: modelData[1]

                                        Behavior on width {
                                            Anim {
                                                kind: "defaultSpatial"
                                            }
                                        }
                                    }
                                }
                            }

                            Label {
                                text: "En uso " + Fmt.mem(page.sum.memory) + " · modificada " + Fmt.mem(page.sum.modified) + " · caché " + Fmt.mem(page.sum.cached) + " · total " + Fmt.mem(page.sum.total_memory)
                                role: "label.medium"
                                color: Theme.m3onSurfaceVariant
                            }
                        }
                    }
                }

                Rectangle {
                    width: (parent.width - parent.spacing) * 0.4
                    height: chartCard.height
                    radius: Theme.rounding.extraLarge ?? 0
                    color: Theme.m3surfaceContainerLow

                    Column {
                        id: usage

                        x: Theme.padding.large ?? 0
                        y: Theme.padding.large ?? 0
                        width: parent.width - x * 2
                        spacing: Theme.spacing.small ?? 0

                        Label {
                            text: "Qué lo está usando"
                            role: "title.medium"
                        }

                        Repeater {
                            model: { procs.stats; return page.resource === "net" ? [] : procs.topApps(page.resource); }

                            Row {
                                required property var modelData
                                readonly property real topValue: { procs.stats; return Math.max(0.0001, ...procs.topApps(page.resource).map(a => a.value)); }

                                width: usage.width
                                height: Metrics.listItemOneLine * 0.8
                                spacing: Theme.spacing.medium ?? 0

                                AppIcon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    source: parent.modelData.icon
                                    tint: parent.modelData.tint
                                    label: parent.modelData.name
                                    size: Metrics.chipHeight
                                }

                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - x - valueLabel.width - parent.spacing
                                    spacing: Theme.spacing.extraSmall ?? 0

                                    Label {
                                        width: parent.width
                                        text: parent.parent.modelData.name
                                        role: "body.medium"
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        width: parent.width
                                        height: Metrics.progressThickness * 1.5
                                        radius: height / 2
                                        color: Theme.m3surfaceContainerHighest

                                        Rectangle {
                                            height: parent.height
                                            radius: height / 2
                                            width: parent.width * Math.max(0.02, parent.parent.parent.modelData.value / parent.parent.parent.topValue)
                                            color: (parent.parent.parent.modelData.tint ?? "") !== "" ? Qt.tint(Theme.m3primary, Qt.alpha(Qt.color(parent.parent.parent.modelData.tint), 0.6)) : Theme.m3primary

                                            Behavior on width {
                                                Anim {
                                                    kind: "defaultSpatial"
                                                }
                                            }
                                        }
                                    }
                                }

                                Label {
                                    id: valueLabel

                                    anchors.verticalCenter: parent.verticalCenter
                                    text: page.resource === "mem" ? Fmt.mem(parent.modelData.value) : page.resource === "disk" ? Fmt.rate(parent.modelData.value) : Fmt.pct(parent.modelData.value)
                                    role: "label.large"
                                }
                            }
                        }

                        Label {
                            visible: page.resource === "net"
                            width: parent.width
                            wrapMode: Text.Wrap
                            text: "El tráfico por app necesita permisos de administrador; aquí se ve el total del equipo."
                            role: "body.small"
                            color: Theme.m3onSurfaceVariant
                        }

                        Grid {
                            columns: 2
                            spacing: Theme.spacing.small ?? 0
                            width: parent.width

                            Repeater {
                                model: page.resource === "cpu" ? [["Temperatura", page.sum.temps?.cpu ? Math.round(page.sum.temps.cpu) + " °C" : "—"], ["Carga 1/5/15", (page.sum.load ?? []).map(v => Number(v).toFixed(2)).join(" · ")], ["Procesos", String(page.sum.count ?? 0)], ["Hilos", String(page.sum.threads ?? 0)]]
                                     : page.resource === "mem" ? [["Swap", Fmt.mem(page.sum.swap) + " / " + Fmt.mem(page.sum.total_swap)], ["Espera de RAM", (page.psi.memory ?? 0).toFixed(1) + " %"], ["En uso", Math.round(page.memPct) + " %"], ["Caché", Fmt.mem(page.sum.cached)]]
                                     : page.resource === "gpu" ? [["Memoria de vídeo", page.sum.gpu_memory ? Fmt.mem(page.sum.gpu_memory) : "—"], ["Temperatura", page.sum.temps?.gpu ? Math.round(page.sum.temps.gpu) + " °C" : "—"]]
                                     : page.resource === "disk" ? [["Lectura", Fmt.rate(page.sum.disk_read)], ["Escritura", Fmt.rate(page.sum.disk_write)], ["Espera de E/S", (page.psi.io ?? 0).toFixed(1) + " %"], ["Temperatura", page.sum.temps?.disk ? Math.round(page.sum.temps.disk) + " °C" : "—"]]
                                     : [["Recibido", Fmt.rate(page.sum.net_rx)], ["Enviado", Fmt.rate(page.sum.net_tx)]]

                                Rectangle {
                                    required property var modelData

                                    width: (usage.width - Theme.spacing.small) / 2
                                    height: Metrics.listItemOneLine
                                    radius: Theme.rounding.medium ?? 0
                                    color: Theme.m3surfaceContainer

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
}
