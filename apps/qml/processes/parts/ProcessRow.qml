// One row of the process table: indent and chevron for groups and the tree, the app's real icon, name and a line
// with state, PID and user, then CPU, memory, GPU, disk and threads in cells whose background warms with the load.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: row

    required property int index
    required property string key
    required property string title
    required property string name
    required property string app
    required property int pid
    required property int depth
    required property bool group
    required property int kids
    required property bool expanded
    required property bool appRow
    required property real cpu
    required property real mem
    required property real gpu
    required property real io
    required property int threads
    required property string state
    required property string stateLabel
    required property string user
    required property bool mine
    required property string icon
    required property string tint
    property var columns: []
    property var columnX: i => 0
    property var columnWidth: i => 0
    property real nameWidth: 0
    property bool selectedRow

    signal activated

    function heat(value, max) {
        const a = Math.min(1, Math.max(0, value) / max);
        return a < 0.08 ? 0 : 0.06 + a * 0.34;
    }

    opacity: state === "T" || state === "t" ? 0.55 : 1

    HoverHandler {
        id: hover
    }

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing.small ?? 0
        anchors.rightMargin: Theme.spacing.small ?? 0
        radius: Theme.rounding.large ?? 0
        color: Theme.m3onSurface
        opacity: hover.hovered && !row.selectedRow ? Metrics.stateHover : 0

        Behavior on opacity {
            Anim {
                kind: "fastEffects"
            }
        }
    }

    TapHandler {
        onTapped: {
            procs.select(row.key);
            row.activated();
        }
        onDoubleTapped: {
            if (row.group || row.kids > 0)
                procs.toggle(row.key);
        }
    }

    Row {
        x: (Theme.padding.large ?? 0) + row.depth * (Theme.spacing.extraLarge ?? 0)
        width: row.nameWidth - x
        height: parent.height
        spacing: Theme.spacing.small ?? 0

        Item {
            width: Metrics.chipHeight * 0.75
            height: parent.height

            Icon {
                anchors.centerIn: parent
                visible: row.group || row.kids > 0
                name: "chevron_right"
                size: Metrics.chipIconSize
                color: Theme.m3onSurfaceVariant
                rotation: row.expanded ? 90 : 0

                Behavior on rotation {
                    Anim {
                        kind: "fastSpatial"
                    }
                }

                TapHandler {
                    onTapped: procs.toggle(row.key)
                }
            }
        }

        AppIcon {
            anchors.verticalCenter: parent.verticalCenter
            visible: row.depth === 0 || row.group
            source: row.icon
            tint: row.tint
            label: row.title
            size: row.depth > 0 ? Metrics.chipAvatarSize : Metrics.chipHeight
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x

            Label {
                width: parent.width
                text: row.title
                role: row.group ? "title.small" : "body.medium"
                elide: Text.ElideRight
            }

            Row {
                spacing: Theme.spacing.extraSmall ?? 0

                Rectangle {
                    visible: !row.group
                    anchors.verticalCenter: parent.verticalCenter
                    width: Theme.spacing.small ?? 0
                    height: width
                    radius: width / 2
                    color: Theme["m3" + Fmt.stateColourRole(row.state)]
                }

                Label {
                    text: row.group ? row.kids + " procesos"
                        : row.stateLabel + " · " + row.pid + (row.mine ? "" : " · " + row.user)
                          + (row.appRow && row.name !== row.title ? " · " + row.name : "")
                    role: "label.small"
                    color: Theme.m3onSurfaceVariant
                    elide: Text.ElideRight
                }
            }
        }
    }

    Repeater {
        model: row.columns

        Item {
            id: cell

            required property var modelData
            required property int index
            readonly property real value: row[modelData.key]
            readonly property real load: modelData.key === "cpu" ? row.heat(row.cpu, 40)
                : modelData.key === "mem" ? row.heat(row.mem, 3 * 1073741824)
                : modelData.key === "gpu" ? row.heat(row.gpu, 40)
                : modelData.key === "io" ? row.heat(row.io, 1572864) : 0

            x: row.columnX(index)
            width: row.columnWidth(index) - (Theme.spacing.small ?? 0)
            height: parent.height

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                height: parent.height - (Theme.spacing.medium ?? 0)
                radius: Theme.rounding.small ?? 0
                color: Qt.alpha(Theme.m3primary, cell.load)

                Behavior on color {
                    ColorAnimation {
                        duration: Motion.ms("fastEffects")       // bounded: rows update every second
                    }
                }

                Rectangle {
                    visible: cell.modelData.key === "cpu" || cell.modelData.key === "mem"
                    anchors.bottom: parent.bottom
                    height: Metrics.progressThickness * 0.75
                    radius: height / 2
                    width: parent.width * Math.min(1, cell.modelData.key === "cpu" ? row.cpu / 40 : row.mem / (3 * 1073741824))
                    color: cell.modelData.key === "cpu" ? Theme.m3primary : Theme.m3tertiary

                    Behavior on width {
                        Anim {
                            kind: "fastEffects"
                            duration: Motion.ms("fastEffects")
                        }
                    }
                }

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Theme.padding.small ?? 0
                    text: cell.modelData.key === "cpu" ? Fmt.pct(row.cpu)
                        : cell.modelData.key === "mem" ? Fmt.mem(row.mem)
                        : cell.modelData.key === "gpu" ? (row.gpu < 0 ? "—" : Math.round(row.gpu) + " %")
                        : cell.modelData.key === "io" ? Fmt.rate(row.io) : String(row.threads)
                    role: "body.medium"
                    font.features: ({ "tnum": 1 })
                }
            }
        }
    }
}
