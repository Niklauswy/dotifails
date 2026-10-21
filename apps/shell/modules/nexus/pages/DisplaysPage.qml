pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

// Monitor layout with a live trial that reverts unless confirmed.
PageBase {
    id: root

    readonly property var rotations: [
        {value: "normal", label: "Normal"},
        {value: "left", label: "90° izquierda"},
        {value: "right", label: "90° derecha"},
        {value: "inverted", label: "180°"}
    ]
    property var plan: []
    property var boxes: []
    property var modes: ({})
    property var scales: [1]
    property var order: []
    property string selected: ""
    property string status: ""
    property bool failed: false
    property string trialFolder: ""
    property int countdown: 0
    readonly property bool trialing: trialFolder.length > 0
    readonly property var current: plan.find(p => p.name === selected) ?? null
    readonly property var modeList: current ? (modes[current.name] ?? []) : []
    readonly property var rateList: (modeList.find(m => m.name === current?.mode)?.rates ?? [])

    function report(message: string, error: bool): void {
        status = message;
        failed = error;
    }

    function load(): void {
        DesktopBridge.call("displays.state", {}, data => {
            root.adopt(data);
            root.modes = data.modes;
            root.scales = data.scales;
            if (!root.current)
                root.selected = data.plan.length ? data.plan[0].name : "";
        }, message => report(message, true));
    }

    function adopt(data: var): void {
        plan = data.plan;
        boxes = data.boxes;
        order = data.order;
    }

    // Edit the selected output; the backend keeps the layout edge to edge.
    function edit(patch: var): void {
        if (!current)
            return;
        const draft = plan.map(p => p.name === current.name ? Object.assign({}, p, patch) : Object.assign({}, p));
        if (patch.primary)
            draft.forEach(p => p.primary = p.name === current.name);
        if (patch.enabled === false && !draft.some(p => p.enabled)) {
            report("Deja al menos una pantalla encendida.", true);
            return;
        }
        if (patch.mode) {
            const rates = (modeList.find(m => m.name === patch.mode)?.rates ?? []);
            const entry = draft.find(p => p.name === current.name);
            if (!rates.includes(entry.rate))
                entry.rate = rates[0] ?? entry.rate;
        }
        DesktopBridge.call("displays.normalize", {plan: draft}, data => {
            adopt(data);
            report("Cambio preparado. Pulsa «Probar distribución» para verlo.", false);
        }, message => report(message, true));
    }

    function place(direction: string): void {
        if (!current)
            return;
        DesktopBridge.call("displays.normalize", {plan: plan, move: {name: current.name, direction: direction}}, data => {
            adopt(data);
            report("Orden preparado. Pulsa «Probar distribución» para verlo.", false);
        }, message => report(message, true));
    }

    function tryPlan(): void {
        report("Aplicando la distribución…", false);
        DesktopBridge.call("displays.try", {plan: plan}, data => {
            trialFolder = data.folder;
            countdown = 15;
            report("", false);
        }, message => {
            report(message, true);
            load();
        });
    }

    function settle(keep: bool): void {
        const folder = trialFolder;
        trialFolder = "";
        countdownTimer.stop();
        DesktopBridge.call("displays.settle", {folder: folder, accept: keep}, () => {
            report(keep ? "Distribución confirmada y guardada para esta combinación de pantallas." : "Se recuperó la distribución anterior.", false);
            load();
        }, message => {
            report(message, true);
            load();
        });
    }

    title: "Pantallas"
    isSubPage: true
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: root.trialing ? "¿Conservar esta distribución? · " + root.countdown + " s" : "Distribución"
        }

        // Miniature of the arrangement; drag a screen to place it beside, above or below another.
        StyledRect {
            id: canvas

            readonly property real extent: Math.max(1, ...root.boxes.map(b => b.x + b.w))
            readonly property real extentY: Math.max(1, ...root.boxes.map(b => b.y + b.h))
            readonly property real factor: Math.min((width - Tokens.padding.large * 2) / extent, (height - Tokens.padding.large * 2) / extentY)

            Layout.fillWidth: true
            implicitHeight: Tokens.sizes.nexus.minHeight / 3
            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainer

            Repeater {
                model: root.boxes

                StyledRect {
                    id: box

                    required property var modelData
                    readonly property bool isSelected: modelData.name === root.selected

                    x: Tokens.padding.large + modelData.x * canvas.factor
                    y: Tokens.padding.large + modelData.y * canvas.factor
                    width: modelData.w * canvas.factor
                    height: modelData.h * canvas.factor
                    radius: Tokens.rounding.small
                    opacity: modelData.enabled ? 1 : 0.4
                    color: isSelected ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh
                    border.width: isSelected ? 2 : 1
                    border.color: isSelected ? Colours.palette.m3primary : Colours.palette.m3outlineVariant

                    StyledText {
                        anchors.centerIn: parent
                        text: box.modelData.name + (root.plan.find(p => p.name === box.modelData.name)?.primary ? " ★" : "")
                        color: box.isSelected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                        font: Tokens.font.label.medium
                    }

                    MouseArea {
                        id: drag

                        property real startX
                        property real startY

                        anchors.fill: parent
                        enabled: !root.trialing
                        onPressed: mouse => {
                            root.selected = box.modelData.name;
                            startX = mouse.x;
                            startY = mouse.y;
                        }
                        onReleased: mouse => {
                            const dx = mouse.x - startX, dy = mouse.y - startY;
                            if (Math.max(Math.abs(dx), Math.abs(dy)) < 24)
                                return;
                            if (Math.abs(dx) > Math.abs(dy))
                                root.place(dx < 0 ? "left" : "right");
                            else
                                root.place(dy < 0 ? "above" : "below");
                        }
                    }
                }
            }
        }

        StyledText {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.topMargin: Tokens.spacing.small
            visible: root.order.length > 0
            text: "Orden: " + root.order.join("  →  ")
            color: Colours.palette.m3outline
            font: Tokens.font.label.small
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small
            visible: !root.trialing

            Repeater {
                model: [
                    {label: "Izquierda", direction: "left"},
                    {label: "Derecha", direction: "right"},
                    {label: "Arriba", direction: "above"},
                    {label: "Abajo", direction: "below"}
                ]

                ActionButton {
                    required property var modelData

                    type: TextButton.Tonal
                    text: modelData.label
                    disabled: !root.current
                    onClicked: root.place(modelData.direction)
                }
            }
        }

        SectionHeader {
            text: "Pantalla seleccionada"
        }

        OptionRow {
            first: true
            label: "Pantalla"
            options: root.plan.map(p => ({value: p.name, label: p.name}))
            current: root.selected
            onPicked: value => root.selected = value
        }

        ToggleRow {
            visible: root.current
            text: "Encendida"
            checked: root.current?.enabled ?? false
            disabled: root.trialing
            onToggled: root.edit({enabled: checked})
        }

        ToggleRow {
            visible: root.current
            text: "Principal"
            subtext: "Recibe el foco al iniciar la sesión"
            checked: root.current?.primary ?? false
            disabled: root.trialing || !(root.current?.enabled ?? false)
            onToggled: root.edit({primary: checked})
        }

        OptionRow {
            visible: root.current
            label: "Resolución"
            options: root.modeList.map(m => ({value: m.name, label: m.name.replace("x", "×")}))
            current: root.current?.mode
            onPicked: value => root.edit({mode: value})
        }

        OptionRow {
            visible: root.current
            label: "Frecuencia"
            options: root.rateList.map(r => ({value: r, label: r + " Hz"}))
            current: root.current?.rate
            onPicked: value => root.edit({rate: value})
        }

        OptionRow {
            visible: root.current
            label: "Escala"
            options: root.scales.map(s => ({value: s, label: s + "×"}))
            current: root.current?.scale ?? 1
            onPicked: value => root.edit({scale: value})
        }

        OptionRow {
            visible: root.current
            last: true
            label: "Rotación"
            options: root.rotations
            current: root.current?.rotation
            onPicked: value => root.edit({rotation: value})
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                visible: !root.trialing
                text: "Probar distribución"
                disabled: root.plan.length === 0
                onClicked: root.tryPlan()
            }

            ActionButton {
                visible: !root.trialing
                type: TextButton.Tonal
                text: "Descartar cambios"
                onClicked: {
                    root.report("Cambios de pantallas descartados.", false);
                    root.load();
                }
            }

            ActionButton {
                visible: root.trialing
                text: "Conservar"
                onClicked: root.settle(true)
            }

            ActionButton {
                visible: root.trialing
                type: TextButton.Tonal
                text: "Volver"
                onClicked: root.settle(false)
            }
        }

        Timer {
            id: countdownTimer

            interval: 1000
            repeat: true
            running: root.trialing
            onTriggered: {
                root.countdown -= 1;
                if (root.countdown <= 0)
                    root.settle(false);
            }
        }
    }
}
