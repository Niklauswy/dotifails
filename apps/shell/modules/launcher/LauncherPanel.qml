pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import M3Shapes
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
import "services/Translate.js" as Translate

// Raycast-style command palette in Material 3 Expressive: a search pill, category chips with
// a sliding indicator, grouped results, a type-aware preview, an actions popover and a
// push/pop view stack. Result lists are rebuilt from in-memory indexes on every keystroke.
Item {
    id: root

    required property ShellScreen screen
    required property ScreenState state
    required property real reveal

    readonly property real scale: Math.max(0.85, Math.min(1.5, screen.height / 1080))
    readonly property real panelWidth: Math.min(880 * scale, screen.width - Tokens.padding.extraExtraLarge * 2)
    readonly property real panelHeight: Math.min(580 * scale, screen.height - Tokens.padding.extraExtraLarge * 2)
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
            files: [["all", "All Files"], ["image", "Images Only"], ["folder", "Folders Only"]],
            browse: [["all", "All Files"], ["image", "Images Only"], ["folder", "Folders Only"]]
        })
    readonly property var filters: filterOptions[current.id] ?? null
    readonly property string filterLabel: (filters?.find(f => f[0] === filter) ?? ["", ""])[1]
    readonly property alias surface: surface

    property var stack: [{id: "root"}]
    readonly property var current: stack[stack.length - 1]
    property int selected: -1
    property bool autoFirst: true
    property bool actionsOpen
    property bool expandedPreview: false
    readonly property string previewKey: row?.key ?? ""
    onPreviewKeyChanged: expandedPreview = false
    property bool previewFocus
    property bool ctrlHeld
    property string confirmKey
    property string selKey
    property real pointerX: -1
    property real pointerY: -1
    // Bumped on open and on every view change: rows replay their staggered entrance.
    property int entrance

    // Category chips under the search pill; each one is a view (root = everything).
    readonly property var categories: [
        {id: "root", title: "All", icon: "search"}, {id: "apps", title: "Apps", icon: "apps"},
        {id: "files", title: "Files", icon: "folder_open"}, {id: "clipboard", title: "Clipboard", icon: "content_paste"}
    ]
    readonly property int categoryIndex: {
        const id = stack.length > 1 ? stack[1].id : "root";
        return categories.findIndex(c => c.id === (id === "browse" ? "files" : id));
    }
    // Folder browsing: +1 when going deeper (the list slides in from the right), -1 going up.
    property int navDir: 1
    property bool altHeld
    readonly property string browsePath: current.id === "browse" ? current.target : ""
    readonly property string query: search.text

    property var suggestSnapshot: []
    readonly property var results: current.id === "root" ? (query.trim() === "" ? Results.keepOrder(suggestSnapshot, LauncherIndex.context.apps.concat(LauncherIndex.context.commands, LauncherIndex.context.settings)) : Results.root(query, LauncherIndex.context, extrasFor(query.trim()))) : Results.view(current.id, query, LauncherIndex.context, current.target, filter)
    readonly property var items: flatten(results)
    readonly property var row: items[selected] ?? null
    readonly property bool previewOn: !!row && ["file", "clip"].includes(row.kind)
    readonly property bool busy: (LauncherIndex.filesBusy && (current.id === "root" || current.id === "files" || current.id === "browse") && query.trim() !== "") || (current.id === "browse" && LauncherIndex.browseBusy)

    readonly property var placeholders: ({
            root: "Search apps, files, commands...",
            clipboard: "Search clipboard history...",
            files: "Search files and folders...",
            browse: "Filter this folder...",
            apps: "Search applications...",
            "calc-history": "Search calculator history...",
            openwith: "Choose an application..."
        })
    readonly property var titles: ({
            clipboard: "Clipboard History", files: "Files", apps: "Applications",
            "calc-history": "Calculator History", openwith: "Open With"
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
        suggestSnapshot = Results.root("", LauncherIndex.context);
        actionsOpen = false;
        previewFocus = false;
        expandedPreview = false;
        confirmKey = "";
        autoFirst = true;
        LauncherIndex.searchFiles("", "");
        LauncherIndex.refresh();
        LauncherIndex.ensureFileIndex();
        entrance++;
        syncLive();
    }

    function showCategory(id: string): void {
        if (id === (stack.length > 1 ? stack[1].id : "root") && stack.length < 3)
            return;
        if (id === "root") {
            stack = [stack[0], stack[1]];
            pop();
        } else {
            stack = [{id: "root"}];
            push({id: id});
        }
    }

    function cycleCategory(step: int): void {
        const i = (Math.max(0, categoryIndex) + step + categories.length) % categories.length;
        showCategory(categories[i].id);
    }

    // Folder navigation ---------------------------------------------------------------------------
    function enterFolder(path: string): void {
        navDir = 1;
        push({id: "browse", target: path});
    }

    // Up one level: back through the stack when we came from there, otherwise replace in place.
    function upFolder(): void {
        if (current.id !== "browse" || browsePath === "/")
            return;
        const parent = dirname(browsePath);
        const previous = stack[stack.length - 2];
        if (previous?.id === "browse" && previous.target === parent)
            pop();
        else
            goTo(parent, -1);
    }

    // Jump to any folder (breadcrumbs), keeping a single browse level on the stack.
    function goTo(path: string, direction: int): void {
        if (path === browsePath)
            return;
        navDir = direction;
        const base = stack.filter(v => v.id !== "browse");
        filter = "all";
        search.clear();
        stack = base.concat([{id: "browse", target: path}]);
        autoFirst = true;
        LauncherIndex.listDir(path);
        viewAnim.restart();
        entrance++;
        search.forceActiveFocus();
    }

    function push(view: var): void {
        if (view.id !== "browse")
            navDir = 1;
        filter = "all";
        filterOpen = false;
        search.clear();
        stack = stack.concat([view]);
        actionsOpen = false;
        confirmKey = "";
        autoFirst = true;
        LauncherIndex.searchFiles("", "");
        if (view.id === "files") {
            LauncherIndex.loadRecentFiles();
            LauncherIndex.loadPlaces();
        } else if (view.id === "browse")
            LauncherIndex.listDir(view.target);
        else if (view.id === "calc-history")
            LauncherIndex.loadCalcHistory();
        else if (view.id === "clipboard") {
            LauncherIndex.loadStatus();
            LauncherIndex.recognizePending();
        }
        viewAnim.restart();
        entrance++;
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
        LauncherIndex.searchFiles("", "");
        if (current.id === "browse")
            LauncherIndex.listDir(current.target);
        navDir = -1;
        viewAnim.restart();
        entrance++;
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
        // Rows arriving above the selection make the ListView carry its own currentIndex along
        // with the old item while `selected` keeps its number: the purple highlight then sat on a
        // different row than the real selection. Put it back once the model has settled.
        Qt.callLater(resyncHighlight);
        // A fresh view/query starts at the top even when the index did not change (no selected signal).
        if (autoFirst)
            Qt.callLater(scrollToTop);
    }

    // Named so that Qt.callLater folds the many calls of one burst of changes into one.
    function resyncHighlight(): void {
        list.currentIndex = selected;
    }

    function scrollToTop(): void {
        list.positionViewAtBeginning();
    }

    // What a query needs besides the indexes, and nothing more: only the properties read here become
    // dependencies of `results`, so a network answer never re-runs the fuzzy
    // search of an ordinary query.
    function extrasFor(q: string): var {
        const extra = {engine: GlobalConfig.general.apps.searchEngine, seed: entrance};
        switch (q[0]) {
        case ";":
            extra.live = {translation: {state: Translator.state, answered: Translator.answered, variants: Translator.variants, meanings: Translator.meanings}};
            break;
        case "?":
        case "!":
        case ">":
            extra.live = {suggest: {kind: Suggest.kind, query: Suggest.query, items: Suggest.items}};
            break;
        default:
            if (/^kill(\s|$)/i.test(q))
                extra.live = {procs: {query: Suggest.query, items: Suggest.items}};
        }
        return extra;
    }

    // Tells the services what the person is typing after a prefix: ";" translates, "?" and "!" suggest
    // searches, ">" looks through the shell history. They debounce and cache by themselves.
    function syncLive(): void {
        const q = current.id === "root" ? query.trim() : "";
        const rest = q.slice(1).trim();
        if (/^kill(\s|$)/i.test(q)) {
            Translator.clear();
            Suggest.ask("proc", q.slice(4).trim());
            return;
        }
        switch (q[0]) {
        case ";": {
            const t = Translate.splitQuery(q.slice(1));
            if (t.text)
                Translator.ask(t.text, t.target);
            else
                Translator.clear();
            Suggest.clear();
            return;
        }
        case "?":
            Translator.clear();
            Suggest.ask("google", rest);
            return;
        case "!":
            Translator.clear();
            Suggest.ask("youtube", rest);
            return;
        case ">":
            Translator.clear();
            Suggest.ask("run", rest);
            return;
        }
        Translator.clear();
        Suggest.clear();
    }

    function setQuery(text: string): void {
        search.text = text;
        search.cursorPosition = text.length;
        search.forceActiveFocus();
    }

    onItemsChanged: syncSelection()
    onCurrentChanged: syncLive()
    onEntranceChanged: Qt.callLater(scrollToTop)
    onSelectedChanged: {
        if (selected >= 0)
            list.positionViewAtIndex(items[selected - 1]?.header ? selected - 1 : selected, ListView.Contain);
    }
    onQueryChanged: {
        autoFirst = true;
        syncLive();
        Qt.callLater(syncSelection);
        confirmKey = "";
        if (current.id === "root" || current.id === "files" || current.id === "browse")
            filesDebounce.restart();
    }

    // Activation ---------------------------------------------------------------------------------

    // Neovim in a terminal: the whole panel turns into the editor (Editor.qml / EditMorph.qml). A snapshot of the
    // panel is taken first so the morph can start as an exact copy of it; the panel closes under the copy.
    function edit(path: string): void {
        const stage = preview.stage, a = stage.mapToItem(root, 0, 0), b = stage.mapToItem(root, stage.width, stage.height);
        const s = surface.mapToItem(root, 0, 0);
        const styled = preview.nvimStyled;
        const code = Qt.rect(originX + x + a.x, originY + y + a.y, b.x - a.x, b.y - a.y);
        const style = styled ? {html: preview.codeHtml, text: preview.bodyText, fg: preview.codeFg, lineNr: preview.codeLineNr, transparent: preview.codeTransparent, scale: (b.x - a.x) / stage.width} : null;
        const panel = {rect: Qt.rect(originX + x + s.x, originY + y + s.y, surface.width, surface.height), colour: surface.color, radius: surface.radius, snapshot: ""};
        let done = false;
        const go = () => {
            if (done)
                return;
            done = true;
            editFallback.stop();
            Editor.open(screen, code, styled ? preview.codeBg : Colours.palette.m3surface, path, style, panel);
            close();
        };
        // Without a snapshot (the grab failed or is late) the morph starts from the plain panel colour.
        editFallback.run = go;
        editFallback.restart();
        if (!surface.grabToImage(result => {
                panel.snapshot = result.url;
                panel.image = result; // keeps the grab alive while the morph shows it
                go();
            }))
            go();
    }

    Timer {
        id: editFallback

        property var run

        interval: 150
        onTriggered: run?.()
    }

    function xdg(target: string): void {
        Quickshell.execDetached(["xdg-open", target]);
    }

    function copyText(text: string): void {
        Quickshell.execDetached(["wl-copy", "--", text]);
    }

    // Runs a typed command the way the person's own terminal would (their shell, so aliases work)
    // and keeps the window open afterwards: a command that just prints and exits would vanish at once.
    function runInTerminal(command: string): void {
        const script = '"${SHELL:-sh}" -ic "$1"; code=$?; printf "\\n[exit %s]  press Enter to close " "$code"; read -r _';
        Quickshell.execDetached(["wysun-terminal", "-e", "sh", "-c", script, "sh", command]);
    }

    // The browser chosen in Settings > Apps, with the address as its last argument.
    function openUrl(url: string): void {
        Quickshell.execDetached([...GlobalConfig.general.apps.browser, url]);
    }

    function openTranslate(r: var): void {
        openUrl(Translate.openUrl(r.text, r.target));
        close();
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

    function showWindow(address: string): void {
        Quickshell.execDetached(["wysun", "activate", address.startsWith("0x") ? address : "0x" + address]);
    }

    function activate(r: var): void {
        if (!r || r.header)
            return;
        switch (r.kind) {
        case "app": {
            LauncherIndex.remember(r, query);
            // Already open: bring that window forward (workspace switch, leaving a covering fullscreen).
            const open = LauncherIndex.windowOf(r);
            if (open)
                showWindow(open);
            else
                Apps.launch(r);
            close();
            return;
        }
        case "cmd":
            if (r.view) {
                LauncherIndex.remember(r, query);
                push({id: r.view});
                return;
            }
            if (r.emoji) {
                LauncherIndex.remember(r, query);
                close();
                state.emoji = true;
                return;
            }
            if (r.confirm && confirmKey !== r.key) {
                confirmKey = r.key;
                return;
            }
            LauncherIndex.remember(r, query);
            runArgv(r.argv);
            close();
            return;
        case "file":
            if (r.isDir) {
                enterFolder(r.path);
                return;
            }
            LauncherIndex.remember(r, query);
            if (r.editable) {
                edit(r.path); // closes the panel itself, once the morph has taken its place
                return;
            }
            xdg(r.path);
            close();
            return;
        case "variant":
        case "value":
            copyText(r.value);
            close();
            return;
        case "link":
            openUrl(r.url);
            close();
            return;
        case "timer":
            Timers.start(r.seconds, r.label);
            close();
            return;
        case "kill":
            // Closing programs is not undone: the first press asks, the second does it.
            if (confirmKey !== r.key) {
                confirmKey = r.key;
                return;
            }
            Quickshell.execDetached(["pkill", "-x", r.name]);
            close();
            return;
        case "hero":
            return;
        case "translate":
            if (Translator.state === "done") {
                copyText(Translator.result);
                close();
            } else if (Translator.state === "error") {
                openTranslate(r);
            }
            return;
        case "web":
            openUrl(r.url);
            close();
            return;
        case "run":
            runInTerminal(r.command);
            close();
            return;
        case "openwith":
            Quickshell.execDetached(["gtk-launch", r.id, r.target]);
            close();
            return;
        case "clip":
        case "calc":
        case "history":
            LauncherData.copy(r);
            close();
            return;
        }
    }

    function secondaryOf(r: var): var {
        return Actions.actionsFor(r, false, []).find(a => a.shortcut === "Alt ↵") ?? null;
    }

    function desktopActionsOf(r: var): var {
        return r?.kind === "app" ? Array.from(r.entry.actions ?? []) : [];
    }

    function runAction(a: var): void {
        const r = row;
        if (!r || !a)
            return;
        const stay = ["pin", "delete", "capture", "clear", "openwith"].includes(a.id);
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
            case "open-app": LauncherIndex.remember(r, query); xdg(r.path); break;
            case "xdg": LauncherIndex.remember(r, query); xdg(r.path); break;
            case "copy-file": Quickshell.execDetached(["wl-copy", "--type", "text/uri-list", "--", "file://" + r.path + "\r\n"]); break;
            case "copy": LauncherData.copy(r); break;
            case "paste": LauncherData.paste(r); break;
            case "copy-expression": copyText(r.expression); break;
            case "copy-translation": copyText(Translator.result); break;
            case "copy-variant": copyText(r.value); break;
            case "copy-link": copyText(r.url); break;
            case "copy-original": copyText(r.text); break;
            case "open-translate": openTranslate(r); return;
            case "open-link": xdg(r.value.trim()); break;
            case "copy-text": LauncherData.run(["copy-text", String(r.id)]); break;
            case "open-image": LauncherIndex.exportClip(r.id, path => xdg(path)); break;
            case "delete": LauncherIndex.mutate(["delete-clip", String(r.id)]); break;
            case "capture": LauncherIndex.mutate(["toggle-capture"]); break;
            case "clear": LauncherIndex.mutate(["clear-clips"]); break;
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

    function handleKey(e: var): void {
        const ctrl = (e.modifiers & Qt.ControlModifier) !== 0;
        const alt = (e.modifiers & Qt.AltModifier) !== 0;
        e.accepted = true;
        if (e.key === Qt.Key_Control) {
            ctrlHeld = true;
            e.accepted = false;
            return;
        }
        if (e.key === Qt.Key_Alt) {
            altHeld = true;
            e.accepted = false;
            return;
        }
        // Alt+1…4: tabs.
        if ((e.modifiers & Qt.AltModifier) && e.key >= Qt.Key_1 && e.key < Qt.Key_1 + categories.length) {
            showCategory(categories[e.key - Qt.Key_1].id);
            return;
        }
        if (actionsOpen) {
            if (e.key === Qt.Key_Backspace && actionFilter) actionFilter = actionFilter.slice(0, -1);
            else if (!ctrl && !alt && e.text.length === 1 && e.text >= " " && e.key !== Qt.Key_Escape) actionFilter += e.text;
            else if (e.key === Qt.Key_Up) actionMenu.move(-1);
            else if (e.key === Qt.Key_Down) actionMenu.move(1);
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) runAction(actionMenu.actions[actionMenu.current]);
            else if (e.key === Qt.Key_Escape || (alt && e.key === Qt.Key_K)) actionsOpen = false;
            else e.accepted = false;
            return;
        }
        if (alt && e.key === Qt.Key_K) {
            if (row) openActions();
            return;
        }
        if (expandedPreview) {
            if (e.key === Qt.Key_Escape || e.key === Qt.Key_Left) {
                expandedPreview = false;
                previewFocus = false;
                preview.resetZoom();
            } else if (e.key === Qt.Key_Space) preview.togglePlayback();
            else if (e.key === Qt.Key_Plus || e.key === Qt.Key_Equal) preview.zoomBy(1.25);
            else if (e.key === Qt.Key_Minus) preview.zoomBy(0.8);
            else if (e.key === Qt.Key_0) preview.resetZoom();
            return;
        }
        if (e.key === Qt.Key_Right && previewOn && preview.expandable && search.cursorPosition === search.text.length) {
            expandedPreview = true;
            return;
        }
        if (previewFocus) {
            if (e.key === Qt.Key_Up) preview.scrollBy(-60);
            else if (e.key === Qt.Key_Down) preview.scrollBy(60);
            else if (e.key === Qt.Key_PageUp) preview.scrollBy(-240);
            else if (e.key === Qt.Key_PageDown) preview.scrollBy(240);
            else if (e.key === Qt.Key_Plus || e.key === Qt.Key_Equal) preview.zoomBy(1.25);
            else if (e.key === Qt.Key_Minus) preview.zoomBy(0.8);
            else if (e.key === Qt.Key_0) preview.resetZoom();
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
            const second = alt && row ? secondaryOf(row) : null;
            if (second) runAction(second); else activate(row);
        } else if (ctrl && (e.key === Qt.Key_Tab || e.key === Qt.Key_Backtab)) {
            cycleCategory(e.key === Qt.Key_Backtab || (e.modifiers & Qt.ShiftModifier) ? -1 : 1);
        } else if (e.key === Qt.Key_Tab) {
            if (previewOn) previewFocus = true;
        } else if (e.key === Qt.Key_Right && row?.kind === "file" && row.isDir && search.cursorPosition === search.text.length) {
            enterFolder(row.path);
        } else if (e.key === Qt.Key_Left && current.id === "browse" && search.text === "") {
            upFolder();
        } else if (e.key === Qt.Key_Backspace && search.text === "" && stack.length > 1) pop();
        else if (ctrl && e.key === Qt.Key_Space && previewOn) preview.togglePlayback();
        else if (alt && e.key === Qt.Key_K) {
            if (row) openActions();
        } else if (alt && e.key === Qt.Key_Delete) {
            const del = Actions.actionsFor(row, false, []).find(a => a.shortcut === "Alt Del");
            if (del) runAction(del);
        } else if (ctrl && e.key >= Qt.Key_1 && e.key <= Qt.Key_9) {
            const target = items.find(r => r.n === e.key - Qt.Key_1);
            if (target) activate(target);
        } else
            e.accepted = false;
    }

    Timer {
        id: filesDebounce

        interval: 30
        onTriggered: LauncherIndex.searchFiles(root.query, root.current.id === "browse" ? root.current.target : "")
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
        const views = {clip: "clipboard", files: "files", apps: "apps", calc: "calc-history"};
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

    readonly property real rowRadius: Tokens.rounding.large
    readonly property real gutter: Tokens.padding.large

    implicitWidth: panelWidth
    implicitHeight: panelHeight

    // The panel springs in from a little above and slightly small; the overshoot of the
    // reveal curve gives it a soft landing. Shadow and surface move together.
    Item {
        id: stage

        width: root.panelWidth
        height: root.panelHeight
        opacity: Math.min(1, root.reveal * 1.6)
        scale: 0.92 + 0.08 * root.reveal
        transformOrigin: Item.Top
        transform: Translate {
            y: (1 - root.reveal) * -18 * root.scale
        }

        Elevation {
            anchors.fill: surface
            radius: surface.radius
            level: 4
        }

    // Solid Material surface, like the dashboard and the other drawers.
    Rectangle {
        id: surface

        anchors.fill: parent
        radius: Tokens.rounding.extraLarge
        color: Colours.palette.m3surfaceContainer
        clip: true

        // Header: search pill -------------------------------------------------------------------
        Item {
            id: head

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: root.gutter
            height: 56 * root.scale

            Rectangle {
                id: pill

                anchors.fill: parent
                radius: height / 2
                color: Colours.palette.m3surfaceContainerHighest
                border.width: search.activeFocus && !root.actionsOpen ? 2 : 0
                border.color: Colours.palette.m3primary

                Behavior on border.width {
                    Anim {
                        type: Anim.FastEffects
                    }
                }
            }

            // Leading shape: a cookie with the search glyph at the root, a circle with an arrow
            // inside a category. The polygon morphs between the two.
            Item {
                id: lead

                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.small
                anchors.verticalCenter: parent.verticalCenter
                width: 40 * root.scale
                height: width

                MaterialShape {
                    anchors.centerIn: parent
                    implicitSize: parent.width
                    shape: root.stack.length > 1 ? MaterialShape.Circle : MaterialShape.Cookie9Sided
                    color: root.stack.length > 1 ? Colours.palette.m3secondaryContainer : Colours.palette.m3primaryContainer
                    animationEasing: Tokens.anim.expressiveDefaultSpatial
                    animationDuration: Tokens.anim.durations.expressiveDefaultSpatial
                    rotation: root.stack.length > 1 ? 0 : -20 + 20 * root.reveal

                    Behavior on color {
                        CAnim {}
                    }
                }
                MaterialIcon {
                    anchors.centerIn: parent
                    text: root.stack.length > 1 ? "arrow_back" : "search"
                    color: root.stack.length > 1 ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onPrimaryContainer
                    fontStyle: Tokens.font.icon.builders.medium.scale(root.scale).build()
                    animate: true
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
                anchors.leftMargin: Tokens.spacing.medium
                anchors.right: trailing.left
                anchors.rightMargin: Tokens.spacing.medium
                anchors.verticalCenter: parent.verticalCenter
                background: null
                leftPadding: 0
                rightPadding: 0
                font: Tokens.font.body.builders.large.size(13.5 * root.scale).build()
                focus: true
                placeholderText: ""
                onTextChanged: root.previewFocus = false
                Keys.onPressed: event => root.handleKey(event)
                Keys.onReleased: event => {
                    if (event.key === Qt.Key_Control)
                        root.ctrlHeld = false;
                    if (event.key === Qt.Key_Alt)
                        root.altHeld = false;
                }

                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: search.text === ""
                    text: root.placeholders[root.current.id] ?? ""
                    font: search.font
                    color: Colours.palette.m3onSurfaceVariant
                }
            }

            Row {
                id: trailing

                anchors.right: parent.right
                anchors.rightMargin: Tokens.padding.small
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.spacing.small

                LoadingIndicator {
                    anchors.verticalCenter: parent.verticalCenter
                    implicitSize: 26 * root.scale
                    visible: root.busy
                }

                // Compact filter (clipboard, files): a tonal chip that opens a small menu.
                Rectangle {
                    id: filterBox

                    anchors.verticalCenter: parent.verticalCenter
                    visible: !!root.filters
                    width: filterRow.implicitWidth + Tokens.padding.large * 1.5
                    height: 36 * root.scale
                    radius: height / 2
                    color: root.filterOpen ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh

                    Behavior on color {
                        CAnim {}
                    }

                    Row {
                        id: filterRow

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.small

                        MaterialIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "filter_list"
                            fontStyle: Tokens.font.icon.small
                            color: Colours.palette.m3onSecondaryContainer
                        }
                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.filterLabel
                            font: root.fontStrong
                            color: Colours.palette.m3onSecondaryContainer
                        }
                    }
                    StateLayer {
                        radius: filterBox.radius
                        color: Colours.palette.m3onSecondaryContainer
                        onClicked: root.filterOpen = !root.filterOpen
                    }
                }
            }
        }

        // Category chips with a sliding indicator ------------------------------------------------
        Item {
            id: chips

            anchors.top: head.bottom
            anchors.topMargin: Tokens.spacing.medium
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: root.gutter
            anchors.rightMargin: root.gutter
            height: 34 * root.scale

            // Re-evaluated when the chips exist and when their row is laid out.
            readonly property Item currentChip: chipRow.width > 0 && chipRepeater.count > 0 ? chipRepeater.itemAt(root.categoryIndex) : null

            Rectangle {
                id: indicator

                x: chips.currentChip?.x ?? 0
                y: 0
                width: chips.currentChip?.width ?? 0
                height: parent.height
                radius: height / 2
                color: Colours.palette.m3secondaryContainer
                opacity: root.categoryIndex >= 0 ? 1 : 0

                Behavior on x {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
                Behavior on width {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
                Behavior on opacity {
                    Anim {
                        type: Anim.FastEffects
                    }
                }
            }

            Row {
                id: chipRow

                height: parent.height
                spacing: Tokens.spacing.extraSmall

                Repeater {
                    id: chipRepeater

                    model: root.categories

                    Item {
                        id: chip

                        required property var modelData
                        required property int index
                        readonly property bool on: root.categoryIndex === index

                        width: chipLabel.implicitWidth + chipIcon.width + Tokens.spacing.small + Tokens.padding.large * 1.4
                        height: chipRow.height

                        Row {
                            anchors.centerIn: parent
                            spacing: Tokens.spacing.small

                            MaterialIcon {
                                id: chipIcon

                                anchors.verticalCenter: parent.verticalCenter
                                text: chip.modelData.icon
                                fill: chip.on ? 1 : 0
                                color: chip.on ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                                fontStyle: Tokens.font.icon.builders.small.scale(root.scale).build()
                            }
                            StyledText {
                                id: chipLabel

                                anchors.verticalCenter: parent.verticalCenter
                                text: chip.modelData.title
                                font: root.fontStrong
                                color: chip.on ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                            }
                        }
                        StateLayer {
                            radius: chip.height / 2
                            color: Colours.palette.m3onSurface
                            onClicked: root.showCategory(chip.modelData.id)
                        }
                        // Alt held: each tab shows the number that selects it.
                        Rectangle {
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: -2
                            width: height
                            height: 18 * root.scale
                            radius: height / 2
                            color: Colours.palette.m3primary
                            scale: root.altHeld ? 1 : 0
                            opacity: scale

                            Behavior on scale {
                                Anim {
                                    type: Anim.FastSpatial
                                }
                            }

                            StyledText {
                                anchors.centerIn: parent
                                text: chip.index + 1
                                font: root.fontStrong
                                color: Colours.palette.m3onPrimary
                            }
                        }
                    }
                }
            }

            Keycaps {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: chipRow.width + width + Tokens.spacing.large < parent.width
                keys: ["Alt", "1–" + root.categories.length]
                opacity: 0.8
            }
        }

        // Body ------------------------------------------------------------------------------------
        Item {
            id: body

            anchors.top: chips.bottom
            anchors.topMargin: Tokens.spacing.medium
            anchors.bottom: foot.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: root.gutter - Tokens.padding.small
            anchors.rightMargin: root.gutter

            property real listWidth: root.expandedPreview ? 0 : root.previewOn ? width * 0.42 : width

            Behavior on listWidth {
                Anim {
                    type: Anim.DefaultSpatial
                }
            }

            // Breadcrumbs while browsing a folder: each step is a chip; the current one is filled.
            Item {
                id: crumbs

                width: body.listWidth
                height: root.current.id === "browse" ? 40 * root.scale : 0
                visible: height > 0 && !root.expandedPreview
                clip: true

                readonly property var steps: {
                    const path = root.browsePath, home = LauncherIndex.home;
                    if (!path)
                        return [];
                    const inHome = path === home || path.startsWith(home + "/");
                    const rest = (inHome ? path.slice(home.length) : path).split("/").filter(Boolean);
                    const out = [{title: inHome ? "Home" : "/", path: inHome ? home : "/", icon: inHome ? "home" : "storage"}];
                    let acc = inHome ? home : "";
                    for (const part of rest) {
                        acc += "/" + part;
                        out.push({title: part, path: acc, icon: ""});
                    }
                    return out;
                }

                Behavior on height {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }

                ListView {
                    id: crumbList

                    anchors.fill: parent
                    anchors.leftMargin: Tokens.padding.small
                    anchors.bottomMargin: Tokens.spacing.small
                    orientation: ListView.Horizontal
                    spacing: Tokens.spacing.extraSmall
                    boundsBehavior: Flickable.StopAtBounds
                    model: crumbs.steps
                    onCountChanged: Qt.callLater(() => crumbList.positionViewAtEnd())

                    delegate: Row {
                        id: crumb

                        required property var modelData
                        required property int index
                        readonly property bool last: index === crumbs.steps.length - 1

                        height: crumbList.height
                        spacing: Tokens.spacing.extraSmall

                        MaterialIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            visible: crumb.index > 0
                            text: "chevron_right"
                            color: Colours.palette.m3outline
                            fontStyle: Tokens.font.icon.small
                        }
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: crumbRow.implicitWidth + Tokens.padding.medium * 1.6
                            height: 30 * root.scale
                            radius: height / 2
                            color: crumb.last ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh

                            Row {
                                id: crumbRow

                                anchors.centerIn: parent
                                spacing: Tokens.spacing.extraSmall

                                MaterialIcon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: crumb.modelData.icon !== ""
                                    text: crumb.modelData.icon
                                    fill: crumb.last ? 1 : 0
                                    color: crumb.last ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                                    fontStyle: Tokens.font.icon.small
                                }
                                StyledText {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: crumb.modelData.title
                                    font: root.fontStrong
                                    color: crumb.last ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                                }
                            }
                            StateLayer {
                                radius: parent.radius
                                color: Colours.palette.m3onSurface
                                disabled: crumb.last
                                onClicked: root.goTo(crumb.modelData.path, -1)
                            }
                        }
                    }
                }
            }

            Item {
                id: listBox

                visible: !root.expandedPreview

                y: crumbs.height
                width: body.listWidth
                height: parent.height - crumbs.height

                ListView {
                    id: list

                    anchors.fill: parent
                    anchors.leftMargin: Tokens.padding.small
                    anchors.rightMargin: Tokens.padding.small
                    clip: true
                    reuseItems: true
                    cacheBuffer: 400
                    boundsBehavior: Flickable.StopAtBounds
                    objectName: "launcherResults"
                    highlightFollowsCurrentItem: true
                    highlightMoveVelocity: -1
                    highlightResizeVelocity: -1
                    highlightMoveDuration: Tokens.anim.durations.expressiveFastEffects
                    highlightResizeDuration: Tokens.anim.durations.expressiveFastEffects
                    model: ScriptModel {
                        values: root.items
                        objectProp: "key"
                    }
                    delegate: ResultRow {
                        panel: root
                    }

                    // A Binding, not `currentIndex: root.selected`: syncSelection() also assigns
                    // currentIndex by hand after the model settles, and an assignment would
                    // destroy a plain binding, leaving the highlight stuck on one row.
                    Binding {
                        target: list
                        property: "currentIndex"
                        value: root.selected
                    }

                    // Let ListView own highlight coordinates and delegate lifecycle. A separate
                    // rectangle uses viewport coordinates and drifts when contentY changes.
                    // Shape morph on move (Material 3 Expressive): the container stretches toward a
                    // pill while it travels and settles back on its resting corners.
                    highlight: Rectangle {
                        id: marker

                        property real stretch

                        radius: root.rowRadius + stretch
                        color: Colours.palette.m3secondaryContainer
                        visible: root.selected >= 0 && !root.items[root.selected]?.header

                        Behavior on color {
                            CAnim {}
                        }

                        SequentialAnimation {
                            id: morph

                            Anim {
                                target: marker
                                property: "stretch"
                                to: 14 * root.scale
                                type: Anim.FastSpatial
                            }
                            Anim {
                                target: marker
                                property: "stretch"
                                to: 0
                                type: Anim.DefaultSpatial
                            }
                        }

                        Connections {
                            target: root

                            function onSelectedChanged(): void {
                                morph.restart();
                            }
                        }
                    }
                }


                // Empty state: a soft shape with the view's glyph and a sentence.
                Column {
                    anchors.centerIn: parent
                    width: parent.width - Tokens.padding.extraLarge * 2
                    spacing: Tokens.spacing.large
                    visible: root.items.length === 0 && !root.busy

                    MaterialShape {
                        anchors.horizontalCenter: parent.horizontalCenter
                        implicitSize: 72 * root.scale
                        shape: MaterialShape.Cookie7Sided
                        color: Colours.palette.m3surfaceContainerHighest

                        MaterialIcon {
                            anchors.centerIn: parent
                            text: root.viewIcons[root.current.id] ?? "search_off"
                            color: Colours.palette.m3onSurfaceVariant
                            fontStyle: Tokens.font.icon.builders.large.scale(root.scale).build()
                        }
                    }
                    StyledText {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: Results.emptyText(root.current.id, root.query)
                        font: root.fontBody
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }

            PreviewPane {
                id: preview

                x: body.listWidth + (root.expandedPreview ? 0 : Tokens.spacing.medium)
                width: body.width - x
                height: parent.height - Tokens.padding.small
                opacity: root.previewOn ? 1 : 0
                visible: opacity > 0.01
                scale: root.scale
                row: root.previewOn ? root.row : null
                focusedPane: root.previewFocus
                expanded: root.expandedPreview
                onExpandRequested: root.expandedPreview = true
                onCollapseRequested: { root.expandedPreview = false; root.previewFocus = false; resetZoom(); }
                decodeSize: Qt.size(root.panelWidth * 2, root.panelHeight * 2)

                transform: Translate {
                    x: (1 - preview.opacity) * 24 * root.scale
                }

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }
        }

        // Footer: context on the left, primary action and the actions menu on the right ------------
        Item {
            id: foot

            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: root.gutter
            anchors.rightMargin: root.gutter - Tokens.padding.small
            height: 56 * root.scale

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.spacing.medium

                readonly property bool appIcon: !!root.row && root.stack.length === 1 && root.row.kind === "app"
                readonly property bool brandIcon: !!root.row && root.stack.length === 1 && !!root.row.brand

                Item {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30 * root.scale
                    height: width

                    MaterialShape {
                        anchors.centerIn: parent
                        implicitSize: parent.width
                        visible: !parent.parent.appIcon
                        shape: MaterialShape.Cookie4Sided
                        color: Colours.palette.m3tertiaryContainer
                    }
                    Image {
                        anchors.centerIn: parent
                        width: parent.width * 0.6
                        height: width
                        visible: parent.parent.brandIcon
                        source: visible ? Quickshell.shellPath(`assets/brands/${root.row.brand}.svg`) : ""
                        sourceSize: Qt.size(96, 96)
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }
                    MaterialIcon {
                        anchors.centerIn: parent
                        visible: !parent.parent.appIcon && !parent.parent.brandIcon
                        text: root.stack.length > 1 ? root.viewIcons[root.current.id] ?? "bolt" : root.row ? root.row.icon || "bolt" : "bolt"
                        color: Colours.palette.m3onTertiaryContainer
                        fontStyle: Tokens.font.icon.builders.small.scale(root.scale).build()
                    }
                    AppIcon {
                        anchors.fill: parent
                        visible: parent.parent.appIcon
                        name: visible ? root.row.icon : ""
                        size: parent.width
                    }
                }
                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.current.id === "browse" ? root.browsePath.replace(LauncherIndex.home, "~") : root.stack.length > 1 ? root.titles[root.current.id] ?? "" : root.row ? root.row.title : "Wysun"
                    font: root.fontStrong
                    color: Colours.palette.m3onSurfaceVariant
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, root.panelWidth * (root.current.id === "browse" ? 0.25 : 0.4))
                }
                // Folder navigation hints: arrows move through the tree.
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Tokens.spacing.small
                    visible: root.current.id === "browse" || (root.row?.kind === "file" && root.row.isDir)

                    Keycaps {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.current.id === "browse"
                        keys: ["←"]
                    }
                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.current.id === "browse"
                        text: "Up"
                        font: root.fontSmall
                        color: Colours.palette.m3onSurfaceVariant
                    }
                    Keycaps {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.row?.kind === "file" && root.row.isDir
                        keys: ["→"]
                    }
                    StyledText {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.row?.kind === "file" && root.row.isDir
                        text: "Open folder"
                        font: root.fontSmall
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.spacing.small

                // Primary action: filled tonal pill.
                Rectangle {
                    id: primary

                    anchors.verticalCenter: parent.verticalCenter
                    width: primaryRow.implicitWidth + Tokens.padding.large * 1.6
                    height: 38 * root.scale
                    radius: height / 2
                    color: Colours.palette.m3primary
                    opacity: root.row ? 1 : 0.5

                    Row {
                        id: primaryRow

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.small

                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Actions.primaryLabel(root.row)
                            font: root.fontStrong
                            color: Colours.palette.m3onPrimary
                        }
                        Keycaps {
                            anchors.verticalCenter: parent.verticalCenter
                            keys: ["↵"]
                            onPrimary: true
                        }
                    }
                    StateLayer {
                        radius: primary.radius
                        color: Colours.palette.m3onPrimary
                        onClicked: root.activate(root.row)
                    }
                }

                Rectangle {
                    id: actionsButton

                    anchors.verticalCenter: parent.verticalCenter
                    width: actionsHint.implicitWidth + Tokens.padding.large * 1.6
                    height: 38 * root.scale
                    radius: root.actionsOpen ? Tokens.rounding.medium : height / 2
                    color: root.actionsOpen ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHighest

                    Behavior on radius {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }
                    Behavior on color {
                        CAnim {}
                    }

                    Row {
                        id: actionsHint

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.small

                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Actions"
                            font: root.fontStrong
                            color: Colours.palette.m3onSurface
                        }
                        Keycaps {
                            anchors.verticalCenter: parent.verticalCenter
                            keys: ["Alt", "K"]
                        }
                    }
                    StateLayer {
                        radius: actionsButton.radius
                        color: Colours.palette.m3onSurface
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

        // Filter menu (clipboard, files)
        Rectangle {
            id: filterMenu

            readonly property bool shown: root.filterOpen && !!root.filters

            anchors.right: parent.right
            anchors.rightMargin: root.gutter
            anchors.top: head.bottom
            anchors.topMargin: Tokens.spacing.small
            width: 200 * root.scale
            height: filterList.implicitHeight + Tokens.padding.small * 2
            radius: Tokens.rounding.large
            color: Colours.palette.m3surfaceContainerHigh
            z: 5
            visible: opacity > 0.01
            opacity: shown ? 1 : 0
            scale: shown ? 1 : 0.9
            transformOrigin: Item.TopRight

            Behavior on opacity {
                Anim {
                    type: Anim.FastEffects
                }
            }
            Behavior on scale {
                Anim {
                    type: Anim.FastSpatial
                }
            }

            Elevation {
                anchors.fill: parent
                radius: parent.radius
                level: 2
                z: -1
            }

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
                        height: 36 * root.scale
                        radius: height / 2
                        color: root.filter === opt.modelData[0] ? Colours.palette.m3secondaryContainer : "transparent"

                        StyledText {
                            anchors.left: parent.left
                            anchors.leftMargin: Tokens.padding.medium
                            anchors.verticalCenter: parent.verticalCenter
                            text: opt.modelData[1]
                            font: root.fontStrong
                        }
                        MaterialIcon {
                            anchors.right: parent.right
                            anchors.rightMargin: Tokens.padding.medium
                            anchors.verticalCenter: parent.verticalCenter
                            visible: root.filter === opt.modelData[0]
                            text: "check"
                            fontStyle: Tokens.font.icon.small
                        }
                        StateLayer {
                            radius: opt.radius
                            color: Colours.palette.m3onSurface
                            onClicked: {
                                root.filter = opt.modelData[0];
                                root.filterOpen = false;
                                root.autoFirst = true;
                                root.entrance++;
                                search.forceActiveFocus();
                            }
                        }
                    }
                }
            }
        }

        // Actions popover: grows out of the Actions button.
        ActionsMenu {
            id: actionMenu

            anchors.right: parent.right
            anchors.rightMargin: root.gutter - Tokens.padding.small
            anchors.bottom: foot.top
            anchors.bottomMargin: Tokens.padding.extraSmall
            scale: root.scale
            source: Actions.actionsFor(root.row, root.row ? LauncherIndex.isPinned(root.row) : false, root.desktopActionsOf(root.row))
            filterText: root.actionFilter
            open: root.actionsOpen
            onTriggered: a => root.runAction(a)
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
    }

    // View change: the list slides in a few pixels while fading; rows add their own stagger.
    ParallelAnimation {
        id: viewAnim

        NumberAnimation {
            target: listBox
            property: "opacity"
            from: 0
            to: 1
            duration: Tokens.anim.durations.expressiveDefaultEffects
            easing: Tokens.anim.expressiveDefaultEffects
        }
        NumberAnimation {
            target: listBox
            property: "x"
            from: Tokens.padding.extraLarge * 1.6 * root.navDir
            to: 0
            duration: Tokens.anim.durations.expressiveDefaultSpatial
            easing: Tokens.anim.expressiveDefaultSpatial
        }
    }

    readonly property var viewIcons: ({
            root: "search_off", clipboard: "content_paste", files: "folder_open", apps: "apps",
            "calc-history": "calculate", openwith: "apps", browse: "folder_open"
        })

    function focusSearch(): void {
        search.forceActiveFocus();
    }
}
