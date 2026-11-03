// Servicios (systemd --user): a filterable list grouped as failed, active, timers and stopped; the chosen unit with
// its explained failure and Reintentar, start/stop/restart, «Iniciar con la sesión», its resources, the countdown
// of a timer and the live journal whose new lines slide in.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: page

    property bool shown
    property string filter: "all"
    property string query
    property int selected: 0
    readonly property var groups: {
        const q = query.toLowerCase();
        const list = procs.services.filter(s => (filter === "all" || (filter === "failed" ? s.state === "failed" : s.kind === "timer"))
                                              && (s.unit + " " + s.description).toLowerCase().indexOf(q) >= 0);
        return [["Con fallos", list.filter(s => s.state === "failed")],
                ["Activos", list.filter(s => s.state === "active" && s.kind === "service")],
                ["Temporizadores", list.filter(s => s.kind === "timer" && s.state !== "failed")],
                ["Parados", list.filter(s => s.state === "inactive" && s.kind === "service")]].filter(g => g[1].length);
    }
    readonly property var rows: {
        const out = [];
        let i = 0;
        for (const g of groups) {
            out.push({header: g[0] + " · " + g[1].length});
            for (const s of g[1])
                out.push(Object.assign({index: i++}, s));
        }
        return out;
    }
    readonly property var units: rows.filter(r => !r.header)
    readonly property var current: units[Math.min(selected, units.length - 1)] ?? null
    property real now: Date.now()

    signal returnFocus

    function handleKey(event) {
        if (event.key === Qt.Key_Down || event.text === "j") {
            selected = Math.min(units.length - 1, selected + 1);
            return true;
        }
        if (event.key === Qt.Key_Up || event.text === "k") {
            selected = Math.max(0, selected - 1);
            return true;
        }
        if (!current)
            return false;
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            procs.serviceAction(current.unit, current.kind === "timer" ? "run" : current.state === "active" ? "stop" : "start");
            return true;
        }
        if (event.text === "r") {
            procs.serviceAction(current.unit, "restart");
            return true;
        }
        if (event.text === "e") {
            procs.serviceAction(current.unit, current.enabled ? "disable" : "enable");
            return true;
        }
        if (event.text === "f") {
            search.forceFocus();
            return true;
        }
        return false;
    }
    function countdown(us) {
        const s = Math.max(0, us / 1000 - now) / 1000;
        if (s >= 86400)
            return Math.floor(s / 86400) + " d " + Math.floor(s % 86400 / 3600) + " h";
        return Math.floor(s / 3600) + " h " + String(Math.floor(s % 3600 / 60)).padStart(2, "0") + " min " + String(Math.floor(s % 60)).padStart(2, "0") + " s";
    }
    function stateColour(s) {
        return s.state === "active" ? Theme.m3success : s.state === "failed" ? Theme.m3error : Theme.m3outline;
    }

    onCurrentChanged: if (current) procs.watchService(current.unit)
    onShownChanged: if (shown && current) procs.watchService(current.unit)

    visible: opacity > 0
    opacity: shown ? 1 : 0

    Behavior on opacity {
        Anim {
            kind: "defaultEffects"
        }
    }

    Timer {
        interval: Theme.duration("extraLarge")
        running: page.shown
        repeat: true
        onTriggered: page.now = Date.now()
    }

    EmptyState {
        objectName: "servicesEmpty"
        anchors.centerIn: parent
        visible: !procs.servicesAvailable
        icon: "settings_suggest"
        title: "Sin servicios de usuario"
        message: "systemd --user no está disponible en esta sesión"
    }

    Rectangle {
        id: listCard

        visible: procs.servicesAvailable
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: Theme.spacing.medium ?? 0
        width: Math.min(Metrics.drawerWidth + Metrics.listItemTwoLine * 1.4, parent.width * 0.4)
        radius: Theme.rounding.extraLarge ?? 0
        color: Theme.m3surfaceContainerLow

        Column {
            id: listHead

            x: Theme.padding.medium ?? 0
            y: Theme.padding.medium ?? 0
            width: parent.width - x * 2
            spacing: Theme.spacing.small ?? 0

            Item {
                width: parent.width
                height: search.height

                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Escape || event.key === Qt.Key_Down || event.key === Qt.Key_Return) {
                        page.returnFocus();
                        event.accepted = true;
                    }
                }

                SearchBar {
                    id: search

                    width: parent.width
                    placeholder: "Filtrar servicios"
                    shortcut: ""
                    onTextChanged: {
                        page.query = text;
                        page.selected = 0;
                    }
                }
            }

            SegmentedButtons {
                width: parent.width
                model: [{value: "all", text: "Todos"}, {value: "failed", text: "Fallos"}, {value: "timer", text: "Programados"}]
                current: page.filter
                onActivated: value => {
                    page.filter = value;
                    page.selected = 0;
                }
            }
        }

        ListView {
            id: unitList

            anchors.top: listHead.bottom
            anchors.topMargin: Theme.spacing.small ?? 0
            anchors.bottom: parent.bottom
            width: parent.width
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: page.rows
            delegate: Item {
                id: unitRow

                required property var modelData
                readonly property bool isHeader: !!modelData.header
                readonly property bool on: !isHeader && page.current && page.current.unit === modelData.unit

                width: unitList.width
                height: isHeader ? Metrics.chipHeight : Metrics.listItemTwoLine * 0.86

                Label {
                    visible: unitRow.isHeader
                    anchors.bottom: parent.bottom
                    x: Theme.padding.large ?? 0
                    text: (unitRow.modelData.header ?? "").toUpperCase()
                    role: "label.small"
                    color: Theme.m3onSurfaceVariant
                }

                Rectangle {
                    visible: !unitRow.isHeader
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing.small ?? 0
                    anchors.rightMargin: Theme.spacing.small ?? 0
                    radius: Theme.rounding.large ?? 0
                    color: unitRow.on ? Theme.m3secondaryContainer : Qt.alpha(Theme.m3onSurface, rowHover.hovered ? Metrics.stateHover : 0)

                    Behavior on color {
                        ColorAnimation {
                            duration: Motion.ms("fastEffects")
                        }
                    }

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        x: Theme.padding.medium ?? 0
                        width: parent.width - x * 2
                        spacing: Theme.spacing.medium ?? 0

                        Item {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Theme.spacing.medium ?? 0
                            height: width

                            Rectangle {
                                anchors.centerIn: parent
                                width: parent.width
                                height: width
                                radius: width / 2
                                color: unitRow.isHeader ? Theme.m3outline : page.stateColour(unitRow.modelData)
                            }

                            Rectangle {
                                id: ring

                                anchors.centerIn: parent
                                width: parent.width
                                height: width
                                radius: width / 2
                                color: Qt.alpha(Theme.m3success, 0)
                                border.width: Metrics.outlineWidth * 2
                                border.color: Theme.m3success
                                visible: !unitRow.isHeader && unitRow.modelData.state === "active" && !Motion.reduced
                                opacity: 0

                                SequentialAnimation {
                                    running: ring.visible && page.shown
                                    loops: Animation.Infinite
                                    ParallelAnimation {
                                        NumberAnimation { target: ring; property: "scale"; from: 0.6; to: 2.2; duration: Theme.duration("extraLarge") * 2; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bezier("emphasizedDecel") }
                                        NumberAnimation { target: ring; property: "opacity"; from: 0.6; to: 0; duration: Theme.duration("extraLarge") * 2; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bezier("emphasizedDecel") }
                                    }
                                }
                            }
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - x - side.width - parent.spacing

                            Label {
                                width: parent.width
                                text: (unitRow.modelData.unit ?? "").replace(/\.(service|timer)$/, "")
                                role: "title.small"
                                elide: Text.ElideRight
                                color: unitRow.on ? Theme.m3onSecondaryContainer : Theme.m3onSurface
                            }

                            Label {
                                width: parent.width
                                text: unitRow.modelData.description ?? ""
                                role: "label.small"
                                elide: Text.ElideRight
                                color: unitRow.on ? Theme.m3onSecondaryContainer : Theme.m3onSurfaceVariant
                            }
                        }

                        Label {
                            id: side

                            anchors.verticalCenter: parent.verticalCenter
                            text: unitRow.isHeader ? "" : unitRow.modelData.kind === "timer" && unitRow.modelData.next_us ? page.countdown(unitRow.modelData.next_us).split(" ").slice(0, 4).join(" ")
                                : unitRow.modelData.memory ? Fmt.mem(unitRow.modelData.memory) : ""
                            role: "label.small"
                            font.family: Theme.font.family?.mono ?? ""
                            color: Theme.m3onSurfaceVariant
                        }
                    }

                    HoverHandler {
                        id: rowHover
                    }

                    TapHandler {
                        onTapped: page.selected = unitRow.modelData.index
                    }
                }
            }
        }

        ScrollIndicator {
            anchors.right: parent.right
            anchors.top: unitList.top
            anchors.bottom: unitList.bottom
            flickable: unitList
        }
    }

    Rectangle {
        id: detail

        visible: procs.servicesAvailable
        anchors.left: listCard.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: Theme.spacing.medium ?? 0
        radius: Theme.rounding.extraLarge ?? 0
        color: Theme.m3surfaceContainerLow

        readonly property var s: page.current ?? ({})
        readonly property bool failed: s.state === "failed"
        readonly property bool active: s.state === "active"
        readonly property bool timer: s.kind === "timer"

        Column {
            id: detailHead

            x: Theme.padding.large ?? 0
            y: Theme.padding.large ?? 0
            width: parent.width - x * 2
            spacing: Theme.spacing.medium ?? 0

            Row {
                spacing: Theme.spacing.medium ?? 0

                ShapeEmblem {
                    shape: detail.failed ? "burst" : detail.timer ? "clover" : "cookie"
                    color: detail.failed ? Theme.m3errorContainer : detail.active ? Theme.m3successContainer : Theme.m3surfaceContainerHighest
                    icon: detail.failed ? "error" : detail.timer ? "schedule" : "settings_suggest"
                    iconColor: detail.failed ? Theme.m3onErrorContainer : detail.active ? Theme.m3onSuccessContainer : Theme.m3onSurface
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter

                    Label {
                        text: detail.s.unit ?? ""
                        role: "headline.small"
                        font.family: Theme.font.family?.mono ?? ""
                    }

                    Label {
                        text: (detail.s.description ?? "") + " · " + (detail.failed ? "falló" : detail.active ? (detail.timer ? "programado" : "activo") : "parado")
                        role: "body.medium"
                        color: Theme.m3onSurfaceVariant
                    }
                }
            }

            Rectangle {
                visible: detail.failed
                width: parent.width
                height: Metrics.listItemTwoLine
                radius: Theme.rounding.large ?? 0
                color: Theme.m3errorContainer

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Theme.padding.large ?? 0
                    width: parent.width - x * 2
                    spacing: Theme.spacing.medium ?? 0

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: "error"
                        color: Theme.m3onErrorContainer
                    }

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - x - retry.width - parent.spacing

                        Label {
                            text: "No pudo arrancar"
                            role: "title.small"
                            color: Theme.m3onErrorContainer
                        }

                        Label {
                            width: parent.width
                            text: detail.s.error ?? ""
                            role: "body.small"
                            color: Theme.m3onErrorContainer
                            elide: Text.ElideRight
                        }
                    }

                    Button {
                        id: retry

                        type: "filled"
                        text: "Reintentar"
                        containerColor: Theme.m3onErrorContainer
                        contentRestColor: Theme.m3errorContainer
                        onClicked: procs.serviceAction(detail.s.unit, "restart")
                    }
                }
            }

            Rectangle {
                visible: detail.timer && !!detail.s.next_us
                width: parent.width
                height: Metrics.listItemTwoLine
                radius: Theme.rounding.large ?? 0
                color: Theme.m3tertiaryContainer

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Theme.padding.large ?? 0
                    spacing: Theme.spacing.medium ?? 0

                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: "schedule"
                        color: Theme.m3onTertiaryContainer
                    }

                    Column {
                        Label {
                            text: "Próxima ejecución en"
                            role: "label.medium"
                            color: Theme.m3onTertiaryContainer
                        }

                        RollingNumber {
                            text: detail.s.next_us ? page.countdown(detail.s.next_us) : ""
                            role: "title.large"
                            color: Theme.m3onTertiaryContainer
                        }
                    }
                }
            }

            Row {
                spacing: Theme.spacing.small ?? 0

                Button {
                    visible: detail.active && !detail.timer
                    type: "tonal"
                    icon: "stop_circle"
                    text: "Parar"
                    onClicked: procs.serviceAction(detail.s.unit, "stop")
                }

                Button {
                    visible: !detail.timer && !detail.failed
                    type: "tonal"
                    icon: "restart_alt"
                    text: "Reiniciar"
                    onClicked: procs.serviceAction(detail.s.unit, "restart")
                }

                Button {
                    visible: !detail.active && !detail.timer && !detail.failed
                    type: "filled"
                    icon: "play_arrow"
                    text: "Iniciar"
                    onClicked: procs.serviceAction(detail.s.unit, "start")
                }

                Button {
                    visible: detail.timer
                    type: "filled"
                    icon: "play_arrow"
                    text: "Ejecutar ahora"
                    onClicked: procs.serviceAction(detail.s.unit, "run")
                }

                Item {
                    width: Theme.spacing.large ?? 0
                    height: 1
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Iniciar con la sesión"
                    role: "body.medium"
                    color: Theme.m3onSurfaceVariant
                }

                Switch {
                    anchors.verticalCenter: parent.verticalCenter
                    checked: !!detail.s.enabled
                    onToggled: procs.serviceAction(detail.s.unit, detail.s.enabled ? "disable" : "enable")
                }
            }

            Row {
                visible: detail.active && !detail.timer
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Repeater {
                    model: [["Memoria", detail.s.memory ? Fmt.mem(detail.s.memory) : "—"], ["CPU usada", detail.s.cpu_ns ? (detail.s.cpu_ns / 1e9).toFixed(1) + " s" : "—"],
                            ["Tareas", String(detail.s.tasks ?? "—")], ["PID principal", String(detail.s.main_pid || "—")]]

                    Rectangle {
                        required property var modelData

                        width: (parent.width - parent.spacing * 3) / 4
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

        Rectangle {
            id: logCard

            anchors.top: detailHead.bottom
            anchors.topMargin: Theme.spacing.medium ?? 0
            anchors.bottom: parent.bottom
            anchors.margins: Theme.padding.medium ?? 0
            anchors.left: parent.left
            anchors.right: parent.right
            radius: Theme.rounding.large ?? 0
            color: Theme.m3surfaceContainerLowest

            Row {
                id: logHead

                x: Theme.padding.medium ?? 0
                height: Metrics.chipHeight + (Theme.spacing.small ?? 0)
                spacing: Theme.spacing.small ?? 0

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Registro"
                    role: "title.small"
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "journalctl --user -u " + (detail.s.unit ?? "")
                    role: "label.small"
                    font.family: Theme.font.family?.mono ?? ""
                    color: Theme.m3onSurfaceVariant
                }
            }

            ListView {
                id: logList

                property bool stick: true

                anchors.top: logHead.bottom
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: Theme.spacing.small ?? 0
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: procs.log
                onContentYChanged: stick = atYEnd
                onCountChanged: if (stick) Qt.callLater(positionViewAtEnd)
                delegate: Row {
                    required property var modelData

                    width: logList.width
                    spacing: Theme.spacing.medium ?? 0

                    Label {
                        text: parent.modelData.time
                        role: "label.medium"
                        font.family: Theme.font.family?.mono ?? ""
                        color: Theme.m3onSurfaceVariant
                    }

                    Label {
                        width: Metrics.chipHeight * 1.6
                        text: ({ info: "INFO", warn: "AVISO", err: "ERROR" })[parent.modelData.level] ?? ""
                        role: "label.medium"
                        font.family: Theme.font.family?.mono ?? ""
                        font.weight: Font.DemiBold
                        color: parent.modelData.level === "err" ? Theme.m3error : parent.modelData.level === "warn" ? Theme.m3tertiary : Theme.m3onSurfaceVariant
                    }

                    Label {
                        width: parent.width - x
                        text: parent.modelData.text
                        role: "label.medium"
                        font.family: Theme.font.family?.mono ?? ""
                        wrapMode: Text.WrapAnywhere
                        color: parent.modelData.level === "err" ? Theme.m3error : Theme.m3onSurface
                    }
                }
                add: Transition {
                    ParallelAnimation {
                        Anim {
                            property: "opacity"
                            from: 0
                            to: 1
                            kind: "defaultEffects"
                        }
                        Anim {
                            property: "x"
                            from: -(Theme.spacing.medium ?? 0)
                            to: 0
                            kind: "fastSpatial"
                        }
                    }
                }
            }

            Label {
                anchors.centerIn: logList
                visible: logList.count === 0
                text: "Sin registros recientes"
                role: "body.small"
                color: Theme.m3onSurfaceVariant
            }
        }
    }
}
