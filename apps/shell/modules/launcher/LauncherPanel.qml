pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Wysun
import Wysun.Config
import Wysun.Services
import qs.components
import qs.components.controls
import qs.components.effects
import qs.services
import qs.modules.launcher.services
import "services/Actions.js" as Actions
import "services/Files.js" as Files
import "services/Results.js" as Results

// Raycast-style command palette: search, grouped results, optional preview, actions popover
// and a push/pop view stack. Result lists are rebuilt from in-memory indexes on every keystroke.
Item {
    id: root

    required property ShellScreen screen
    required property ScreenState state
    required property real reveal

    readonly property real scale: Math.max(0.85, Math.min(1.5, screen.height / 1080))
    readonly property real panelWidth: Math.min(760 * scale, screen.width - Tokens.padding.extraExtraLarge * 2)
    readonly property real panelHeight: Math.min(500 * scale, screen.height - Tokens.padding.extraExtraLarge * 2)
    readonly property real maxPanelHeight: panelHeight
    readonly property font fontBody: Tokens.font.body.builders.medium.size(10.5 * scale).build()
    readonly property font fontSmall: Tokens.font.body.builders.small.size(9 * scale).build()
    readonly property font fontStrong: Tokens.font.body.builders.small.size(9 * scale).weight(Font.Medium).build()
    property real originX
    property real originY
    property string filter: "all"
    property bool filterOpen
    property string actionFilter
    readonly property var filterOptions: ({
            clipboard: [["all", "All Types"], ["text", "Text Only"], ["image", "Images Only"], ["url", "Links Only"], ["color", "Colors Only"]],
            files: [["all", "All Files"], ["image", "Images Only"], ["folder", "Folders Only"]]
        })
    readonly property var filters: filterOptions[current.id] ?? null
    readonly property string filterLabel: (filters?.find(f => f[0] === filter) ?? ["", ""])[1]
    readonly property alias surface: surface

    property var stack: [{id: "root"}]
    readonly property var current: stack[stack.length - 1]
    property int selected: -1
    property bool autoFirst: true
    property bool actionsOpen
    property bool previewFocus
    property bool ctrlHeld
    property string confirmKey
    property string selKey
    property real pointerX: -1
    property real pointerY: -1
    property real hlY
    property real hlH
    property bool hlOn
    readonly property string query: search.text

    readonly property var results: current.id === "root" ? Results.root(query, LauncherIndex.context) : current.id === "snippet-form" ? [] : Results.view(current.id, query, LauncherIndex.context, current.target, filter)
    readonly property var items: flatten(results)
    readonly property var row: items[selected] ?? null
    readonly property bool formOpen: current.id === "snippet-form"
    readonly property bool previewOn: !!row && ["file", "clip", "snippet"].includes(row.kind) && !formOpen
    readonly property bool busy: LauncherIndex.filesBusy && (current.id === "root" || current.id === "files") && query.trim() !== ""

    readonly property var placeholders: ({
            root: "Search apps, files, commands...",
            clipboard: "Search clipboard history...",
            snippets: "Search snippets...",
            windows: "Search open windows...",
            files: "Search files and folders...",
            apps: "Search applications...",
            system: "Search system commands...",
            "calc-history": "Search calculator history...",
            openwith: "Choose an application..."
        })
    readonly property var titles: ({
            clipboard: "Clipboard History", snippets: "Snippets", windows: "Windows", files: "Files", apps: "Applications",
            system: "System", "calc-history": "Calculator History", openwith: "Open With", "snippet-form": "Snippet"
        })

    function flatten(list: var): var {
        const out = [];
        let last = null, n = 0;
        for (const r of list) {
            if (r.section && r.section !== last)
                out.push({header: true, key: "h:" + r.section, title: r.section});
            last = r.section;
            out.push(Object.assign({}, r, {n: n++}));
        }
        return out;
    }

    function close(): void {
        state.launcher = false;
    }

    function reset(): void {
        pointerX = -1;
        stack = [{id: "root"}];
        search.clear();
        actionsOpen = false;
        previewFocus = false;
        confirmKey = "";
        autoFirst = true;
        LauncherIndex.searchFiles("");
        LauncherIndex.refresh();
    }

    function push(view: var): void {
        filter = "all";
        filterOpen = false;
        search.clear();
        stack = stack.concat([view]);
        actionsOpen = false;
        confirmKey = "";
        autoFirst = true;
        LauncherIndex.searchFiles("");
        if (view.id === "files")
            LauncherIndex.loadRecentFiles();
        else if (view.id === "calc-history")
            LauncherIndex.loadCalcHistory();
        else if (view.id === "clipboard")
            LauncherIndex.loadStatus();
        else if (view.id === "windows")
            LauncherIndex.refreshWindows();
        else if (view.id === "snippet-form") {
            form.load(view.snippet ?? null);
            return;
        }
        viewAnim.restart();
        search.forceActiveFocus();
    }

    function pop(): void {
        if (stack.length < 2)
            return;
        filter = "all";
        filterOpen = false;
        search.clear();
        stack = stack.slice(0, -1);
        actionsOpen = false;
        confirmKey = "";
        autoFirst = true;
        LauncherIndex.searchFiles("");
        viewAnim.restart();
        search.forceActiveFocus();
    }

    function select(i: int): void {
        if (i < 0 || i >= items.length || items[i].header)
            return;
        selected = i;
        selKey = items[i].key;
        autoFirst = false;
        confirmKey = "";
    }

    function firstSelectable(): int {
        return items.findIndex(r => !r.header);
    }

    function move(d: int): void {
        let i = selected + d;
        const step = d < 0 ? -1 : 1;
        while (i >= 0 && i < items.length && items[i].header)
            i += step;
        if (i < 0 || i >= items.length) {
            // Wrap around
            i = step > 0 ? firstSelectable() : items.length - 1;
            while (i > 0 && items[i].header)
                i--;
        }
        select(i);
    }

    // Keep the selected entry across streaming updates; jump to the first one after a new query.
    function syncSelection(): void {
        let i = !autoFirst && selKey ? items.findIndex(r => r.key === selKey) : -1;
        if (i < 0)
            i = firstSelectable();
        selected = i;
        selKey = items[i]?.key ?? "";
    }

    onItemsChanged: syncSelection()
    onSelectedChanged: {
        if (selected >= 0)
            list.positionViewAtIndex(items[selected - 1]?.header ? selected - 1 : selected, ListView.Contain);
    }
    onQueryChanged: {
        autoFirst = true;
        Qt.callLater(syncSelection);
        confirmKey = "";
        if (current.id === "root" || current.id === "files")
            filesDebounce.restart();
    }

    // Activation ---------------------------------------------------------------------------------

    function xdg(target: string): void {
        Quickshell.execDetached(["xdg-open", target]);
    }

    function copyText(text: string): void {
        Quickshell.execDetached(["wl-copy", "--", text]);
    }

    function dirname(path: string): string {
        return path.slice(0, path.lastIndexOf("/")) || "/";
    }

    function runArgv(argv: var): void {
        if (argv[0] === "setMode")
            Colours.setMode(argv[1]);
        else if (!SessionManager.exec(argv))
            Quickshell.execDetached(argv);
    }

    function dispatchWindow(verb: string, address: string): void {
        const addr = address.startsWith("0x") ? address : "0x" + address;
        const lua = {focus: `hl.dsp.focus({ window = "address:${addr}" })`, close: `hl.dsp.window.close({ window = "address:${addr}" })`};
        Hypr.dispatch(Hypr.usingLua ? lua[verb] : (verb === "focus" ? "focuswindow" : "closewindow") + ` address:${addr}`);
    }

    function activate(r: var): void {
        if (!r || r.header)
            return;
        switch (r.kind) {
        case "app":
            Apps.launch(r);
            close();
            return;
        case "cmd":
            if (r.view) {
                push({id: r.view});
                return;
            }
            if (r.form) {
                push({id: "snippet-form"});
                return;
            }
            if (r.emoji) {
                close();
                state.emoji = true;
                return;
            }
            if (r.confirm && confirmKey !== r.key) {
                confirmKey = r.key;
                return;
            }
            LauncherIndex.remember(r);
            runArgv(r.argv);
            close();
            return;
        case "file":
            LauncherIndex.remember(r);
            xdg(r.path);
            close();
            return;
        case "window":
            dispatchWindow("focus", r.address);
            close();
            return;
        case "web":
            xdg(`https://duckduckgo.com/?q=${encodeURIComponent(r.query)}`);
            close();
            return;
        case "run":
            Quickshell.execDetached([...GlobalConfig.general.apps.terminal, `${Quickshell.shellDir}/assets/wrap_term_launch.sh`, "sh", "-c", r.command]);
            close();
            return;
        case "openwith":
            Quickshell.execDetached(["gtk-launch", r.id, r.target]);
            close();
            return;
        case "clip":
        case "snippet":
        case "calc":
        case "history":
            LauncherData.copy(r);
            close();
            return;
        }
    }

    function secondaryOf(r: var): var {
        return Actions.actionsFor(r, false, []).find(a => a.shortcut === "Ctrl ↵") ?? null;
    }

    function desktopActionsOf(r: var): var {
        return r?.kind === "app" ? Array.from(r.entry.actions ?? []) : [];
    }

    function runAction(a: var): void {
        const r = row;
        if (!r || !a)
            return;
        const stay = ["pin", "delete", "capture", "clear", "edit", "openwith"].includes(a.id);
        if (a.danger && actionMenu.confirmId !== a.id) {
            actionMenu.confirmId = a.id;
            return;
        }
        actionMenu.confirmId = "";
        if (a.id.startsWith("desktop:"))
            Apps.run(desktopActionsOf(r)[parseInt(a.id.slice(8))], false);
        else
            switch (a.id) {
            case "open": activate(r); return;
            case "pin": LauncherIndex.togglePin(r); break;
            case "copy-title": copyText(r.title); break;
            case "folder": xdg(dirname(r.path)); break;
            case "openwith": actionsOpen = false; push({id: "openwith", target: r.path}); return;
            case "copy-path": copyText(r.path); break;
            case "copy-file": Quickshell.execDetached(["wl-copy", "--type", "text/uri-list", "--", "file://" + r.path + "\r\n"]); break;
            case "copy": LauncherData.copy(r); break;
            case "paste": LauncherData.paste(r); break;
            case "copy-expression": copyText(r.expression); break;
            case "open-image": LauncherIndex.exportClip(r.id, path => xdg(path)); break;
            case "delete": LauncherIndex.mutate([r.kind === "clip" ? "delete-clip" : "delete-snippet", String(r.id)]); break;
            case "edit": actionsOpen = false; push({id: "snippet-form", snippet: r}); return;
            case "capture": LauncherIndex.mutate(["toggle-capture"]); break;
            case "clear": LauncherIndex.mutate(["clear-clips"]); break;
            case "close-window": dispatchWindow("close", r.address); break;
            }
        actionsOpen = false;
        if (!stay)
            close();
    }

    function openActions(): void {
        actionFilter = "";
        actionMenu.current = 0;
        actionMenu.confirmId = "";
        actionsOpen = true;
    }

    function saveSnippet(): void {
        const args = ["save-snippet", form.title, form.shortcut, form.body];
        if (form.snippetId >= 0)
            args.push(String(form.snippetId));
        LauncherIndex.mutate(args);
        pop();
    }

    function handleKey(e: var): void {
        const ctrl = (e.modifiers & Qt.ControlModifier) !== 0;
        e.accepted = true;
        if (e.key === Qt.Key_Control) {
            ctrlHeld = true;
            e.accepted = false;
            return;
        }
        if (actionsOpen) {
            if (e.key === Qt.Key_Backspace && actionFilter) actionFilter = actionFilter.slice(0, -1);
            else if (!ctrl && e.text.length === 1 && e.text >= " " && e.key !== Qt.Key_Escape) actionFilter += e.text;
            else if (e.key === Qt.Key_Up) actionMenu.move(-1);
            else if (e.key === Qt.Key_Down) actionMenu.move(1);
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) runAction(actionMenu.actions[actionMenu.current]);
            else if (e.key === Qt.Key_Escape || (ctrl && e.key === Qt.Key_K)) actionsOpen = false;
            else e.accepted = false;
            return;
        }
        if (previewFocus) {
            if (e.key === Qt.Key_Up) preview.scrollBy(-60);
            else if (e.key === Qt.Key_Down) preview.scrollBy(60);
            else if (e.key === Qt.Key_PageUp) preview.scrollBy(-240);
            else if (e.key === Qt.Key_PageDown) preview.scrollBy(240);
            else if (e.key === Qt.Key_Tab || e.key === Qt.Key_Backtab || e.key === Qt.Key_Escape || e.key === Qt.Key_Left) previewFocus = false;
            else e.accepted = false;
            return;
        }
        if (e.key === Qt.Key_Escape) {
            if (stack.length > 1) pop(); else close();
        } else if (e.key === Qt.Key_Up) move(-1);
        else if (e.key === Qt.Key_Down) move(1);
        else if (e.key === Qt.Key_PageUp) move(-6);
        else if (e.key === Qt.Key_PageDown) move(6);
        else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            const second = ctrl && row ? secondaryOf(row) : null;
            if (second) runAction(second); else activate(row);
        } else if (e.key === Qt.Key_Tab) {
            if (previewOn) previewFocus = true;
        } else if (e.key === Qt.Key_Backspace && search.text === "" && stack.length > 1) pop();
        else if (ctrl && e.key === Qt.Key_K) {
            if (row) openActions();
        } else if (ctrl && e.key === Qt.Key_Delete) {
            const del = Actions.actionsFor(row, false, []).find(a => a.shortcut === "Ctrl Del");
            if (del) runAction(del);
        } else if (ctrl && e.key >= Qt.Key_1 && e.key <= Qt.Key_9) {
            const target = items.find(r => r.n === e.key - Qt.Key_1);
            if (target) activate(target);
        } else
            e.accepted = false;
    }

    Timer {
        id: filesDebounce

        interval: 120
        onTriggered: LauncherIndex.searchFiles(root.query)
    }

    Connections {
        target: root.state

        function onLauncherChanged(): void {
            if (root.state.launcher) {
                root.reset();
                root.adoptRoute();
                search.forceActiveFocus();
            }
        }
        function onLauncherCategoryChanged(): void { root.adoptRoute(); }
        function onLauncherQueryChanged(): void { root.adoptRoute(); }
    }

    function adoptRoute(): void {
        if (!state.launcher)
            return;
        const views = {clip: "clipboard", snippets: "snippets", windows: "windows", files: "files", apps: "apps", calc: "calc-history", commands: "system"};
        const cat = state.launcherCategory;
        if (cat && views[cat]) {
            state.launcherCategory = "";
            push({id: views[cat]});
        } else if (cat) {
            state.launcherCategory = "";
        }
        if (state.launcherQuery) {
            search.text = state.launcherQuery;
            state.launcherQuery = "";
        }
    }

    // Visuals ------------------------------------------------------------------------------------

    readonly property color hairline: Qt.alpha(Colours.palette.m3onSurface, 0.1)
    readonly property real rowRadius: Tokens.rounding.small

    implicitWidth: panelWidth
    implicitHeight: panelHeight

    Elevation {
        anchors.fill: surface
        radius: surface.radius
        level: 5
        opacity: surface.opacity
        scale: surface.scale
    }

    Rectangle {
        id: surface

        width: root.panelWidth
        height: root.panelHeight
        radius: Tokens.rounding.medium
        color: "transparent"
        opacity: root.reveal
        scale: 0.96 + 0.04 * root.reveal

        // Frosted material: the wallpaper, blurred and tinted, under a translucent surface.
        Item {
            id: material

            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: maskShape
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1
            }

            Image {
                id: wall

                x: -(root.originX + root.x + surface.x)
                y: -(root.originY + root.y + surface.y)
                width: root.screen.width
                height: root.screen.height
                source: Wallpapers.current ? "file://" + Wallpapers.current : ""
                sourceSize: Qt.size(root.screen.width / 4, root.screen.height / 4)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                layer.enabled: true
                layer.effect: MultiEffect {
                    blurEnabled: true
                    blurMax: 48
                    blur: 1
                    saturation: 0.2
                }
            }
            Rectangle {
                anchors.fill: parent
                color: Qt.alpha(Colours.palette.m3surface, Colours.light ? 0.82 : 0.78)
            }
        }
        Item {
            id: maskShape

            anchors.fill: parent
            visible: false
            layer.enabled: true

            Rectangle {
                anchors.fill: parent
                radius: surface.radius
            }
        }
        Rectangle {
            anchors.fill: parent
            radius: surface.radius
            color: "transparent"
            border.width: 1
            border.color: Qt.alpha(Colours.palette.m3onSurface, 0.14)
        }

        // Header -------------------------------------------------------------------------------
        Item {
            id: head

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 56 * root.scale

            Rectangle {
                id: lead

                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.medium
                anchors.verticalCenter: parent.verticalCenter
                width: 28 * root.scale
                height: width
                radius: width / 2
                color: root.stack.length > 1 ? Qt.alpha(Colours.palette.m3onSurface, 0.1) : "transparent"

                MaterialIcon {
                    anchors.centerIn: parent
                    text: root.stack.length > 1 ? "arrow_back" : "search"
                    color: root.stack.length > 1 ? Colours.palette.m3onSurface : Colours.palette.m3onSurfaceVariant
                    fontStyle: Tokens.font.icon.builders.medium.scale(root.scale * 0.9).build()
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: root.stack.length > 1
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.pop()
                }
            }

            TextFieldBase {
                id: search

                anchors.left: lead.right
                anchors.leftMargin: Tokens.spacing.small
                anchors.right: filterBox.visible ? filterBox.left : busy.left
                anchors.rightMargin: Tokens.spacing.medium
                anchors.verticalCenter: parent.verticalCenter
                visible: !root.formOpen
                background: null
                leftPadding: 0
                rightPadding: 0
                font: Tokens.font.body.builders.large.size(12.75 * root.scale).build()
                focus: true
                placeholderText: ""
                onTextChanged: root.previewFocus = false
                Keys.onPressed: event => root.handleKey(event)
                Keys.onReleased: event => {
                    if (event.key === Qt.Key_Control)
                        root.ctrlHeld = false;
                }

                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: search.text === ""
                    text: root.placeholders[root.current.id] ?? ""
                    font: search.font
                    color: Colours.palette.m3onSurfaceVariant
                }
            }

            LoadingIndicator {
                id: busy

                anchors.right: parent.right
                anchors.rightMargin: Tokens.padding.large
                anchors.verticalCenter: parent.verticalCenter
                width: 18 * root.scale
                height: width
                visible: root.busy && !filterBox.visible
            }

            // Compact filter dropdown (clipboard, files)
            Rectangle {
                id: filterBox

                anchors.right: parent.right
                anchors.rightMargin: Tokens.padding.medium
                anchors.verticalCenter: parent.verticalCenter
                visible: !!root.filters && !root.formOpen
                width: filterRow.implicitWidth + Tokens.padding.large
                height: 30 * root.scale
                radius: Tokens.rounding.small
                color: filterMouse.containsMouse ? Qt.alpha(Colours.palette.m3onSurface, 0.1) : "transparent"
                border.width: 1
                border.color: Qt.alpha(Colours.palette.m3onSurface, 0.16)

                Row {
                    id: filterRow

                    anchors.centerIn: parent
                    spacing: Tokens.spacing.medium

                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.filterLabel
                        font: root.fontStrong
                    }
                    MaterialIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "keyboard_arrow_down"
                        fontStyle: Tokens.font.icon.small
                        color: Colours.palette.m3onSurface
                    }
                }
                MouseArea {
                    id: filterMouse

                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.filterOpen = !root.filterOpen
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: root.hairline
            }
        }

        // Body ---------------------------------------------------------------------------------
        Item {
            id: body

            anchors.top: head.bottom
            anchors.bottom: foot.top
            anchors.left: parent.left
            anchors.right: parent.right

            property real listWidth: root.previewOn ? width * 0.4 : width

            Behavior on listWidth {
                NumberAnimation {
                    duration: Tokens.anim.durations.small * 0.8
                    easing: Tokens.anim.standard
                }
            }

            Item {
                id: listBox

                width: body.listWidth
                height: parent.height
                visible: !root.formOpen

                ListView {
                    id: list

                    anchors.fill: parent
                    anchors.margins: Tokens.padding.small
                    clip: true
                    reuseItems: true
                    cacheBuffer: 400
                    boundsBehavior: Flickable.StopAtBounds
                    currentIndex: root.selected
                    highlightFollowsCurrentItem: false
                    model: ScriptModel {
                        values: root.items
                        objectProp: "key"
                    }
                    delegate: ResultRow {
                        panel: root
                    }

                    // Selection pill: slides between rows; rows report their geometry when current.
                    Rectangle {
                        x: 0
                        y: root.hlY
                        z: -1
                        width: list.width
                        height: root.hlH
                        radius: root.rowRadius
                        color: Qt.alpha(Colours.palette.m3onSurface, 0.1)
                        opacity: root.hlOn && root.items.length > 0 ? 1 : 0

                        Behavior on y {
                            enabled: root.hlOn
                            NumberAnimation {
                                duration: Tokens.anim.durations.small * 0.7
                                easing: Tokens.anim.standard
                            }
                        }
                        Behavior on height {
                            NumberAnimation {
                                duration: Tokens.anim.durations.small * 0.5
                                easing: Tokens.anim.standard
                            }
                        }
                    }
                }

                StyledText {
                    anchors.centerIn: parent
                    width: parent.width - Tokens.padding.extraLarge * 2
                    visible: root.items.length === 0 && !root.formOpen && !root.busy
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: Results.emptyText(root.current.id, root.query)
                    font: root.fontBody
                    color: Colours.palette.m3onSurfaceVariant
                }
            }

            Rectangle {
                x: body.listWidth
                width: 1
                height: parent.height
                color: root.hairline
                opacity: root.previewOn ? 1 : 0
            }

            PreviewPane {
                id: preview

                x: body.listWidth + 1
                width: body.width - body.listWidth - 1
                height: parent.height
                opacity: root.previewOn ? 1 : 0
                visible: opacity > 0.01
                scale: root.scale
                row: root.previewOn ? root.row : null
                focusedPane: root.previewFocus
                decodeSize: Qt.size(root.panelWidth * 0.6 * 2, 200 * root.scale * 2)

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            SnippetForm {
                id: form

                anchors.fill: parent
                visible: root.formOpen
                onSubmit: root.saveSnippet()
                onCancel: root.pop()
            }
        }

        // Footer -------------------------------------------------------------------------------
        Item {
            id: foot

            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 40 * root.scale

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: root.hairline
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.medium
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.spacing.small

                readonly property bool appIcon: !!root.row && !root.formOpen && root.stack.length === 1 && (root.row.kind === "app" || root.row.kind === "window")

                AppIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: parent.appIcon
                    name: parent.appIcon ? root.row.icon : ""
                    size: 20 * root.scale
                }
                // The extension icon carries the only accent colour.
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: !parent.appIcon
                    width: 20 * root.scale
                    height: width
                    radius: Tokens.rounding.extraSmall + 1
                    color: Colours.palette.m3primary

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: root.stack.length > 1 ? root.viewIcons[root.current.id] ?? "bolt" : root.row && !root.formOpen ? root.row.icon || "bolt" : "search"
                        color: Colours.palette.m3onPrimary
                        fontStyle: Tokens.font.icon.builders.small.scale(root.scale * 0.8).build()
                    }
                }
                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.formOpen ? "New Snippet" : root.stack.length > 1 ? root.titles[root.current.id] ?? "" : root.row ? root.row.title : "Wysun"
                    font: root.fontStrong
                    color: Colours.palette.m3onSurfaceVariant
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, root.panelWidth * 0.4)
                }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: Tokens.padding.small
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.spacing.medium
                visible: !root.formOpen

                Row {
                    spacing: Tokens.spacing.small
                    anchors.verticalCenter: parent.verticalCenter

                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Actions.primaryLabel(root.row)
                        font: root.fontStrong
                    }
                    Keycaps {
                        anchors.verticalCenter: parent.verticalCenter
                        keys: ["↵"]
                    }
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 1
                    height: 16 * root.scale
                    color: root.hairline
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: actionsHint.implicitWidth + Tokens.padding.medium
                    height: 28 * root.scale
                    radius: Tokens.rounding.small
                    color: actionsMouse.containsMouse || root.actionsOpen ? Qt.alpha(Colours.palette.m3onSurface, 0.1) : "transparent"

                    Row {
                        id: actionsHint

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.small

                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Actions"
                            font: root.fontStrong
                            color: Colours.palette.m3onSurfaceVariant
                        }
                        Keycaps {
                            anchors.verticalCenter: parent.verticalCenter
                            keys: ["Ctrl", "K"]
                        }
                    }
                    MouseArea {
                        id: actionsMouse

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!root.row)
                                return;
                            if (root.actionsOpen)
                                root.actionsOpen = false;
                            else
                                root.openActions();
                        }
                    }
                }
            }
        }

        // Filter dropdown menu
        Rectangle {
            visible: root.filterOpen && !!root.filters
            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.medium
            anchors.top: head.bottom
            anchors.topMargin: -Tokens.padding.extraSmall
            width: 180 * root.scale
            height: filterList.implicitHeight + Tokens.padding.small * 2
            radius: Tokens.rounding.small
            color: Qt.alpha(Colours.palette.m3surfaceContainerHigh, 0.97)
            border.width: 1
            border.color: Qt.alpha(Colours.palette.m3onSurface, 0.16)
            z: 5

            Column {
                id: filterList

                anchors.fill: parent
                anchors.margins: Tokens.padding.small

                Repeater {
                    model: root.filters ?? []

                    Rectangle {
                        id: opt

                        required property var modelData

                        width: filterList.width
                        height: 30 * root.scale
                        radius: Tokens.rounding.extraSmall
                        color: optMouse.containsMouse ? Qt.alpha(Colours.palette.m3onSurface, 0.1) : "transparent"

                        StyledText {
                            anchors.left: parent.left
                            anchors.leftMargin: Tokens.padding.small
                            anchors.verticalCenter: parent.verticalCenter
                            text: opt.modelData[1]
                            font: root.fontStrong
                        }
                        MaterialIcon {
                            anchors.right: parent.right
                            anchors.rightMargin: Tokens.padding.small
                            anchors.verticalCenter: parent.verticalCenter
                            visible: root.filter === opt.modelData[0]
                            text: "check"
                            fontStyle: Tokens.font.icon.small
                        }
                        MouseArea {
                            id: optMouse

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.filter = opt.modelData[0];
                                root.filterOpen = false;
                                root.autoFirst = true;
                                search.forceActiveFocus();
                            }
                        }
                    }
                }
            }
        }

        // Actions popover
        ActionsMenu {
            id: actionMenu

            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.small
            anchors.bottom: foot.top
            anchors.bottomMargin: Tokens.padding.extraSmall
            scale: root.scale
            source: Actions.actionsFor(root.row, root.row ? LauncherIndex.isPinned(root.row) : false, root.desktopActionsOf(root.row))
            filterText: root.actionFilter
            visible: opacity > 0.01
            opacity: root.actionsOpen ? 1 : 0
            transformOrigin: Item.BottomRight
            onTriggered: a => root.runAction(a)

            Behavior on opacity {
                Anim {
                    type: Anim.FastEffects
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            z: -1
            onClicked: {
                root.actionsOpen = false;
                root.filterOpen = false;
            }
        }
    }

    // View change: the list slides in a few pixels while fading.
    ParallelAnimation {
        id: viewAnim

        NumberAnimation {
            target: listBox
            property: "opacity"
            from: 0
            to: 1
            duration: Tokens.anim.durations.expressiveFastEffects
            easing: Tokens.anim.standard
        }
        NumberAnimation {
            target: listBox
            property: "x"
            from: Tokens.padding.large
            to: 0
            duration: Tokens.anim.durations.expressiveFastEffects
            easing: Tokens.anim.standard
        }
    }

    readonly property var viewIcons: ({
            clipboard: "content_paste", snippets: "data_object", windows: "web_asset", files: "folder_open", apps: "apps",
            system: "power_settings_new", "calc-history": "calculate", openwith: "apps", "snippet-form": "data_object"
        })

    function focusSearch(): void {
        search.forceActiveFocus();
    }
}
