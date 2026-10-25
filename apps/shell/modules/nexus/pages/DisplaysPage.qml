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
        {value: "left", label: "90° left"},
        {value: "right", label: "90° right"},
        {value: "inverted", label: "180°"}
    ]
    property bool busy: false
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
    readonly property var switchedOff: plan.filter(p => !p.enabled)
    readonly property var modeList: current ? (modes[current.name] ?? []) : []
    readonly property var rateList: (modeList.find(m => m.name === current?.mode)?.rates ?? [])

    function report(message: string, error: bool): void {
        status = message;
        failed = error;
    }

    function load(): void {
        DisplayBridge.call("displays.state", {}, data => {
            root.adopt(data);
            root.modes = data.modes;
            root.scales = data.scales;
            if (!root.current)
                root.selected = data.plan.length ? data.plan[0].name : "";
        }, message => { busy = false; report(message, true); });
    }

    function adopt(data: var): void {
        plan = data.plan;
        boxes = data.boxes;
        order = data.order;
    }

    // Edit the selected output; the backend keeps the layout edge to edge.
    function edit(patch: var): void {
        if (!current || trialing || busy)
            return;
        const draft = plan.map(p => p.name === current.name ? Object.assign({}, p, patch) : Object.assign({}, p));
        if (patch.primary)
            draft.forEach(p => p.primary = p.name === current.name);
        if (patch.enabled === false && !draft.some(p => p.enabled)) {
            report("Keep at least one display enabled.", true);
            return;
        }
        if (patch.mode) {
            const rates = (modeList.find(m => m.name === patch.mode)?.rates ?? []);
            const entry = draft.find(p => p.name === current.name);
            if (!rates.includes(entry.rate))
                entry.rate = rates[0] ?? entry.rate;
        }
        busy = true;
        DisplayBridge.call("displays.normalize", {plan: draft}, data => {
            busy = false;
            adopt(data);
            report("Changes ready. Test the layout to preview them.", false);
        }, message => { busy = false; report(message, true); });
    }

    function place(direction: string): void {
        if (!current || trialing || busy)
            return;
        busy = true;
        DisplayBridge.call("displays.normalize", {plan: plan, move: {name: current.name, direction: direction}}, data => {
            busy = false;
            adopt(data);
            report("Arrangement ready. Test the layout to preview it.", false);
        }, message => { busy = false; report(message, true); });
    }

    function tryPlan(): void {
        if (busy || trialing) return;
        busy = true;
        report("Applying display layout…", false);
        DisplayBridge.call("displays.try", {plan: plan}, data => {
            busy = false;
            trialFolder = data.folder;
            countdown = 15;
            report("", false);
        }, message => {
            busy = false;
            report(message, true);
            load();
        });
    }

    function settle(keep: bool): void {
        const folder = trialFolder;
        busy = true;
        trialFolder = "";
        countdownTimer.stop();
        DisplayBridge.call("displays.settle", {folder: folder, accept: keep}, () => {
            busy = false;
            report(keep ? "Display layout saved for these connected displays." : "Previous display layout restored.", false);
            load();
        }, message => {
            busy = false;
            report(message, true);
            load();
        });
    }

    title: "Displays"
    Component.onCompleted: load()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        SectionHeader {
            first: true
            text: root.trialing ? "Keep this layout? · " + root.countdown + " s" : "Arrangement"
        }

        StyledText {
            Layout.fillWidth: true
            Layout.bottomMargin: Tokens.spacing.small
            text: "Select a display to edit it. Drag to snap it beside, above or below its neighbours."
            wrapMode: Text.Wrap
            font: Tokens.font.body.small
            color: Colours.palette.m3onSurfaceVariant
        }

        // Miniature of the arrangement; drag a screen to place it beside, above or below another.
        StyledRect {
            id: canvas

            readonly property real extent: Math.max(1, ...root.boxes.filter(b => b.enabled).map(b => b.x + b.w))
            readonly property real extentY: Math.max(1, ...root.boxes.filter(b => b.enabled).map(b => b.y + b.h))
            readonly property real factor: Math.min((width - Tokens.padding.large * 2) / extent, (height - Tokens.padding.large * 2) / extentY)

            Layout.fillWidth: true
            implicitHeight: Tokens.sizes.nexus.minHeight / 3
            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainer

            Repeater {
                model: root.boxes.filter(b => b.enabled)

                StyledRect {
                    id: box

                    required property var modelData
                    readonly property bool isSelected: modelData.name === root.selected

                    x: (canvas.width - canvas.extent * canvas.factor) / 2 + modelData.x * canvas.factor
                    y: (canvas.height - canvas.extentY * canvas.factor) / 2 + modelData.y * canvas.factor
                    width: modelData.w * (canvas?.factor ?? 0)
                    height: modelData.h * (canvas?.factor ?? 0)
                    radius: Tokens.rounding.small
                    opacity: modelData.enabled ? 1 : 0.4
                    color: isSelected ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh
                    border.width: isSelected || DisplayIdentify.showing ? 2 : 1
                    border.color: DisplayIdentify.showing ? Colours.palette.m3tertiary : isSelected ? Colours.palette.m3primary : Colours.palette.m3outlineVariant

                    transform: Translate { x: drag.offsetX; y: drag.offsetY }
                    z: drag.pressed ? 1 : 0

                    StyledText {
                        anchors.centerIn: parent
                        text: (root.order.indexOf(box.modelData.name) + 1) + " · " + box.modelData.name + (root.plan.find(p => p.name === box.modelData.name)?.primary ? " ★" : "")
                        color: box.isSelected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                        font: Tokens.font.label.medium
                    }

                    MouseArea {
                        id: drag

                        property real startX
                        property real startY
                        property real offsetX: 0
                        property real offsetY: 0
                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        preventStealing: true

                        anchors.fill: parent
                        enabled: !root.trialing && !root.busy
                        onPressed: mouse => {
                            root.selected = box.modelData.name;
                            startX = mouse.x;
                            startY = mouse.y;
                        }
                        onPositionChanged: mouse => {
                            if (pressed) {
                                offsetX += mouse.x - startX;
                                offsetY += mouse.y - startY;
                            }
                        }
                        onCanceled: { offsetX = 0; offsetY = 0; }
                        onReleased: mouse => {
                            const dx = offsetX, dy = offsetY;
                            offsetX = 0; offsetY = 0;
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

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            StyledText {
                Layout.fillWidth: true
                visible: root.order.length > 0
                text: "Display order: " + root.order.join("  →  ")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.label.small
                elide: Text.ElideRight
            }

            // Puts the number and name of each display on that display for a few seconds.
            ActionButton {
                type: TextButton.Tonal
                text: "Identify"
                onClicked: DisplayIdentify.show()
            }
        }

        // Displays that are off do not appear in the miniature; they are here, one click from on.
        Flow {
            Layout.fillWidth: true
            Layout.topMargin: Tokens.spacing.small
            Layout.leftMargin: Tokens.padding.small
            spacing: Tokens.spacing.small
            visible: root.switchedOff.length > 0 && !root.trialing

            StyledText {
                height: 32
                verticalAlignment: Text.AlignVCenter
                text: "Turned off"
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.label.small
            }

            Repeater {
                model: root.switchedOff

                StyledRect {
                    id: off

                    required property var modelData

                    implicitWidth: offRow.implicitWidth + Tokens.padding.large * 2
                    implicitHeight: 32
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3surfaceContainerHigh
                    opacity: root.busy ? 0.5 : 1

                    StateLayer {
                        radius: off.radius
                        disabled: root.busy
                        onClicked: {
                            root.selected = off.modelData.name;
                            root.edit({enabled: true});
                        }
                    }

                    Row {
                        id: offRow

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.small

                        MaterialIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "power_settings_new"
                            color: Colours.palette.m3primary
                            fontStyle: Tokens.font.icon.small
                        }
                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: off.modelData.name + " · turn on"
                            font: Tokens.font.label.medium
                            color: Colours.palette.m3onSurface
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small
            visible: !root.trialing
            enabled: !root.busy

            Repeater {
                model: [
                    {label: "Left", direction: "left"},
                    {label: "Right", direction: "right"},
                    {label: "Above", direction: "above"},
                    {label: "Below", direction: "below"}
                ]

                ActionButton {
                    required property var modelData

                    type: TextButton.Tonal
                    text: modelData.label
                    disabled: !root.current || root.busy
                    onClicked: root.place(modelData.direction)
                }
            }
        }

        SectionHeader {
            text: "Display settings"
        }

        OptionRow {
            first: true
            label: "Display"
            options: root.plan.map(p => ({value: p.name, label: p.enabled ? p.name : p.name + " · off"}))
            current: root.selected
            onPicked: value => root.selected = value
        }

        ToggleRow {
            visible: root.current
            text: "Enabled"
            checked: root.current?.enabled ?? false
            disabled: root.trialing || root.busy
            onToggled: root.edit({enabled: checked})
        }

        ToggleRow {
            visible: root.current
            text: "Primary display"
            subtext: "Receives focus at startup and hosts widgets in primary-only mode"
            checked: root.current?.primary ?? false
            disabled: root.trialing || root.busy || !(root.current?.enabled ?? false)
            onToggled: root.edit({primary: checked})
        }

        OptionRow {
            label: "Widgets on"
            options: [{value: "all", label: "All displays"}, {value: "primary", label: "Primary display"}]
            current: Screens.widgetsOnlyPrimary ? "primary" : "all"
            enabled: !root.trialing && !root.busy
            onPicked: value => {
                root.busy = true;
                DisplayBridge.call("displays.widgets", {mode: value}, data => {
                    root.busy = false;
                    root.report("Widget placement saved. Wallpapers and capture remain on all displays.", false);
                }, message => { root.busy = false; root.report(message, true); });
            }
        }

        OptionRow {
            visible: root.current
            enabled: !root.trialing && !root.busy
            label: "Resolution"
            options: root.modeList.map(m => ({value: m.name, label: m.name.replace("x", "×")}))
            current: root.current?.mode
            onPicked: value => root.edit({mode: value})
        }

        OptionRow {
            visible: root.current
            enabled: !root.trialing && !root.busy
            label: "Refresh rate"
            options: root.rateList.map(r => ({value: r, label: r + " Hz"}))
            current: root.current?.rate
            onPicked: value => root.edit({rate: value})
        }

        OptionRow {
            visible: root.current
            enabled: !root.trialing && !root.busy
            label: "Scale"
            options: root.scales.map(s => ({value: s, label: s + "×"}))
            current: root.current?.scale ?? 1
            onPicked: value => root.edit({scale: value})
        }

        OptionRow {
            visible: root.current
            enabled: !root.trialing && !root.busy
            last: true
            label: "Rotation"
            options: root.rotations
            current: root.current?.rotation
            onPicked: value => root.edit({rotation: value})
        }

        StatusLine {
            text: root.trialing ? "Keep these settings within " + root.countdown + " seconds, or the previous layout will be restored." : root.status
            error: root.failed
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.large
            spacing: Tokens.spacing.small

            ActionButton {
                visible: !root.trialing
                text: "Test layout"
                disabled: root.plan.length === 0 || root.busy
                onClicked: root.tryPlan()
            }

            ActionButton {
                visible: !root.trialing
                type: TextButton.Tonal
                disabled: root.busy
                text: "Discard changes"
                onClicked: {
                    root.report("Display changes discarded.", false);
                    root.load();
                }
            }

            ActionButton {
                visible: root.trialing
                disabled: root.busy
                text: "Keep changes"
                onClicked: root.settle(true)
            }

            ActionButton {
                visible: root.trialing
                type: TextButton.Tonal
                disabled: root.busy
                text: "Revert"
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
