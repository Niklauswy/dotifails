pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Details and actions for one process, identified by PID and start time.
PageBase {
    id: root

    readonly property var row: nState.selectedProcess
    property var detail: null
    property string status: ""
    property bool failed: false
    property string armed: ""

    function fail(message: string): void {
        status = message;
        failed = true;
    }

    function refresh(): void {
        DesktopBridge.call("processes.details", {row: {pid: row.pid, start: row.start}}, data => root.detail = data, fail);
    }

    function act(action: string): void {
        const destructive = action === "terminate" || action === "kill";
        if (destructive && armed !== action) {
            armed = action;
            status = "Pulsa de nuevo para " + (action === "kill" ? "forzar el cierre" : "terminar") + " «" + row.name + "».";
            failed = false;
            return;
        }
        armed = "";
        DesktopBridge.call("processes.act", {row: {pid: row.pid, start: row.start}, action: action}, () => {
            root.status = {terminate: "Se pidió terminar el proceso.", kill: "Proceso forzado a cerrar.", pause: "Proceso pausado.", resume: "Proceso reanudado."}[action];
            root.failed = false;
        }, fail);
    }

    title: row ? row.name + " · " + row.pid : "Proceso"
    isSubPage: true
    Component.onCompleted: if (row)
        refresh()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        InfoRow {
            first: true
            label: "Usuario"
            value: root.row?.user ?? ""
        }

        InfoRow {
            label: "Estado"
            value: ({R: "Ejecutando", S: "En espera", D: "Espera de E/S", T: "Pausado", t: "Depuración", Z: "Zombi", I: "Inactivo", X: "Finalizado"})[root.row?.state] ?? root.row?.state ?? ""
        }

        InfoRow {
            label: "Memoria"
            value: (Number(root.row?.memory ?? 0) / 1048576).toFixed(1) + " MB"
        }

        InfoRow {
            label: "Hilos"
            value: String(root.detail?.thread_count ?? root.row?.threads ?? "")
        }

        InfoRow {
            label: "Archivos abiertos"
            value: String(root.detail?.file_count ?? "—")
        }

        InfoRow {
            last: true
            label: "Proceso padre"
            value: String(root.row?.ppid ?? "")
        }

        SectionHeader {
            text: "Ejecutable y comando"
        }

        InfoRow {
            first: true
            label: "Ejecutable"
            subtext: root.detail?.exe || "—"
        }

        InfoRow {
            label: "Directorio"
            subtext: root.detail?.cwd || "—"
        }

        InfoRow {
            last: true
            label: "Comando"
            subtext: root.detail?.command || "—"
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                text: root.armed === "terminate" ? "Confirmar" : "Terminar"
                disabled: !(root.row?.actionable ?? false)
                onClicked: root.act("terminate")
            }

            ActionButton {
                type: TextButton.Tonal
                text: root.armed === "kill" ? "Confirmar" : "Forzar cierre"
                disabled: !(root.row?.actionable ?? false)
                onClicked: root.act("kill")
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Pausar"
                disabled: !(root.row?.actionable ?? false)
                onClicked: root.act("pause")
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Reanudar"
                disabled: !(root.row?.actionable ?? false)
                onClicked: root.act("resume")
            }
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            ActionButton {
                type: TextButton.Tonal
                text: "Actualizar"
                onClicked: root.refresh()
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Copiar comando"
                disabled: !root.detail
                onClicked: Quickshell.clipboardText = root.detail.command
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Copiar PID"
                onClicked: Quickshell.clipboardText = String(root.row.pid)
            }
        }

        SectionHeader {
            visible: root.detail && root.detail.threads.length > 0
            text: "Hilos (" + (root.detail?.thread_count ?? 0) + ")"
        }

        Repeater {
            model: (root.detail?.threads ?? []).slice(0, 30)

            InfoRow {
                required property var modelData
                required property int index

                first: index === 0
                last: index === 29
                label: modelData.name
                subtext: "TID " + modelData.tid + " · " + modelData.state + " · espera " + modelData.wait
                value: Number(modelData.cpu_time).toFixed(2) + " s"
            }
        }
    }
}
