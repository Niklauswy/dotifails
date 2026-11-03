// Apps: one column per monitor, in the monitors' physical left-to-right order, with one row per window (16:9 live
// thumbnail, name, title, CPU and memory) grouped by workspace as thin separators; a narrower «Sin ventana» column
// lists the user's windowless apps by memory and folds the session's plumbing into a single «Sistema» line. A row
// opens its app sheet with a container transform. Narrow windows stack the columns with «Sin ventana» last.
import QtQuick
import WysunM3
import "Fmt.js" as Fmt

Item {
    id: page

    objectName: "appsPage"

    property bool shown
    property bool live: true          // the page and the window can be seen: only then do its animations run
    property int selectedColumn: 0
    property int selectedRow: 0
    property bool systemExpanded: false

    readonly property var stats: procs.stats
    readonly property var columns: procs.monitorColumns
    readonly property var windowless: procs.windowless
    readonly property var system: procs.systemWindowless
    readonly property int sideIndex: columns.length
    readonly property bool hasSide: windowless.length > 0 || (system.count ?? 0) > 0
    readonly property int columnCount: columns.length + (hasSide ? 1 : 0)
    readonly property real gap: Theme.spacing.medium ?? 0
    readonly property real contentWidth: Math.max(0, width - (Theme.spacing.medium ?? 0) * 2)
    // A row needs room for its thumbnail, name, title and figures; «Sin ventana» takes a drawer's width. Below that,
    // the columns stack (docs/qml-base.md: the adaptive classes of Metrics).
    readonly property real minColumnWidth: Metrics.drawerWidth + Theme.spacing.extraLarge
    readonly property real sideWidth: Metrics.drawerWidth + Theme.spacing.extraExtraLarge
    readonly property bool stacked: columns.length === 0 || contentWidth < columns.length * minColumnWidth
        + (hasSide ? sideWidth : 0) + gap * (Math.max(0, columns.length - 1) + (hasSide ? 1 : 0))
    readonly property real monitorWidth: columns.length === 0 ? contentWidth
        : Math.max(minColumnWidth, (contentWidth - (hasSide ? sideWidth : 0)
            - gap * (columns.length - 1 + (hasSide ? 1 : 0))) / columns.length)
    readonly property int windowCount: {
        let count = 0;
        for (const column of columns)
            count += column.count ?? 0;
        return count;
    }
    readonly property int windowlessCount: windowless.length + (system.apps ?? []).length
    readonly property bool empty: windowCount === 0 && !hasSide
    readonly property real bodyHeight: body.height
    // The bar compares each window with the heaviest one; CPU saturating a core always fills it.
    readonly property real referenceMem: {
        let top = 0;
        for (const column of columns)
            for (const space of column.workspaces)
                for (const window of space.windows) {
                    const stat = stats[window.app];
                    if (stat)
                        top = Math.max(top, stat.mem ?? 0);
                }
        for (const app of windowless)
            top = Math.max(top, app.mem ?? 0);
        for (const app of (system.apps ?? []))
            top = Math.max(top, app.mem ?? 0);
        return Math.max(1, top);
    }

    signal showProcesses(string app)

    // Rows of one column: windows for a monitor column, the windowless apps (and the folded system line) for the
    // side one. Keys are handled on this flat sequence.
    function entries(column) {
        const out = [];
        if (column < columns.length) {
            for (const space of columns[column].workspaces)
                for (const window of space.windows)
                    out.push(Object.assign({kind: "window", ws: space.id}, window));
        } else {
            for (const app of windowless)
                out.push(Object.assign({kind: "app"}, app));
            if ((system.count ?? 0) > 0)
                out.push({kind: "system"});
        }
        return out;
    }
    function currentEntry() {
        return entries(selectedColumn)[selectedRow] ?? null;
    }
    function clampSelection() {
        if (columnCount === 0) {
            selectedColumn = 0;
            selectedRow = 0;
            return;
        }
        let column = Math.max(0, Math.min(columnCount - 1, selectedColumn));
        if (entries(column).length === 0) {
            for (let i = 0; i < columnCount; i++) {
                if (entries(i).length > 0) {
                    column = i;
                    break;
                }
            }
        }
        selectedColumn = column;
        const list = entries(column);
        selectedRow = Math.max(0, Math.min(Math.max(0, list.length - 1), selectedRow));
    }
    function moveRow(delta) {
        const list = entries(selectedColumn);
        if (!list.length)
            return false;
        selectedRow = Math.max(0, Math.min(list.length - 1, selectedRow + delta));
        return true;
    }
    function moveColumn(delta) {
        let target = selectedColumn + delta;
        while (target >= 0 && target < columnCount && entries(target).length === 0)
            target += delta;
        if (target < 0 || target >= columnCount)
            return false;
        selectedColumn = target;
        selectedRow = Math.min(selectedRow, entries(target).length - 1);
        return true;
    }
    function openWindow(entry) {
        if (!entry || !(entry.address ?? ""))
            return;
        sheetHost.open(tileMap[entry.address] ?? page, sheetComponent, {entry: entry});
    }
    function toggleSystem() {
        systemExpanded = !systemExpanded;
    }
    readonly property var tileMap: ({})
    function registerTile(address, tile) {
        tileMap[address] = tile;
    }
    function unregisterTile(address) {
        delete tileMap[address];
    }
    function handleKey(event) {
        if (sheetHost.opened) {
            if (event.key === Qt.Key_Escape) {
                sheetHost.close();
                return true;
            }
            return false;
        }
        if (!columnCount)
            return false;
        if (event.key === Qt.Key_Right)
            return moveColumn(1);
        if (event.key === Qt.Key_Left)
            return moveColumn(-1);
        if (event.key === Qt.Key_Down || event.text === "j") {
            moveRow(1);
            return true;
        }
        if (event.key === Qt.Key_Up || event.text === "k") {
            moveRow(-1);
            return true;
        }
        const entry = currentEntry();
        if (!entry)
            return false;
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (entry.kind === "window")
                openWindow(entry);
            else if (entry.kind === "app")
                showProcesses(entry.app);
            else if (entry.kind === "system")
                toggleSystem();
            return true;
        }
        if (event.key === Qt.Key_Delete) {
            if (entry.kind !== "system")
                procs.closeApp(entry.app, event.modifiers & Qt.ShiftModifier);
            return true;
        }
        if (event.text === "l" || event.text === "L") {
            if (entry.kind !== "system")
                procs.locateApp(entry.app);
            return true;
        }
        if (event.text === "w") {
            if (entry.kind !== "system")
                procs.focusApp(entry.app);
            return true;
        }
        if (event.text === "i") {
            if (entry.kind !== "system")
                showProcesses(entry.app);
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

    Connections {
        target: procs

        function onAppsChanged() {
            page.clampSelection();
        }
    }

    Item {
        id: header

        x: Theme.spacing.medium ?? 0
        y: Theme.spacing.medium ?? 0
        width: page.width - x * 2
        height: Math.max(title.implicitHeight, hint.implicitHeight)

        Label {
            id: title

            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "Ventanas abiertas"
            role: "headline.small"
        }

        Label {
            id: hint

            anchors.left: title.right
            anchors.leftMargin: Theme.spacing.medium ?? 0
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "←/→ cambia de columna · Enter abre · L localiza · Supr cierra"
            role: "body.small"
            color: Theme.m3onSurfaceVariant
            elide: Text.ElideRight
        }
    }

    Item {
        id: body

        anchors.top: header.bottom
        anchors.topMargin: Theme.spacing.medium ?? 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.spacing.medium ?? 0
        anchors.rightMargin: Theme.spacing.medium ?? 0
        anchors.bottomMargin: Theme.spacing.medium ?? 0
        visible: !page.empty
    }

    Row {
        id: wide

        anchors.fill: body
        visible: !page.stacked && !page.empty
        spacing: page.gap

        Repeater {
            model: page.stacked ? [] : page.columns
            delegate: monitorColumnComponent
        }

        Repeater {
            model: page.stacked || !page.hasSide ? [] : [0]
            delegate: sideColumnComponent
        }
    }

    Flickable {
        id: stackFlick

        anchors.fill: body
        visible: page.stacked && !page.empty
        contentHeight: stackColumn.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: stackColumn

            width: stackFlick.width
            spacing: page.gap

            Repeater {
                model: page.stacked ? page.columns : []
                delegate: monitorColumnComponent
            }

            Repeater {
                model: page.stacked && page.hasSide ? [0] : []
                delegate: sideColumnComponent
            }
        }

        ScrollIndicator {
            anchors.right: parent.right
            height: parent.height
            flickable: stackFlick
        }
    }

    EmptyState {
        anchors.centerIn: parent
        visible: page.empty
        icon: "web_asset_off"
        title: "No hay ventanas abiertas"
        message: "Aquí aparecerán las ventanas de Hyprland con lo que gasta cada una"
    }

    Component {
        id: monitorColumnComponent

        Item {
            id: columnItem

            required property var modelData
            required property int index

            objectName: "monitorColumn-" + modelData.connector
            readonly property real pad: Theme.padding.medium ?? 0
            readonly property real headHeight: Math.max(monitorIcon.height, monitorName.implicitHeight, sidePill.height)
            width: page.stacked ? page.contentWidth : page.monitorWidth
            height: page.stacked
                ? pad * 2 + headHeight + (Theme.spacing.small ?? 0) + list.contentHeight
                : page.bodyHeight

            Rectangle {
                anchors.fill: parent
                radius: Theme.rounding.extraLarge ?? 0
                color: Theme.m3surfaceContainerLow
            }

            Icon {
                id: monitorIcon

                x: columnItem.pad
                y: columnItem.pad
                name: "desktop_windows"
                size: Metrics.chipIconSize
                color: Theme.m3onSurfaceVariant
            }

            Label {
                id: monitorName

                anchors.left: monitorIcon.right
                anchors.leftMargin: Theme.spacing.small ?? 0
                anchors.verticalCenter: monitorIcon.verticalCenter
                width: Math.max(0, columnItem.width - columnItem.pad * 2 - monitorIcon.width
                    - (Theme.spacing.small ?? 0) * 2 - (sidePill.visible ? sidePill.width : 0))
                text: columnItem.modelData.label ?? ""
                role: "title.medium"
                elide: Text.ElideRight
            }

            Rectangle {
                id: sidePill

                anchors.right: parent.right
                anchors.rightMargin: columnItem.pad
                anchors.verticalCenter: monitorIcon.verticalCenter
                visible: (columnItem.modelData.side ?? "") !== ""
                width: sideLabel.implicitWidth + (Theme.padding.medium ?? 0) * 2
                height: sideLabel.implicitHeight + (Theme.spacing.extraSmall ?? 0) * 2
                radius: height / 2
                color: Theme.m3surfaceContainerHigh

                Label {
                    id: sideLabel

                    anchors.centerIn: parent
                    text: columnItem.modelData.side
                    role: "label.small"
                    color: Theme.m3onSurfaceVariant
                }
            }

            Flickable {
                id: list

                x: columnItem.pad
                y: columnItem.pad + columnItem.headHeight + (Theme.spacing.medium ?? 0)
                width: parent.width - x * 2
                height: page.stacked ? contentColumn.height : parent.height - y - columnItem.pad
                contentHeight: contentColumn.height
                interactive: !page.stacked
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                function reveal(item) {
                    if (!interactive || contentHeight <= height)
                        return;
                    const top = item.mapToItem(contentItem, 0, 0).y;
                    const margin = Theme.spacing.small ?? 0;
                    if (top < contentY + margin)
                        contentY = Math.max(0, top - margin);
                    else if (top + item.height > contentY + height - margin)
                        contentY = Math.min(contentHeight - height, top + item.height - height + margin);
                }

                Column {
                    id: contentColumn

                    width: list.width
                    spacing: Theme.spacing.small ?? 0

                    Repeater {
                        model: columnItem.modelData.workspaces

                        Column {
                            id: workspaceItem

                            required property var modelData
                            required property int index
                            readonly property int base: {
                                let count = 0;
                                for (let i = 0; i < index; i++)
                                    count += columnItem.modelData.workspaces[i].windows.length;
                                return count;
                            }

                            width: contentColumn.width
                            spacing: Theme.spacing.extraSmall ?? 0

                            Item {
                                width: parent.width
                                height: workspaceName.implicitHeight + (Theme.spacing.small ?? 0)

                                Label {
                                    id: workspaceName

                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Espacio " + workspaceItem.modelData.id
                                        + (workspaceItem.modelData.current ? " · aquí" : "")
                                    role: "label.medium"
                                    color: workspaceItem.modelData.current ? Theme.m3primary : Theme.m3onSurfaceVariant
                                }

                                Rectangle {
                                    anchors.left: workspaceName.right
                                    anchors.leftMargin: Theme.spacing.small ?? 0
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    height: Metrics.outlineWidth
                                    color: Theme.m3outlineVariant
                                }
                            }

                            Repeater {
                                model: workspaceItem.modelData.windows

                                WindowTile {
                                    id: windowRow

                                    required property var modelData
                                    required property int index

                                    objectName: "windowRow-" + modelData.address
                                    width: workspaceItem.width
                                    entry: modelData
                                    stat: page.stats[modelData.app] ?? ({})
                                    referenceMem: page.referenceMem
                                    columnIndex: columnItem.index
                                    rowIndex: workspaceItem.base + index
                                    selected: page.selectedColumn === columnItem.index && page.selectedRow === rowIndex
                                    host: page
                                    onClicked: {
                                        page.selectedColumn = columnItem.index;
                                        page.selectedRow = rowIndex;
                                        page.openWindow(modelData);
                                    }
                                    onLocate: procs.locateApp(modelData.app)
                                    onCloseApp: procs.closeApp(modelData.app, false)
                                    onSelectedChanged: {
                                        if (selected)
                                            list.reveal(windowRow);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            ScrollIndicator {
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing.extraSmall ?? 0
                y: list.y
                height: list.height
                flickable: list
                visible: !page.stacked && list.contentHeight > list.height
            }
        }
    }

    Component {
        id: sideColumnComponent

        Item {
            id: sideItem

            objectName: "windowlessColumn"
            readonly property real pad: Theme.padding.medium ?? 0
            readonly property real headHeight: Math.max(sideTitle.implicitHeight, sideCount.height)
            width: page.stacked ? page.contentWidth : page.sideWidth
            height: page.stacked
                ? pad * 2 + headHeight + (Theme.spacing.small ?? 0) + sideContent.height
                : page.bodyHeight

            Rectangle {
                anchors.fill: parent
                radius: Theme.rounding.extraLarge ?? 0
                color: Theme.m3surfaceContainerLow
            }

            Label {
                id: sideTitle

                x: sideItem.pad
                y: sideItem.pad
                text: "Sin ventana"
                role: "title.medium"
            }

            Rectangle {
                id: sideCount

                anchors.right: parent.right
                anchors.rightMargin: sideItem.pad
                anchors.verticalCenter: sideTitle.verticalCenter
                width: sideCountLabel.implicitWidth + (Theme.padding.medium ?? 0) * 2
                height: sideCountLabel.implicitHeight + (Theme.spacing.extraSmall ?? 0) * 2
                radius: height / 2
                color: Theme.m3surfaceContainerHigh

                Label {
                    id: sideCountLabel

                    objectName: "windowlessCount"
                    anchors.centerIn: parent
                    text: String(page.windowlessCount)
                    role: "label.small"
                    color: Theme.m3onSurfaceVariant
                    font.features: ({ "tnum": 1 })
                }
            }

            Flickable {
                id: sideList

                x: sideItem.pad
                y: sideItem.pad + sideItem.headHeight + (Theme.spacing.medium ?? 0)
                width: parent.width - x * 2
                height: page.stacked ? sideContent.height : parent.height - y - sideItem.pad
                contentHeight: sideContent.height
                interactive: !page.stacked
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: sideContent

                    width: sideList.width
                    spacing: Theme.spacing.extraSmall ?? 0

                    Repeater {
                        model: page.windowless

                        Item {
                            id: appRow

                            required property var modelData
                            required property int index
                            readonly property bool selected: page.selectedColumn === page.sideIndex
                                && page.selectedRow === index

                            objectName: "windowlessRow-" + modelData.app
                            width: sideContent.width
                            height: Metrics.iconButtonSize

                            Rectangle {
                                anchors.fill: parent
                                radius: Theme.rounding.small ?? 0
                                color: appRow.selected ? Theme.m3surfaceContainerHigh : Theme.m3surfaceContainerLow
                            }

                            Label {
                                id: appName

                                x: Theme.spacing.small ?? 0
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(0, parent.width - x - appCpu.width - appMem.width
                                    - (Theme.spacing.small ?? 0) * 2)
                                text: appRow.modelData.name ?? ""
                                role: "body.small"
                                elide: Text.ElideRight
                            }

                            Label {
                                id: appCpu

                                anchors.right: appMem.left
                                anchors.rightMargin: Theme.spacing.small ?? 0
                                anchors.verticalCenter: parent.verticalCenter
                                width: Theme.spacing.extraExtraLarge
                                text: Fmt.pct(appRow.modelData.cpu ?? 0)
                                role: "label.small"
                                color: Theme.m3onSurfaceVariant
                                horizontalAlignment: Text.AlignRight
                                font.features: ({ "tnum": 1 })
                            }

                            Label {
                                id: appMem

                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: Theme.spacing.extraExtraLarge * 1.5
                                text: Fmt.mem(appRow.modelData.mem ?? 0)
                                role: "label.small"
                                color: Theme.m3onSurfaceVariant
                                horizontalAlignment: Text.AlignRight
                                font.features: ({ "tnum": 1 })
                            }

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: Metrics.outlineWidth
                                color: Theme.m3outlineVariant
                                opacity: 0.5
                            }

                            TapHandler {
                                onTapped: {
                                    page.selectedColumn = page.sideIndex;
                                    page.selectedRow = appRow.index;
                                }
                                onDoubleTapped: page.showProcesses(appRow.modelData.app)
                            }
                        }
                    }

                    Item {
                        id: systemLine

                        readonly property bool selected: page.selectedColumn === page.sideIndex
                            && page.selectedRow === page.windowless.length

                        objectName: "systemWindowless"
                        width: sideContent.width
                        height: Metrics.iconButtonSize
                        visible: (page.system.count ?? 0) > 0

                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.rounding.small ?? 0
                            color: systemLine.selected ? Theme.m3surfaceContainerHigh : Theme.m3surfaceContainerLow
                        }

                        Label {
                            id: systemName

                            objectName: "systemWindowlessLabel"
                            x: Theme.spacing.small ?? 0
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.max(0, parent.width - x - systemMem.width - systemChevron.width
                                - (Theme.spacing.small ?? 0))
                            text: "Sistema · " + (page.system.count ?? 0)
                                + ((page.system.count ?? 0) === 1 ? " proceso" : " procesos")
                            role: "label.large"
                            elide: Text.ElideRight
                        }

                        Label {
                            id: systemMem

                            anchors.right: systemChevron.left
                            anchors.rightMargin: Theme.spacing.small ?? 0
                            anchors.verticalCenter: parent.verticalCenter
                            width: Theme.spacing.extraExtraLarge + Theme.spacing.small
                            text: Fmt.mem(page.system.mem ?? 0)
                            role: "label.small"
                            color: Theme.m3onSurfaceVariant
                            horizontalAlignment: Text.AlignRight
                            font.features: ({ "tnum": 1 })
                        }

                        Icon {
                            id: systemChevron

                            anchors.right: parent.right
                            anchors.rightMargin: Theme.spacing.small ?? 0
                            anchors.verticalCenter: parent.verticalCenter
                            name: page.systemExpanded ? "expand_less" : "expand_more"
                            size: Metrics.chipIconSize
                            color: Theme.m3onSurfaceVariant
                        }

                        TapHandler {
                            onTapped: {
                                page.selectedColumn = page.sideIndex;
                                page.selectedRow = page.windowless.length;
                                page.toggleSystem();
                            }
                        }
                    }

                    Column {
                        id: systemAppsColumn

                        objectName: "systemWindowlessApps"
                        width: sideContent.width
                        visible: page.systemExpanded

                        Repeater {
                            model: page.systemExpanded ? (page.system.apps ?? []) : []

                            Item {
                                required property var modelData

                                width: systemAppsColumn.width
                                height: Metrics.iconButtonSize

                                Label {
                                    x: Theme.padding.large ?? 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Math.max(0, parent.width - x - systemAppCpu.width - systemAppMem.width
                                        - (Theme.spacing.small ?? 0) * 2)
                                    text: parent.modelData.name ?? ""
                                    role: "body.small"
                                    color: Theme.m3onSurfaceVariant
                                    elide: Text.ElideRight
                                }

                                Label {
                                    id: systemAppCpu

                                    anchors.right: systemAppMem.left
                                    anchors.rightMargin: Theme.spacing.small ?? 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Theme.spacing.extraExtraLarge
                                    text: Fmt.pct(parent.modelData.cpu ?? 0)
                                    role: "label.small"
                                    color: Theme.m3onSurfaceVariant
                                    horizontalAlignment: Text.AlignRight
                                    font.features: ({ "tnum": 1 })
                                }

                                Label {
                                    id: systemAppMem

                                    anchors.right: parent.right
                                    anchors.rightMargin: Theme.spacing.small ?? 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: Theme.spacing.extraExtraLarge * 1.5
                                    text: Fmt.mem(parent.modelData.mem ?? 0)
                                    role: "label.small"
                                    color: Theme.m3onSurfaceVariant
                                    horizontalAlignment: Text.AlignRight
                                    font.features: ({ "tnum": 1 })
                                }
                            }
                        }
                    }
                }
            }

            ScrollIndicator {
                anchors.right: parent.right
                anchors.rightMargin: Theme.spacing.extraSmall ?? 0
                y: sideList.y
                height: sideList.height
                flickable: sideList
                visible: !page.stacked && sideList.contentHeight > sideList.height
            }
        }
    }

    ContainerTransform {
        id: sheetHost

        objectName: "appSheetHost"
        anchors.fill: parent
        containerColor: Theme.m3surfaceContainer
        endRadius: Theme.rounding.extraLarge ?? 0
    }

    Component {
        id: sheetComponent

        AppSheet {
            onCloseRequested: sheetHost.close()
            onShowProcesses: app => {
                sheetHost.close();
                page.showProcesses(app);
            }
        }
    }
}
