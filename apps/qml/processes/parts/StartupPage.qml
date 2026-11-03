// Inicio: when the session was ready and a timeline of what started, one bar per program coloured by impact; then
// the list with its source, impact, delay and switch. Pieces of Wysun and the exec-once lines of hyprland.lua are
// shown read only: the app never writes that file.
import QtQuick
import WysunM3

Item {
    id: page

    property bool shown
    property int selected: 0
    readonly property var items: procs.startupItems
    readonly property real span: Math.max(3, Math.ceil(Math.max(procs.readyAt, ...items.map(i => (i.ready_s ?? 0) + (i.delay ?? 0))) + 1))

    function impactColour(level) {
        return level >= 3 ? Theme.m3error : level === 2 ? Theme.m3tertiary : Theme.m3success;
    }
    function handleKey(event) {
        if (event.key === Qt.Key_Down || event.text === "j") {
            selected = Math.min(items.length - 1, selected + 1);
            return true;
        }
        if (event.key === Qt.Key_Up || event.text === "k") {
            selected = Math.max(0, selected - 1);
            return true;
        }
        const item = items[selected];
        if (!item || !item.editable)
            return false;
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return) {
            procs.setStartupEnabled(item.id, !item.enabled);
            return true;
        }
        if (event.text === "d") {
            procs.setStartupDelay(item.id, ({0: 5, 5: 10, 10: 0})[item.delay ?? 0]);
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

            Rectangle {
                width: parent.width
                height: timeline.height + (Theme.padding.large ?? 0) * 3 + title.height
                radius: Theme.rounding.extraLarge ?? 0
                color: Theme.m3surfaceContainerLow

                Row {
                    id: title

                    x: Theme.padding.large ?? 0
                    y: Theme.padding.large ?? 0
                    spacing: Theme.spacing.small ?? 0

                    Label {
                        text: "Tu sesión estuvo lista en"
                        role: "headline.small"
                    }

                    RollingNumber {
                        text: procs.readyAt.toFixed(1) + " s"
                        role: "headline.small"
                        color: Theme.m3primary
                    }
                }

                Item {
                    id: timeline

                    readonly property real labels: Metrics.drawerWidth * 0.6
                    readonly property real track: width - labels - (Theme.padding.large ?? 0)

                    anchors.top: title.bottom
                    anchors.topMargin: Theme.padding.large ?? 0
                    x: Theme.padding.large ?? 0
                    width: parent.width - x * 2
                    height: bars.height + Metrics.chipHeight

                    Column {
                        id: bars

                        width: parent.width

                        Repeater {
                            model: page.items

                            Item {
                                id: bar

                                required property var modelData
                                required property int index
                                readonly property real start: (modelData.started_s ?? 0) + (modelData.delay ?? 0)
                                readonly property real length: Math.max(0.08, (modelData.ready_s ?? start) - (modelData.started_s ?? 0))

                                width: bars.width
                                height: Metrics.chipHeight * 0.9
                                opacity: modelData.enabled ? 1 : 0.35

                                Label {
                                    width: timeline.labels - (Theme.spacing.medium ?? 0)
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: bar.modelData.name
                                    role: page.selected === bar.index ? "label.large" : "label.medium"
                                    color: page.selected === bar.index ? Theme.m3onSurface : Theme.m3onSurfaceVariant
                                    elide: Text.ElideRight
                                }

                                Rectangle {
                                    id: fillBar

                                    anchors.verticalCenter: parent.verticalCenter
                                    x: timeline.labels + timeline.track * bar.start / page.span
                                    height: parent.height * 0.5
                                    radius: height / 2
                                    width: page.shown ? Math.max(height, timeline.track * bar.length / page.span) : 0
                                    color: bar.modelData.started_s === null || bar.modelData.started_s === undefined ? Theme.m3outlineVariant : page.impactColour(bar.modelData.impact)
                                    border.width: page.selected === bar.index ? Metrics.focusRingWidth : 0
                                    border.color: Qt.alpha(color, 0.45)

                                    Behavior on width {
                                        Anim {
                                            kind: "slowSpatial"
                                        }
                                    }
                                    Behavior on x {
                                        Anim {
                                            kind: "defaultSpatial"
                                        }
                                    }
                                }

                                Label {
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: fillBar.x + fillBar.width + (Theme.spacing.small ?? 0)
                                    text: bar.modelData.started_s === null || bar.modelData.started_s === undefined ? "no está en marcha"
                                        : (bar.modelData.ready_s - bar.modelData.started_s > 0.05 ? (bar.modelData.ready_s - bar.modelData.started_s).toFixed(1) + " s" : bar.modelData.started_s.toFixed(1) + " s")
                                          + (bar.modelData.delay ? " · +" + bar.modelData.delay + " s" : "")
                                    role: "label.small"
                                    font.family: Theme.font.family?.mono ?? ""
                                    color: Theme.m3onSurfaceVariant
                                }

                                TapHandler {
                                    onTapped: page.selected = bar.index
                                }
                            }
                        }
                    }

                    Rectangle {
                        x: timeline.labels + timeline.track * procs.readyAt / page.span
                        height: bars.height
                        width: Metrics.outlineWidth * 2
                        color: Theme.m3primary

                        Behavior on x {
                            Anim {
                                kind: "defaultSpatial"
                            }
                        }

                        Label {
                            x: Theme.spacing.small ?? 0
                            text: "lista"
                            role: "label.small"
                            color: Theme.m3primary
                        }
                    }

                    Row {
                        anchors.bottom: parent.bottom
                        x: timeline.labels

                        Repeater {
                            model: page.span + 1

                            Label {
                                required property int index

                                width: timeline.track / page.span
                                text: index + " s"
                                role: "label.small"
                                font.family: Theme.font.family?.mono ?? ""
                                color: Theme.m3onSurfaceVariant
                            }
                        }
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: list.height + (Theme.padding.medium ?? 0) * 2
                radius: Theme.rounding.extraLarge ?? 0
                color: Theme.m3surfaceContainerLow

                Column {
                    id: list

                    y: Theme.padding.medium ?? 0
                    width: parent.width

                    Label {
                        x: Theme.padding.large ?? 0
                        height: Metrics.chipHeight
                        verticalAlignment: Text.AlignVCenter
                        text: ("Al iniciar sesión · " + page.items.filter(i => i.enabled).length + " activos").toUpperCase()
                        role: "label.small"
                        color: Theme.m3onSurfaceVariant
                    }

                    Repeater {
                        model: page.items

                        Rectangle {
                            id: entry

                            required property var modelData
                            required property int index

                            objectName: "startupRow-" + modelData.id
                            x: Theme.spacing.small ?? 0
                            width: list.width - x * 2
                            height: Metrics.listItemTwoLine
                            radius: Theme.rounding.large ?? 0
                            color: page.selected === index ? Theme.m3secondaryContainer : Qt.alpha(Theme.m3onSurface, entryHover.hovered ? Metrics.stateHover : 0)

                            HoverHandler {
                                id: entryHover
                            }

                            TapHandler {
                                onTapped: page.selected = entry.index
                            }

                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                x: Theme.padding.medium ?? 0
                                width: parent.width - x * 2
                                spacing: Theme.spacing.medium ?? 0

                                AppIcon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    source: entry.modelData.icon ?? ""
                                    tint: entry.modelData.tint ?? ""
                                    label: entry.modelData.name
                                }

                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - x - trailing.width - parent.spacing

                                    Label {
                                        width: parent.width
                                        text: entry.modelData.name
                                        role: "title.small"
                                        elide: Text.ElideRight
                                    }

                                    Label {
                                        width: parent.width
                                        text: entry.modelData.source === "session" ? "Parte de Wysun · no se puede quitar"
                                            : entry.modelData.source === "exec-once" ? "En hyprland.lua · solo lectura"
                                            : entry.modelData.enabled ? (entry.modelData.ready_s !== null && entry.modelData.ready_s !== undefined ? "Arrancó a los " + Number(entry.modelData.started_s).toFixed(1) + " s" : "Activado") : "No se inicia"
                                        role: "label.small"
                                        color: Theme.m3onSurfaceVariant
                                        elide: Text.ElideRight
                                    }
                                }

                                Row {
                                    id: trailing

                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: Theme.spacing.medium ?? 0

                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: sourceLabel.implicitWidth + (Theme.padding.medium ?? 0) * 2
                                        height: Metrics.chipHeight * 0.8
                                        radius: Theme.rounding.small ?? 0
                                        color: Theme.m3surfaceContainerHighest

                                        Label {
                                            id: sourceLabel

                                            anchors.centerIn: parent
                                            text: ({ session: "sesión", "exec-once": "exec-once", systemd: "systemd --user", autostart: "autostart" })[entry.modelData.source] ?? ""
                                            role: "label.small"
                                            font.family: Theme.font.family?.mono ?? ""
                                        }
                                    }

                                    Row {
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: Theme.spacing.extraSmall ?? 0

                                        Repeater {
                                            model: 3

                                            Rectangle {
                                                required property int index

                                                anchors.bottom: parent.bottom
                                                width: Theme.spacing.small ?? 0
                                                height: (index + 1) * (Theme.spacing.small ?? 0)
                                                radius: Theme.rounding.extraSmall ?? 0
                                                color: index < entry.modelData.impact ? page.impactColour(entry.modelData.impact) : Theme.m3outlineVariant
                                            }
                                        }
                                    }

                                    Chip {
                                        visible: entry.modelData.editable
                                        anchors.verticalCenter: parent.verticalCenter
                                        kind: "assist"
                                        icon: "timer"
                                        text: entry.modelData.delay ? "+" + entry.modelData.delay + " s" : "Sin retraso"
                                        onClicked: procs.setStartupDelay(entry.modelData.id, ({0: 5, 5: 10, 10: 0})[entry.modelData.delay ?? 0])
                                    }

                                    Loader {
                                        anchors.verticalCenter: parent.verticalCenter
                                        active: entry.modelData.editable
                                        sourceComponent: Switch {
                                            objectName: "startupSwitch-" + entry.modelData.id
                                            checked: entry.modelData.enabled
                                            onToggled: procs.setStartupEnabled(entry.modelData.id, !entry.modelData.enabled)
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
