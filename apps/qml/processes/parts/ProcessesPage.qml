// Procesos: the query bar with its filter chips, the view and owner toggles, the table (rows slide to their new
// place, the selection is a pill that follows with a spring) and the detail pane on the right.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: page

    property bool shown
    property Item overlayHost
    property bool detailShown: true
    readonly property real gap: Theme.spacing.medium ?? 0
    readonly property real detailWidth: Math.min(Metrics.richTooltipMaxWidth + Metrics.listItemTwoLine, width * 0.36)
    readonly property real rowHeight: Metrics.iconButtonSize + (Theme.spacing.small ?? 0)
    readonly property var columns: [
        {key: "cpu", label: "CPU", share: 0.13},
        {key: "mem", label: "Memoria", share: 0.13},
        {key: "gpu", label: "GPU", share: 0.09},
        {key: "io", label: "Disco", share: 0.14},
        {key: "threads", label: "Hilos", share: 0.08}
    ]

    signal returnFocus

    function focusSearch() {
        search.forceFocus();
    }

    function handleKey(event) {
        const key = procs.selectedKey;
        const shift = event.modifiers & Qt.ShiftModifier;
        switch (event.key) {
        case Qt.Key_Down:
            procs.move(1);
            return true;
        case Qt.Key_Up:
            procs.move(-1);
            return true;
        case Qt.Key_PageDown:
            procs.move(10);
            return true;
        case Qt.Key_PageUp:
            procs.move(-10);
            return true;
        case Qt.Key_Home:
            procs.move(-100000);
            return true;
        case Qt.Key_End:
            procs.move(100000);
            return true;
        case Qt.Key_Right:
            if (!procs.setExpanded(key, true))
                procs.move(1);
            return true;
        case Qt.Key_Left:
            if (!procs.setExpanded(key, false))
                procs.selectParent();
            return true;
        case Qt.Key_Return:
        case Qt.Key_Enter:
            if (!procs.setExpanded(key, !(procs.selected.expanded ?? false)))
                page.detailShown = true;
            return true;
        case Qt.Key_Delete:
            procs.act(shift ? "kill" : "terminate");
            return true;
        case Qt.Key_Space:
            procs.setFrozen(!procs.frozen);
            return true;
        case Qt.Key_BracketRight:
            detail.cycleTab(1);
            return true;
        case Qt.Key_BracketLeft:
            detail.cycleTab(-1);
            return true;
        }
        switch (event.text) {
        case "j":
            procs.move(1);
            return true;
        case "k":
            procs.move(-1);
            return true;
        case "g":
            procs.move(-100000);
            return true;
        case "G":
            procs.move(100000);
            return true;
        case "p":
        case "P":
            procs.act("pause");
            return true;
        case "+":
        case "-":
        case "=":
            procs.act("priority");
            return true;
        case "i":
            page.detailShown = !page.detailShown;
            return true;
        case "v":
            procs.cycleMode();
            return true;
        case "u":
            procs.setMine(!procs.mine);
            return true;
        case "y":
            procs.copyPid();
            return true;
        case "w":
            procs.focusWindow();
            return true;
        case "l":
        case "L":
            procs.locate();
            return true;
        case "s":
            procs.cycleSort();
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

    transform: Translate {
        y: page.shown ? 0 : (Theme.spacing.large ?? 0)

        Behavior on y {
            Anim {
                kind: "defaultSpatial"
            }
        }
    }

    Item {
        id: mainArea

        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: detailHolder.left
        anchors.margins: page.gap
        anchors.rightMargin: page.gap

        // Query bar: typing filters at once; filters such as cpu>10 become removable chips.
        Item {
            id: queryRow

            width: parent.width
            height: search.height

            Keys.onPressed: event => {
                if (event.key === Qt.Key_Escape) {
                    page.returnFocus();
                    event.accepted = true;
                } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    page.returnFocus();
                    if (event.key === Qt.Key_Down)
                        procs.move(1);
                    event.accepted = true;
                }
            }

            SearchBar {
                id: search

                objectName: "querySearch"
                anchors.left: parent.left
                anchors.right: tools.left
                anchors.rightMargin: page.gap
                placeholder: "Buscar · cpu>10  mem>500m  user:root  state:running"
                shortcut: ""
                onTextChanged: debounce.restart()
                onCleared: procs.setQuery("")
            }

            Timer {
                id: debounce

                interval: Theme.duration("small")
                onTriggered: procs.setQuery(search.text)
            }

            Connections {
                target: procs

                function onStateChanged() {
                    if (search.text !== procs.query && !debounce.running)
                        search.text = procs.query;
                }
            }

            Row {
                id: tools

                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacing.small ?? 0

                IconButton {
                    objectName: "freezeButton"
                    icon: procs.frozen ? "play_arrow" : "pause"
                    type: procs.frozen ? "tonal" : "standard"
                    onClicked: procs.setFrozen(!procs.frozen)
                }

                IconButton {
                    icon: "view_sidebar"
                    type: page.detailShown ? "standard" : "tonal"
                    onClicked: page.detailShown = !page.detailShown
                }
            }
        }

        // View, owner, refresh, active filters and the live summary.
        Item {
            id: toolbar

            anchors.top: queryRow.bottom
            anchors.topMargin: page.gap
            width: parent.width
            height: Metrics.segmentedHeight

            Row {
                id: left

                spacing: Theme.spacing.small ?? 0
                anchors.verticalCenter: parent.verticalCenter

                SegmentedButtons {
                    objectName: "viewSwitch"
                    model: [{value: "apps", text: "Por app", icon: "view_agenda"}, {value: "tree", text: "Árbol", icon: "account_tree"}, {value: "list", text: "Lista", icon: "list"}]
                    current: procs.mode
                    onActivated: value => procs.setMode(value)
                }

                Chip {
                    kind: "filter"
                    text: procs.mine ? "Mis procesos" : "Todos los usuarios"
                    selected: procs.mine
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: procs.setMine(!procs.mine)
                }

                Chip {
                    kind: "assist"
                    icon: "timer"
                    text: "Cada " + procs.interval / 1000 + " s"
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: procs.setInterval(procs.interval === 1000 ? 2000 : 1000)
                }

                Repeater {
                    model: procs.tokens

                    Chip {
                        required property string modelData

                        objectName: "token-" + modelData
                        kind: "input"
                        text: modelData
                        anchors.verticalCenter: parent.verticalCenter
                        onRemoved: procs.removeToken(modelData)
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacing.large ?? 0
                visible: toolbar.width - left.width > width + page.gap

                Row {
                    spacing: Theme.spacing.small ?? 0
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Theme.spacing.small ?? 0
                        height: width
                        radius: width / 2
                        color: procs.frozen ? Theme.m3outline : Theme.m3success

                        SequentialAnimation on opacity {
                            running: !procs.frozen && !Motion.reduced
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.35; duration: Theme.duration("extraLarge"); easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bezier("standard") }
                            NumberAnimation { to: 1; duration: Theme.duration("extraLarge"); easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bezier("standard") }
                        }
                    }

                    Label {
                        text: procs.frozen ? "Congelado" : "En vivo"
                        role: "label.large"
                        color: Theme.m3onSurfaceVariant
                    }
                }

                Label {
                    text: procs.matched + " procesos"
                    role: "label.large"
                    color: Theme.m3onSurfaceVariant
                }

                Label {
                    text: (procs.summary.running ?? 0) + " activos"
                    role: "label.large"
                    color: Theme.m3onSurfaceVariant
                }
            }
        }

        // The table.
        Rectangle {
            id: table

            objectName: "processTable"
            anchors.top: toolbar.bottom
            anchors.topMargin: page.gap
            anchors.bottom: parent.bottom
            width: parent.width
            radius: Theme.rounding.extraLarge ?? 0
            color: Theme.m3surfaceContainerLow
            clip: true

            readonly property real inner: width - (Theme.padding.large ?? 0) * 2
            readonly property real nameWidth: inner * (1 - page.columns.reduce((a, c) => a + c.share, 0))

            function columnX(index) {
                let x = (Theme.padding.large ?? 0) + nameWidth;
                for (let i = 0; i < index; i++)
                    x += inner * page.columns[i].share;
                return x;
            }

            Item {
                id: header

                width: parent.width
                height: Metrics.listItemOneLine

                Label {
                    x: Theme.padding.large ?? 0
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Nombre"
                    role: "label.large"
                    color: procs.sort === "name" ? Theme.m3primary : Theme.m3onSurfaceVariant

                    TapHandler {
                        onTapped: procs.sortBy("name")
                    }
                }

                Repeater {
                    model: page.columns

                    Item {
                        id: headCell

                        required property var modelData
                        required property int index
                        readonly property bool active: procs.sort === modelData.key

                        x: table.columnX(index)
                        width: table.inner * modelData.share
                        height: parent.height

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.padding.small ?? 0

                            Label {
                                visible: headCell.modelData.key !== "threads"
                                text: headCell.modelData.key === "cpu" ? Fmt.pct(procs.summary.cpu)
                                    : headCell.modelData.key === "mem" ? Fmt.mem(procs.summary.memory)
                                    : headCell.modelData.key === "gpu" ? Fmt.pct(procs.summary.gpu ?? -1)
                                    : Fmt.rate((procs.summary.disk_read ?? 0) + (procs.summary.disk_write ?? 0))
                                role: "title.small"
                                color: Theme.m3onSurface
                            }

                            Row {
                                spacing: Theme.spacing.extraSmall ?? 0

                                Label {
                                    text: headCell.modelData.label
                                    role: "label.medium"
                                    color: headCell.active ? Theme.m3primary : Theme.m3onSurfaceVariant
                                }

                                Icon {
                                    visible: headCell.active
                                    name: "arrow_downward"
                                    size: Metrics.chipIconSize * 0.8
                                    color: Theme.m3primary
                                    rotation: procs.descending ? 0 : 180

                                    Behavior on rotation {
                                        Anim {
                                            kind: "fastSpatial"
                                        }
                                    }
                                }
                            }
                        }

                        TapHandler {
                            onTapped: procs.sortBy(headCell.modelData.key)
                        }
                    }
                }
            }

            ListView {
                id: list

                objectName: "processList"
                anchors.top: header.bottom
                anchors.bottom: footer.top
                width: parent.width
                clip: true
                model: procs.rows
                currentIndex: procs.selectedIndex
                highlightFollowsCurrentItem: false
                boundsBehavior: Flickable.StopAtBounds
                reuseItems: true

                onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)

                Rectangle {
                    id: pill

                    parent: list.contentItem
                    z: -1
                    x: Theme.spacing.small ?? 0
                    width: list.width - x * 2
                    height: page.rowHeight
                    radius: Theme.rounding.large ?? 0
                    color: Theme.m3secondaryContainer
                    visible: list.currentItem !== null
                    y: list.currentItem ? list.currentItem.y : 0

                    Behavior on y {
                        Anim {
                            kind: "defaultSpatial"
                        }
                    }
                }

                delegate: ProcessRow {
                    width: list.width
                    height: page.rowHeight
                    columns: page.columns
                    columnX: i => table.columnX(i)
                    columnWidth: i => table.inner * page.columns[i].share
                    nameWidth: table.nameWidth
                    selectedRow: ListView.isCurrentItem
                    onActivated: page.returnFocus()
                }

                move: Transition {
                    Anim {
                        properties: "y"
                        kind: "defaultSpatial"
                    }
                }
                moveDisplaced: Transition {
                    Anim {
                        properties: "y"
                        kind: "defaultSpatial"
                    }
                }
                displaced: Transition {
                    Anim {
                        properties: "y"
                        kind: "defaultSpatial"
                    }
                }
                add: Transition {
                    Anim {
                        property: "opacity"
                        from: 0
                        to: 1
                        kind: "defaultEffects"
                    }
                }
                remove: Transition {
                    Anim {
                        property: "opacity"
                        to: 0
                        kind: "fastEffects"
                    }
                }
            }

            ScrollIndicator {
                anchors.right: parent.right
                anchors.top: list.top
                anchors.bottom: list.bottom
                flickable: list
            }

            EmptyState {
                anchors.centerIn: list
                visible: list.count === 0
                icon: "search_off"
                title: "Nada coincide"
                message: "Prueba con otro nombre o quita un filtro"
            }

            Rectangle {
                id: footer

                anchors.bottom: parent.bottom
                width: parent.width
                height: Metrics.chipHeight + (Theme.spacing.small ?? 0)
                color: Theme.m3surfaceContainerLow

                Rectangle {
                    width: parent.width
                    height: Metrics.outlineWidth
                    color: Theme.m3outlineVariant
                }

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Theme.padding.large ?? 0
                    spacing: Theme.spacing.large ?? 0

                    Repeater {
                        model: [["↑ ↓", "mover"], ["→ ←", "abrir o cerrar"], ["Supr", "terminar"], ["P", "pausar"], ["L", "localizar"], ["Ctrl K", "acciones"], ["?", "todos los atajos"]]

                        Row {
                            required property var modelData

                            spacing: Theme.spacing.extraSmall ?? 0

                            Rectangle {
                                width: keyLabel.implicitWidth + (Theme.padding.small ?? 0) * 2
                                height: keyLabel.implicitHeight + (Theme.spacing.extraSmall ?? 0)
                                radius: Theme.rounding.extraSmall ?? 0
                                color: Theme.m3surfaceContainerHighest
                                anchors.verticalCenter: parent.verticalCenter

                                Label {
                                    id: keyLabel

                                    anchors.centerIn: parent
                                    text: parent.parent.modelData[0]
                                    role: "label.small"
                                    font.family: Theme.font.family?.mono ?? ""
                                }
                            }

                            Label {
                                anchors.verticalCenter: parent.verticalCenter
                                text: parent.modelData[1]
                                role: "label.small"
                                color: Theme.m3onSurfaceVariant
                            }
                        }
                    }
                }
            }
        }
    }

    Item {
        id: detailHolder

        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: page.gap
        width: page.detailShown ? page.detailWidth : 0
        clip: true

        Behavior on width {
            Anim {
                kind: "defaultSpatial"
            }
        }

        DetailPane {
            id: detail

            width: page.detailWidth
            height: parent.height
            onCloseRequested: page.detailShown = false
        }
    }
}
