pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Live process list: filter, sort, tree view and per-process actions.
PageBase {
    id: root

    function size(bytes: var): string {
        if (bytes === null || bytes === undefined)
            return "—";
        const units = ["B", "KB", "MB", "GB", "TB"];
        let value = Number(bytes), unit = 0;
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024;
            unit++;
        }
        return value.toFixed(unit === 0 ? 0 : 1) + " " + units[unit];
    }

    property var rows: []
    property int matched: 0
    property var summary: ({})
    property bool frozen: false
    property bool started: false
    property string query: ""
    property string owner: "mine"
    property string stateFilter: "all"
    property string sortKey: "cpu"
    property bool tree: false
    property real interval: 2
    readonly property var control: ({query: query, owner: owner, state: stateFilter, sort: sortKey, tree: tree, interval: interval})
    readonly property var pressure: summary.pressure ?? ({})

    function pct(value: var): string {
        return value === null || value === undefined ? "—" : Number(value).toFixed(1) + "%";
    }

    function send(): void {
        if (started)
            feed.write(JSON.stringify(control) + "\n");
    }

    onControlChanged: send()

    title: "Procesos"

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: (root.frozen ? "Congelado" : "En vivo") + " · " + (root.summary.count ?? 0) + " procesos, " + (root.summary.running ?? 0) + " ejecutándose"
        }

        InfoRow {
            first: true
            icon: "memory"
            label: "Procesador"
            subtext: (root.summary.cores ?? 1) + " núcleos lógicos · carga " + (root.summary.load ? Number(root.summary.load[0]).toFixed(2) : "—")
            value: root.pct(root.summary.cpu)
        }

        InfoRow {
            icon: "developer_board"
            label: "Memoria"
            subtext: "de " + root.size(root.summary.total_memory)
            value: root.size(root.summary.memory)
        }

        InfoRow {
            icon: "swap_horiz"
            label: "Intercambio"
            subtext: root.summary.total_swap ? "de " + root.size(root.summary.total_swap) : "Sin intercambio configurado"
            value: root.size(root.summary.swap)
        }

        InfoRow {
            last: true
            icon: "speed"
            label: "Presión del sistema"
            subtext: "CPU · RAM · E/S"
            value: root.pct(root.pressure.cpu) + " · " + root.pct(root.pressure.memory) + " · " + root.pct(root.pressure.io)
        }

        SectionHeader {
            text: "Filtros"
        }

        TextFieldRow {
            first: true
            label: "Buscar"
            subtext: "Nombre, pid:, user:, state:, cpu>5, mem>500m"
            value: root.query
            onValueEdited: value => root.query = value
        }

        OptionRow {
            label: "Propietario"
            options: [{value: "mine", label: "Mis procesos"}, {value: "all", label: "Todos los usuarios"}]
            current: root.owner
            onPicked: value => root.owner = value
        }

        OptionRow {
            label: "Estado"
            options: [{value: "all", label: "Todos"}, {value: "running", label: "Ejecutando"}, {value: "paused", label: "Pausados"}, {value: "busy", label: "Consumo alto"}]
            current: root.stateFilter
            onPicked: value => root.stateFilter = value
        }

        OptionRow {
            label: "Ordenar por"
            options: [{value: "cpu", label: "CPU"}, {value: "memory", label: "Memoria"}, {value: "pid", label: "PID"}, {value: "name", label: "Nombre"}]
            current: root.sortKey
            onPicked: value => root.sortKey = value
        }

        OptionRow {
            label: "Actualizar"
            options: [{value: 1, label: "Cada 1 s"}, {value: 2, label: "Cada 2 s"}, {value: 5, label: "Cada 5 s"}]
            current: root.interval
            onPicked: value => root.interval = value
        }

        ToggleRow {
            text: "Vista de árbol"
            checked: root.tree
            onToggled: root.tree = checked
        }

        ToggleRow {
            last: true
            text: "Congelar lista"
            subtext: "Mantiene los valores mientras eliges un proceso"
            checked: root.frozen
            onToggled: root.frozen = checked
        }

        SectionHeader {
            text: root.matched + " resultados" + (root.matched > root.rows.length ? " · mostrando " + root.rows.length : "")
        }

        Repeater {
            model: root.rows

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: index === root.rows.length - 1
                icon: modelData.state === "T" || modelData.state === "t" ? "pause_circle" : "apps"
                text: "    ".repeat(Math.min(modelData.depth ?? 0, 8)) + modelData.name
                subtext: "PID " + modelData.pid + " · CPU " + (modelData.sampled ? modelData.cpu.toFixed(1) + "%" : "—") + " · " + root.size(modelData.memory) + " · " + modelData.user
                trailingIcon: "chevron_right"
                onClicked: {
                    root.nState.selectedProcess = modelData;
                    root.nState.openSubPage(1);
                }
            }
        }

        Process {
            id: feed

            command: DesktopBridge.streamCommand("processes.stream", {interval: root.interval})
            running: root.visible
            stdinEnabled: true
            onStarted: {
                root.started = true;
                root.send();
            }
            onRunningChanged: if (!running)
                root.started = false
            stdout: SplitParser {
                onRead: line => {
                    if (root.frozen)
                        return;
                    try {
                        const reply = JSON.parse(line);
                        if (!reply.ok || !reply.data.rows)
                            return;
                        root.rows = reply.data.rows.slice(0, 120);
                        root.matched = reply.data.matched;
                        root.summary = reply.data.summary;
                    } catch (error) {
                    }
                }
            }
        }
    }
}
