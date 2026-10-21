pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

FloatingWindow {
    id: win
    title: "Wysun Processes"
    implicitWidth: Math.min(1320, (screen?.width ?? 1440) * 0.92)
    implicitHeight: Math.min(850, (screen?.height ?? 1000) * 0.86)
    minimumSize.width: 980
    minimumSize.height: 620
    color: Colours.tPalette.m3surface
    contentItem.Config.screen: screen.name
    contentItem.Tokens.screen: screen.name
    onVisibleChanged: if (!visible) destroy()
    property var rows: []
    property var summary: ({})
    property var history: ({cpu: [], memory: [], gpu: [], disk: [], network: []})
    property var selected: null
    property var selectedKey: null
    property var details: ({})
    property var processHistory: []
    property bool exited: false
    property bool frozen: false
    property bool started: false
    property string failure: ""
    property string message: ""
    property int matched: 0
    property string query: ""
    property string owner: "mine"
    property string mode: "list"
    property string sort: "cpu"
    property bool descending: true
    property var collapsed: []
    property int interval: 2
    onQueryChanged: table.positionViewAtBeginning()
    onModeChanged: table.positionViewAtBeginning()
    onOwnerChanged: table.positionViewAtBeginning()
    onSortChanged: table.positionViewAtBeginning()
    onDescendingChanged: table.positionViewAtBeginning()
    property var pending: null
    property bool busy: false
    readonly property bool canAct: !!selected?.actionable && !exited && !busy
    readonly property string script: Quickshell.shellPath('modules/processes/backend.py')
    readonly property var control: ({query: query, owner: owner, mode: mode, sort: sort, descending: descending,
        collapsed: collapsed, selected: selectedKey, interval: interval})
    function send(): void { if (started) feed.write(JSON.stringify(control) + '\n'); }
    onControlChanged: send()
    function size(value: var): string {
        if (value === null || value === undefined) return "—";
        let n = Number(value), i = 0; const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
        while (n >= 1024 && i < 4) { n /= 1024; i++; }
        return n.toFixed(i ? 1 : 0) + ' ' + units[i];
    }
    function pct(value: var): string { return value === null || value === undefined ? '—' : Number(value).toFixed(1) + '%'; }
    function rate(value: var): string { return value === null || value === undefined ? '—' : size(value) + '/s'; }
    function reorder(key: string): void { if (sort === key) descending = !descending; else { sort = key; descending = key !== 'name' && key !== 'pid'; } }
    function fold(key: var): void { const a = collapsed.slice(); const i = a.indexOf(key); if (i < 0) a.push(key); else a.splice(i, 1); collapsed = a; }
    function choose(row: var): void {
        if (row.group) { fold(row.app); return; }
        selected = row; selectedKey = [row.pid, row.start]; details = {}; processHistory = []; exited = false; message = '';
        const identity = JSON.stringify(selectedKey);
        call({row: row, action: 'details'}, data => { if (identity === JSON.stringify(selectedKey)) details = data; }, error => { if (identity === JSON.stringify(selectedKey)) message = error; });
    }
    function refreshDetails(): void {
        if (!selected || exited) return;
        const key = JSON.stringify(selectedKey);
        call({row: selected, action: 'details'}, data => { if (key === JSON.stringify(selectedKey)) details = data; }, error => { if (key === JSON.stringify(selectedKey)) message = error; });
    }
    function call(args: var, done: var, failed: var): void { callComponent.createObject(win, {command: ['/usr/bin/python3', script, JSON.stringify(args)], done: done, failed: failed, running: true}); }
    function ask(action: string, nice: int): void { pending = {row: Object.assign({}, selected), action: action, nice: nice}; }
    function confirm(): void {
        const args = pending; pending = null; busy = true;
        call(args, () => { busy = false; message = 'Action completed.'; }, error => { busy = false; message = error; });
    }
    function detailText(): string {
        if (!selected) return '';
        const d = details;
        return 'Command\n' + (d.command || 'Not accessible') + '\n\nExecutable\n' + (d.exe || 'Not accessible') +
            '\n\nWorking directory\n' + (d.cwd || 'Not accessible') + '\n\nControl group\n' + (d.cgroup || 'Not accessible') +
            '\n\nThreads (' + (d.thread_count ?? selected.threads) + ')\n' + (d.threads || []).slice(0, 30).map(t => t.tid + '  ' + t.name + ' · ' + t.state + ' · ' + t.cpu_time.toFixed(1) + 's').join('\n') +
            '\n\nOpen files (' + (d.file_count ?? 'unavailable') + ')\n' + (d.files || []).map(f => f[0] + '  ' + f[1]).join('\n');
    }
    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: { if (win.pending) win.pending = null; else win.destroy(); }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Tokens.padding.large
            spacing: Tokens.spacing.medium
            RowLayout {
                Layout.fillWidth: true
                MaterialIcon { text: 'monitoring'; color: Colours.palette.m3primary }
                ColumnLayout {
                    spacing: Tokens.spacing.extraSmall
                    StyledText { text: 'Processes'; font: Tokens.font.headline.small }
                    StyledText { text: (win.frozen ? 'Paused' : 'Live') + ' · ' + (win.summary.count ?? 0) + ' processes · ' + (win.summary.running ?? 0) + ' running'; color: Colours.palette.m3onSurfaceVariant }
                }
                Item { Layout.fillWidth: true }
                TextButton { text: win.interval + 's refresh'; onClicked: win.interval = win.interval === 1 ? 2 : win.interval === 2 ? 5 : 1 }
                TextButton { text: win.frozen ? 'Resume' : 'Pause updates'; onClicked: win.frozen = !win.frozen }
                TextButton { text: 'Close'; onClicked: win.destroy() }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.small
                Metric { Layout.fillWidth: true; label: 'CPU'; value: win.pct(win.summary.cpu); samples: win.history.cpu; subtitle: (win.summary.cores ?? 0) + ' logical cores' }
                Metric { Layout.fillWidth: true; label: 'Memory'; value: win.size(win.summary.memory); samples: win.history.memory; ceiling: win.summary.total_memory ?? 1; tone: Colours.palette.m3tertiary; subtitle: 'of ' + win.size(win.summary.total_memory) }
                Metric { Layout.fillWidth: true; label: 'GPU'; value: win.pct(win.summary.gpu); samples: win.history.gpu; tone: Colours.palette.m3secondary; subtitle: win.summary.gpu === null || win.summary.gpu === undefined ? 'Driver telemetry unavailable' : win.summary.gpu_source + (win.summary.gpu_memory === null ? '' : ' · ' + win.size(win.summary.gpu_memory)) }
                Metric { Layout.fillWidth: true; label: 'Disk I/O'; value: win.rate(win.summary.disk); samples: win.history.disk; ceiling: Math.max(1048576, ...win.history.disk); subtitle: 'Physical devices · read + write' }
                Metric { Layout.fillWidth: true; label: 'Network'; value: win.rate(win.summary.network); samples: win.history.network; ceiling: Math.max(1048576, ...win.history.network); tone: Colours.palette.m3tertiary; subtitle: 'System · receive + send' }
            }
            RowLayout {
                Layout.fillWidth: true
                StyledTextField { Layout.fillWidth: true; placeholderText: 'Search name, pid:, user:, cpu>5, mem>500m'; leadingIcon: 'search'; text: win.query; onTextEdited: win.query = text; verticalPadding: Tokens.padding.small }
                TextButton { text: win.owner === 'mine' ? 'My processes' : 'All users'; onClicked: win.owner = win.owner === 'mine' ? 'all' : 'mine' }
                Repeater {
                    model: ['list', 'tree', 'apps']
                    TextButton {
                        required property string modelData
                        text: ({list: 'List', tree: 'Tree', apps: 'Applications'})[modelData]
                        isToggle: true; checked: win.mode === modelData
                        onClicked: { win.mode = modelData; internalChecked = true; win.collapsed = []; }
                    }
                }
            }
            StyledText { visible: !!win.failure; text: win.failure; color: Colours.palette.m3error; Layout.fillWidth: true; wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Tokens.spacing.medium
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Colours.tPalette.m3surfaceContainerLow
                    radius: Tokens.rounding.medium
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Tokens.padding.small
                        spacing: Tokens.spacing.extraSmall
                        Row {
                            id: header
                            Layout.fillWidth: true
                            Repeater {
                                model: [{key:'name', label:'Process', weight:0.32}, {key:'pid', label:'PID', weight:0.09}, {key:'cpu', label:'CPU', weight:0.11}, {key:'memory', label:'Memory', weight:0.16}, {key:'gpu', label:'GPU', weight:0.11}, {key:'read_rate', label:'Read/s', weight:0.105}, {key:'write_rate', label:'Write/s', weight:0.105}]
                                Item {
                                    required property var modelData
                                    width: header.width * modelData.weight; height: Tokens.spacing.extraLargeIncreased
                                    StyledText { anchors.verticalCenter: parent.verticalCenter; text: modelData.label + (win.sort === modelData.key ? (win.descending ? ' ↓' : ' ↑') : ''); color: win.sort === modelData.key ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: win.reorder(parent.modelData.key) }
                                }
                            }
                        }
                        ListView {
                            id: table
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: win.rows
                            boundsBehavior: Flickable.StopAtBounds
                            Controls.ScrollBar.vertical: Controls.ScrollBar {}
                            delegate: Rectangle {
                                id: entry
                                required property var modelData
                                required property int index
                                width: table.width
                                height: Tokens.spacing.extraExtraLarge
                                radius: Tokens.rounding.small
                                color: win.selectedKey && modelData.pid === win.selectedKey[0] && modelData.start === win.selectedKey[1] ? Colours.palette.m3secondaryContainer : hover.containsMouse ? Colours.tPalette.m3surfaceContainerHigh : 'transparent'
                                MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: win.choose(entry.modelData) }
                                Row {
                                    anchors.fill: parent
                                    Item {
                                        width: table.width * 0.32; height: parent.height
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.rightMargin: Tokens.padding.small
                                            spacing: Tokens.spacing.extraSmall
                                            Item { width: Math.min(entry.modelData.depth ?? 0, 6) * Tokens.spacing.medium; Layout.fillHeight: true }
                                            Item {
                                                Layout.preferredWidth: Tokens.spacing.large
                                                Layout.fillHeight: true
                                                StyledText {
                                                    anchors.centerIn: parent
                                                    text: entry.modelData.group || entry.modelData.hasChildren ? (win.collapsed.includes(entry.modelData.group ? entry.modelData.app : entry.modelData.pid) ? '▸' : '▾') : '·'
                                                    color: Colours.palette.m3primary
                                                }
                                                MouseArea { anchors.fill: parent; enabled: !!entry.modelData.hasChildren || !!entry.modelData.group; cursorShape: Qt.PointingHandCursor; onClicked: win.fold(entry.modelData.group ? entry.modelData.app : entry.modelData.pid) }
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true; spacing: 0
                                                StyledText { Layout.fillWidth: true; text: entry.modelData.name; elide: Text.ElideRight; font: Tokens.font.label.medium }
                                                StyledText { Layout.fillWidth: true; text: entry.modelData.group ? entry.modelData.count + ' processes' : entry.modelData.user + ' · ' + entry.modelData.stateLabel; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; elide: Text.ElideRight }
                                            }
                                        }
                                    }
                                    Repeater {
                                        model: [{value:entry.modelData.group ? '—' : entry.modelData.pid, weight:0.09}, {value:win.pct(entry.modelData.cpu), weight:0.11}, {value:win.size(entry.modelData.memory), weight:0.16}, {value:win.pct(entry.modelData.gpu), weight:0.11}, {value:win.size(entry.modelData.read_rate), weight:0.105}, {value:win.size(entry.modelData.write_rate), weight:0.105}]
                                        Item {
                                            required property var modelData
                                            width: table.width * modelData.weight; height: entry.height
                                            StyledText { anchors.verticalCenter: parent.verticalCenter; width: parent.width - Tokens.spacing.extraSmall; text: parent.modelData.value; elide: Text.ElideRight; font: Tokens.font.label.small }
                                        }
                                    }
                                }
                            }
                            StyledText { anchors.centerIn: parent; visible: !table.count; text: win.started ? 'No matching processes' : 'Connecting to process telemetry…'; color: Colours.palette.m3onSurfaceVariant }
                        }
                        StyledText { text: win.matched + ' matching · ' + win.rows.length + (win.rows.length === 1 ? ' row' : ' rows') + ' · CPU: 100% = one logical core'; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
                    }
                }
                Rectangle {
                    Layout.preferredWidth: win.selected ? Math.max(280, win.width * 0.25) : 240
                    Layout.fillHeight: true
                    color: Colours.tPalette.m3surfaceContainer
                    radius: Tokens.rounding.medium
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: Tokens.padding.medium; spacing: Tokens.spacing.small
                        StyledText { text: win.selected ? win.selected.name : 'Process inspector'; font: Tokens.font.title.medium; Layout.fillWidth: true; elide: Text.ElideRight }
                        StyledText { text: win.selected ? 'PID ' + win.selected.pid + ' · parent ' + win.selected.ppid + ' · ' + (win.exited ? 'Exited' : win.selected.stateLabel) : 'Select a process to inspect its activity, files and threads.'; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Colours.palette.m3onSurfaceVariant }
                        Metric { visible: !!win.selected; Layout.fillWidth: true; implicitHeight: Tokens.spacing.extraExtraLarge * 2.5; label: 'Process CPU · ' + win.size(win.selected?.memory); value: win.pct(win.selected?.cpu); samples: win.processHistory; ceiling: Math.max(100, ...win.processHistory); subtitle: win.selected ? win.selected.threads + (win.selected.threads === 1 ? ' thread' : ' threads') + ' · nice ' + win.selected.nice : '' }
                        StyledText { visible: !!win.selected; text: win.selected?.reason || 'Actions affect only the selected process.'; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small }
                        Flow {
                            visible: !!win.selected; Layout.fillWidth: true; Layout.preferredHeight: childrenRect.height; spacing: Tokens.spacing.extraSmall
                            enabled: win.canAct
                            TextButton { disabled: !win.canAct; text: 'End process'; onClicked: win.ask('terminate', 0) }
                            TextButton { disabled: !win.canAct; text: 'Force kill'; onClicked: win.ask('kill', 0) }
                            TextButton { disabled: !win.canAct; text: (win.selected?.state === 'T' || win.selected?.state === 't') ? 'Resume' : 'Suspend'; onClicked: win.ask((win.selected?.state === 'T' || win.selected?.state === 't') ? 'resume' : 'pause', 0) }
                            TextButton { disabled: !win.canAct; text: 'Priority'; onClicked: win.ask('priority', win.selected.nice) }
                        }
                        StyledText { visible: !!win.message; text: win.message; color: Colours.palette.m3primary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        TextButton { visible: !!win.selected && !win.exited; text: 'Refresh details'; onClicked: win.refreshDetails() }
                        Controls.ScrollView {
                            Layout.fillHeight: true; Layout.fillWidth: true; clip: true
                            Controls.TextArea { text: win.selected ? win.detailText() : 'GPU per process requires DRM fdinfo support.\n\nPer-process network usage is unavailable without privileged tracing. The network graph shows system totals.\n\nDisk rates count physical I/O; cached reads may be zero.'; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small; background: null }
                        }
                    }
                }
            }
        }
        Rectangle {
            anchors.fill: parent
            visible: !!win.pending
            color: Qt.alpha(Colours.palette.m3scrim, 0.7)
            MouseArea { anchors.fill: parent; onClicked: win.pending = null }
            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - Tokens.padding.extraLarge * 2, 480)
                height: confirmation.implicitHeight + Tokens.padding.extraLarge * 2
                radius: Tokens.rounding.large
                color: Colours.tPalette.m3surfaceContainerHigh
                MouseArea { anchors.fill: parent }
                ColumnLayout {
                    id: confirmation
                    anchors.fill: parent; anchors.margins: Tokens.padding.extraLarge; spacing: Tokens.spacing.large
                    StyledText { text: win.pending?.action === 'priority' ? 'Change process priority' : win.pending?.action === 'kill' ? 'Force kill process?' : 'Confirm process action'; font: Tokens.font.title.large; Layout.fillWidth: true; Layout.maximumWidth: confirmation.width; wrapMode: Text.Wrap }
                    StyledText { text: (win.pending?.row.name ?? '') + ' · PID ' + (win.pending?.row.pid ?? '') + '\n\n' + (win.pending?.action === 'kill' ? 'The process will stop immediately. Unsaved work may be lost.' : win.pending?.action === 'priority' ? 'Nice ranges from −20 (highest priority) to 19 (lowest). Raising priority may require administrator privileges.' : 'Send ' + ({terminate:'a termination request', pause:'a suspend signal', resume:'a resume signal'})[win.pending?.action] + ' to this process?'); Layout.fillWidth: true; Layout.maximumWidth: confirmation.width; wrapMode: Text.Wrap }
                    RowLayout {
                        visible: win.pending?.action === 'priority'
                        TextButton { text: '−'; onClicked: win.pending = Object.assign({}, win.pending, {nice: Math.max(-20, win.pending.nice - 1)}) }
                        StyledText { text: String(win.pending?.nice ?? 0); Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                        TextButton { text: '+'; onClicked: win.pending = Object.assign({}, win.pending, {nice: Math.min(19, win.pending.nice + 1)}) }
                    }
                    RowLayout {
                        Item { Layout.fillWidth: true }
                        TextButton { text: 'Cancel'; onClicked: win.pending = null }
                        TextButton { text: 'Confirm'; onClicked: win.confirm() }
                    }
                }
            }
        }
    }
    Process {
        id: feed
        command: ['/usr/bin/python3', win.script]
        stdinEnabled: true
        running: win.visible
        onStarted: { win.started = true; win.failure = ''; win.send(); }
        onExited: (code, status) => { win.started = false; if (win.visible) win.failure = 'Telemetry stopped. Close and reopen Processes to reconnect.'; }
        stdout: SplitParser {
            onRead: line => {
                try {
                    const data = JSON.parse(line);
                    if (data.ok === false) { win.failure = data.error; return; }
                    if (win.frozen) return;
                    const scroll = table.contentY;
                    win.rows = data.rows;
                    Qt.callLater(() => { table.contentY = Math.max(0, Math.min(scroll, table.contentHeight - table.height)); });
                    win.summary = data.summary; win.matched = data.matched;
                    if (win.selectedKey) { win.exited = !data.selected; if (data.selected) win.selected = data.selected; }
                    if (!data.redraw) {
                        const h = Object.assign({}, win.history);
                        for (const key of ['cpu', 'memory', 'gpu', 'disk', 'network']) if (data.summary[key] !== null && data.summary[key] !== undefined) h[key] = h[key].concat([data.summary[key]]).slice(-60);
                        win.history = h;
                        if (data.selected) win.processHistory = win.processHistory.concat([data.selected.cpu]).slice(-60);
                    }
                } catch (error) { win.failure = 'Invalid telemetry: ' + error; }
            }
        }
    }
    Component {
        id: callComponent
        Process {
            id: request
            property var done
            property var failed
            stdout: StdioCollector {
                onStreamFinished: {
                    try { const reply = JSON.parse(text); if (reply.ok) request.done(reply.data); else request.failed(reply.error); }
                    catch (error) { request.failed('Process service did not respond.'); }
                    request.destroy();
                }
            }
        }
    }
}
