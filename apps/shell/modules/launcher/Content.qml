pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Wysun.I18n
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.launcher.services
import "services/Catalog.js" as Catalog

Item {
    id: root
    required property ScreenState screenState
    required property var panels
    required property real maxHeight
    property real maxWidth: Tokens.sizes.launcher.itemWidth * 1.6
    property string category: "all"
    property int snippetId: -1
    property bool editingSnippet: false
    property bool confirmClear: false
    property string clipFilter: ""
    readonly property var categories: Catalog.categories()
    readonly property var selected: results.currentItem?.modelData ?? null
    readonly property bool copyable: selected && ["clip", "snippet", "calc"].includes(selected.kind)
    readonly property string heading: categories.find(c => c.id === category)?.title ?? "Discover"
    readonly property var resultRows: buildRows()
    implicitWidth: Math.min(maxWidth, Tokens.sizes.launcher.itemWidth * 1.6)
    implicitHeight: Math.min(maxHeight, Tokens.sizes.launcher.itemHeight * 10 + Tokens.padding.extraLarge * 3)

    function choose(mode: string): void {
        category = mode;
        editingSnippet = false;
        confirmClear = false;
        clipFilter = "";
        search.clear();
        search.forceActiveFocus();
        source.refresh();
    }
    function buildRows(): var {
        const q = search.text.trim();
        let rows = [];
        if (category === "all" || category === "apps") {
            const apps = Apps.search(q).filter(Boolean).slice(0, category === "all" ? (q ? GlobalConfig.launcher.maxShown : Math.min(5, GlobalConfig.launcher.maxShown)) : 100);
            rows = apps.map(app => ({kind: "app", title: app.name, subtitle: app.comment || app.genericName || "Application", app: app, icon: app.icon, section: q ? "Applications" : "Your applications"}));
        }
        if (category === "all" || category === "commands") {
            let actions = Catalog.actions(q, Array.from(GlobalConfig.launcher.actions.values).map(a => ({name: Tr.trMarked(a.name), description: Tr.trMarked(a.description), icon: a.icon, command: a.command, enabled: a.enabled, dangerous: a.dangerous})), GlobalConfig.launcher.enableDangerousActions);
            if (category === "all" && !q) actions = actions.slice(0, 3);
            rows = rows.concat(actions);
            if (q) rows.push(Object.assign(LauncherData.runRow(q), {section: "Command", title: "Run in terminal"}));
        }
        if (category !== "apps" && category !== "commands") {
            const data = source.rows.map(r => Object.assign({}, r, {section: r.section || (category === "files" && !q ? "Recent files" : heading)}));
            // Arithmetic and conversions get the first result without switching modes.
            rows = data.filter(r => r.kind === "calc" && q).concat(rows, data.filter(r => r.kind !== "calc" || !q));
        }
        if (q && category === "all") rows.push(Object.assign(LauncherData.webRow(q), {section: "Web", title: "Search DuckDuckGo"}));
        return rows;
    }
    function activate(row: var): void {
        if (!row || ["hint", "error"].includes(row.kind)) return;
        if (row.kind === "app") Apps.launch(row.app);
        else if (row.kind === "action") {
            if (row.argv[0] === "autocomplete") {
                const modes = {clip: "clip", snip: "snippets", snippets: "snippets", calc: "calc", hist: "calc", win: "windows", windows: "windows", files: "files", run: "commands"};
                if (row.argv[1] === "emoji") { screenState.launcher = false; screenState.emoji = true; return; }
                if (modes[row.argv[1]]) { choose(modes[row.argv[1]]); return; }
                Quickshell.execDetached(["wysun", "settings", "wallpaper"]);
            } else if (row.argv[0] === "setMode") Colours.setMode(row.argv[1]);
            else if (!SessionManager.exec(row.argv)) Quickshell.execDetached(row.argv);
        }
        else if (!LauncherData.activate(row)) return;
        screenState.launcher = false;
    }
    function removeSelected(): void {
        if (!selected || !["clip", "snippet"].includes(selected.kind)) return;
        historyAction.command = ["python3", "-I", LauncherData.script, "act", selected.kind === "clip" ? "delete-clip" : "delete-snippet", String(selected.id)];
        historyAction.running = true;
    }
    function adoptRoute(): void {
        if (screenState.launcherCategory) {
            choose(screenState.launcherCategory);
            screenState.launcherCategory = "";
        }
        if (screenState.launcherQuery) {
            search.text = screenState.launcherQuery;
            screenState.launcherQuery = "";
        }
    }

    DataSource {
        id: source
        mode: root.category
        query: (root.category === "clip" && root.clipFilter ? root.clipFilter + " " : "") + search.text
        enabled: root.screenState.launcher && root.category !== "apps" && root.category !== "commands"
    }
    DataSource { id: captureStatus; mode: "status"; enabled: root.screenState.launcher && root.category === "clip" }
    FilePreview { id: preview; path: root.selected?.kind === "file" ? root.selected.path : ""; clipId: root.selected?.kind === "clip" && root.selected.clip_kind === "image" ? root.selected.id : -1 }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.large

        RowLayout {
            spacing: Tokens.spacing.medium
            MaterialIcon { text: "search"; color: Colours.palette.m3primary; fontStyle: Tokens.font.icon.large }
            StyledText { text: "Wysun"; font: Tokens.font.title.medium }
            StyledText { text: "Find it. Open it. Get going."; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.body.small; Layout.fillWidth: true }
            StyledText { text: "Super + D"; color: Colours.palette.m3outline; font: Tokens.font.label.small }
            IconButton { icon: "close"; type: IconButton.Text; onClicked: root.screenState.launcher = false }
        }
        SearchBar {
            id: search
            objectName: "launcherSearch"
            Layout.fillWidth: true
            font: Tokens.font.body.large
            placeholderText: root.category === "calc" ? "Try 15% of 80 or 10 km to mi" : root.category === "commands" ? "Find an action or type a terminal command" : "Search apps, files, actions or calculate…"
            onAccepted: root.activate(root.selected)
            Keys.onUpPressed: results.decrementCurrentIndex()
            Keys.onDownPressed: results.incrementCurrentIndex()
            Keys.onEscapePressed: { if (root.editingSnippet) root.editingSnippet = false; else root.screenState.launcher = false; }
            Keys.onPressed: event => {
                if ((event.modifiers & Qt.AltModifier) && event.key >= Qt.Key_1 && event.key <= Qt.Key_8) {
                    root.choose(root.categories[event.key - Qt.Key_1].id); event.accepted = true;
                } else if (GlobalConfig.launcher.vimKeybinds && (event.modifiers & Qt.ControlModifier) && [Qt.Key_J, Qt.Key_N, Qt.Key_K, Qt.Key_P].includes(event.key)) {
                    if ([Qt.Key_J, Qt.Key_N].includes(event.key)) results.incrementCurrentIndex(); else results.decrementCurrentIndex();
                    event.accepted = true;
                } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                    const index = root.categories.findIndex(c => c.id === root.category);
                    root.choose(root.categories[(index + ((event.modifiers & Qt.ShiftModifier) || event.key === Qt.Key_Backtab ? 7 : 1)) % 8].id);
                    event.accepted = true;
                } else if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Delete) {
                    root.removeSelected(); event.accepted = true;
                } else if (root.selected && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
                    if ((event.modifiers & Qt.ShiftModifier) && LauncherData.openFolder(root.selected)) {
                        root.screenState.launcher = false; event.accepted = true;
                    } else if ((event.modifiers & Qt.ControlModifier) && (LauncherData.paste(root.selected) || LauncherData.copyPath(root.selected))) {
                        root.screenState.launcher = false; event.accepted = true;
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Tokens.spacing.large
            ColumnLayout {
                Layout.minimumWidth: Tokens.sizes.launcher.itemWidth / 4
                Layout.maximumWidth: Tokens.sizes.launcher.itemWidth / 4
                Layout.preferredWidth: Tokens.sizes.launcher.itemWidth / 4
                Layout.alignment: Qt.AlignTop
                spacing: Tokens.spacing.extraSmall
                Repeater {
                    model: root.categories
                    delegate: Rectangle {
                        id: nav
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        implicitHeight: Tokens.sizes.launcher.itemHeight * 0.72
                        radius: Tokens.rounding.medium
                        color: root.category === modelData.id ? Colours.palette.m3secondaryContainer : "transparent"
                        StateLayer { radius: nav.radius; onClicked: root.choose(nav.modelData.id) }
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Tokens.padding.small
                            spacing: Tokens.spacing.small
                            MaterialIcon { text: nav.modelData.icon; fontStyle: Tokens.font.icon.small; color: root.category === nav.modelData.id ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant }
                            StyledText { text: nav.modelData.title; font: Tokens.font.label.medium; color: root.category === nav.modelData.id ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface; Layout.fillWidth: true }
                        }
                    }
                }
                Item { Layout.fillHeight: true }
                StyledText { text: "Tab to explore\nAlt + 1–8 to jump"; font: Tokens.font.label.small; color: Colours.palette.m3outline; lineHeight: 1.5 }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Tokens.spacing.small
                RowLayout {
                    Layout.fillWidth: true
                    StyledText { text: root.heading; font: Tokens.font.title.small; Layout.fillWidth: true }
                    StyledText { text: source.loading ? "Searching…" : results.count + " results"; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
                }
                RowLayout {
                    visible: root.category === "clip"
                    spacing: Tokens.spacing.extraSmall
                    Repeater {
                        model: ["All", "Text", "Image", "Color", "URL"]
                        delegate: TextButton {
                            required property string modelData
                            text: modelData
                            type: TextButton.Text
                            checked: root.clipFilter === (modelData === "All" ? "" : modelData.toLowerCase())
                            onClicked: { root.clipFilter = modelData === "All" ? "" : modelData.toLowerCase(); search.forceActiveFocus(); }
                        }
                    }
                }
                ListView {
                    id: results
                    objectName: "launcherResults"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Tokens.spacing.extraSmall
                    model: ScriptModel { values: root.resultRows; onValuesChanged: { results.currentIndex = 0; results.positionViewAtBeginning(); } }
                    delegate: Item {
                        id: result
                        required property var modelData
                        required property int index
                        readonly property bool selected: ListView.isCurrentItem
                        readonly property bool showSection: index === 0 || root.resultRows[index - 1]?.section !== modelData.section
                        width: results.width
                        implicitHeight: Tokens.sizes.launcher.itemHeight + (showSection ? sectionLabel.implicitHeight + Tokens.spacing.small : 0)
                        StyledText {
                            id: sectionLabel
                            visible: result.showSection
                            text: result.modelData.section
                            font: Tokens.font.label.small
                            color: Colours.palette.m3onSurfaceVariant
                            topPadding: Tokens.padding.small
                            bottomPadding: Tokens.padding.extraSmall
                        }
                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: Tokens.sizes.launcher.itemHeight
                            radius: Tokens.rounding.medium
                            color: result.selected ? Colours.palette.m3secondaryContainer : "transparent"
                            StateLayer {
                                radius: Tokens.rounding.medium
                                onContainsMouseChanged: { if (containsMouse) results.currentIndex = result.index; }
                                onClicked: root.activate(result.modelData)
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Tokens.padding.small
                                spacing: Tokens.spacing.medium
                                AppIcon { visible: result.modelData.kind === "app"; name: result.modelData.icon || ""; size: Tokens.spacing.extraLarge }
                                MaterialIcon { visible: result.modelData.kind !== "app"; text: result.modelData.icon || "draft"; fontStyle: Tokens.font.icon.large; color: Colours.palette.m3primary }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: Tokens.spacing.extraSmall / 2
                                    StyledText { text: result.modelData.title; font: Tokens.font.body.medium; elide: Text.ElideRight; Layout.fillWidth: true }
                                    StyledText { text: result.modelData.subtitle || ""; font: Tokens.font.body.small; color: Colours.palette.m3onSurfaceVariant; elide: Text.ElideRight; Layout.fillWidth: true }
                                }
                                MaterialIcon { visible: result.selected; text: ["clip", "snippet", "calc"].includes(result.modelData.kind) ? "content_copy" : "subdirectory_arrow_left"; fontStyle: Tokens.font.icon.small; color: Colours.palette.m3onSecondaryContainer }
                            }
                        }
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
                StyledText {
                    visible: !results.count
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    text: source.loading ? "Searching your desktop…" : root.category === "calc" ? "A little space to think.\n\n24 × 8 / 16\n15% of 80\n10 km to mi\n\nPast calculations appear here." : root.category === "snippets" ? "Your words, a shortcut away.\nCreate a snippet to get started." : root.category === "clip" ? "Your next copy starts the history.\nText, images, colours and links." : "No results yet.\nTry another search or category."
                    font: Tokens.font.body.medium
                    color: Colours.palette.m3onSurfaceVariant
                }
            }

            Rectangle {
                Layout.minimumWidth: Tokens.sizes.launcher.itemWidth * 0.4
                Layout.maximumWidth: Tokens.sizes.launcher.itemWidth * 0.4
                Layout.preferredWidth: Tokens.sizes.launcher.itemWidth * 0.4
                Layout.fillHeight: true
                visible: root.editingSnippet || root.width >= Tokens.sizes.launcher.itemWidth * 1.3
                radius: Tokens.rounding.large
                color: Colours.tPalette.m3surfaceContainer
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.medium
                    visible: !root.editingSnippet
                    StyledText { text: root.selected?.section || root.heading; font: Tokens.font.label.small; color: Colours.palette.m3primary; Layout.fillWidth: true; elide: Text.ElideRight }
                    AppIcon { visible: root.selected?.kind === "app"; name: root.selected?.icon || ""; size: Tokens.spacing.extraLarge * 2; Layout.alignment: Qt.AlignHCenter }
                    MaterialIcon { visible: root.selected?.kind !== "app"; text: root.selected?.icon || "auto_awesome"; fontStyle: Tokens.font.icon.builders.extraLarge.scale(1.5).build(); color: Colours.palette.m3primary; Layout.alignment: Qt.AlignHCenter }
                    StyledText { text: root.selected?.title || "Make room for your next idea."; font: root.selected?.kind === "calc" ? Tokens.font.headline.medium : Tokens.font.title.medium; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; maximumLineCount: 3; elide: Text.ElideRight }
                    StyledText { text: root.selected?.subtitle || "Apps, recent files, calculations and desktop actions in one place."; font: Tokens.font.body.small; color: Colours.palette.m3onSurfaceVariant; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; maximumLineCount: 3; elide: Text.ElideRight }
                    Image {
                        visible: !!preview.data.image
                        Layout.fillWidth: true
                        Layout.preferredHeight: Tokens.sizes.launcher.itemHeight * 2
                        source: preview.data.image || ""
                        sourceSize.width: Tokens.sizes.launcher.itemWidth
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        StyledText {
                            width: parent.width
                            text: root.selected?.kind === "file" ? preview.data.text || "" : root.copyable ? root.selected.value || "" : root.selected?.kind === "run" ? "This runs exactly what you type in your terminal. Review the command before opening it." : ""
                            font: Tokens.font.body.small
                            color: Colours.palette.m3onSurfaceVariant
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                    TextButton { visible: !!root.selected && !["hint", "error"].includes(root.selected.kind); Layout.fillWidth: true; text: root.copyable ? "Copy result  ↵" : "Open  ↵"; onClicked: root.activate(root.selected) }
                    TextButton { visible: root.copyable; Layout.fillWidth: true; text: "Paste to previous window"; type: TextButton.Text; onClicked: { LauncherData.paste(root.selected); root.screenState.launcher = false; } }
                    TextButton { visible: root.selected?.kind === "file"; Layout.fillWidth: true; text: "Open containing folder"; type: TextButton.Text; onClicked: { LauncherData.openFolder(root.selected); root.screenState.launcher = false; } }
                    TextButton { visible: root.selected?.kind === "file"; Layout.fillWidth: true; text: "Copy path"; type: TextButton.Text; onClicked: { LauncherData.copyPath(root.selected); root.screenState.launcher = false; } }
                    TextButton { visible: root.selected?.kind === "snippet"; Layout.fillWidth: true; text: "Edit snippet"; type: TextButton.Text; onClicked: { root.snippetId = root.selected.id; snippetTitle.text = root.selected.title; snippetShortcut.text = root.selected.shortcut; snippetBody.text = root.selected.body; root.editingSnippet = true; snippetTitle.forceActiveFocus(); } }
                    TextButton { visible: ["clip", "snippet"].includes(root.selected?.kind); Layout.fillWidth: true; text: "Delete selected"; type: TextButton.Text; onClicked: root.removeSelected() }
                }
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.medium
                    visible: root.editingSnippet
                    StyledText { text: root.snippetId < 0 ? "New snippet" : "Edit snippet"; font: Tokens.font.title.medium }
                    StyledTextField { id: snippetTitle; Layout.fillWidth: true; placeholderText: "Name" }
                    StyledTextField { id: snippetShortcut; Layout.fillWidth: true; placeholderText: "Abbreviation (optional)" }
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        TextArea {
                            id: snippetBody
                            placeholderText: "Your text…\n\nVariables: {date}, {time}, {datetime}"
                            wrapMode: TextEdit.Wrap
                            color: Colours.palette.m3onSurface
                            placeholderTextColor: Colours.palette.m3onSurfaceVariant
                            selectionColor: Colours.palette.m3primaryContainer
                            font: Tokens.font.body.medium
                            background: Rectangle { color: Colours.tPalette.m3surfaceContainerHigh; radius: Tokens.rounding.medium }
                        }
                    }
                    TextButton {
                        text: "Save snippet"
                        Layout.fillWidth: true
                        disabled: !snippetTitle.text.trim() || !snippetBody.text.trim()
                        onClicked: {
                            saveSnippet.command = ["python3", "-I", LauncherData.script, "act", "save-snippet", snippetTitle.text, snippetShortcut.text, snippetBody.text];
                            if (root.snippetId >= 0) saveSnippet.command = [...saveSnippet.command, String(root.snippetId)];
                            saveSnippet.running = true;
                        }
                    }
                    TextButton { text: "Cancel"; type: TextButton.Text; onClicked: root.editingSnippet = false }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium
            StyledText { text: "↑ ↓ Navigate     ↵ Open / copy     Esc Close"; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; Layout.fillWidth: true }
            TextButton { visible: root.category === "snippets"; text: "New snippet"; type: TextButton.Text; onClicked: { root.snippetId = -1; snippetTitle.clear(); snippetShortcut.clear(); snippetBody.clear(); root.editingSnippet = true; snippetTitle.forceActiveFocus(); } }
            TextButton { visible: root.category === "clip"; text: captureStatus.rows[0]?.paused ? "Resume capture" : "Pause capture"; type: TextButton.Text; onClicked: { historyAction.command = ["python3", "-I", LauncherData.script, "act", "toggle-capture"]; historyAction.running = true; } }
            TextButton { visible: root.category === "clip"; text: root.confirmClear ? "Confirm clear history" : "Clear history"; type: TextButton.Text; onClicked: { if (root.confirmClear) { historyAction.command = ["python3", "-I", LauncherData.script, "act", "clear-clips"]; historyAction.running = true; root.confirmClear = false; } else root.confirmClear = true; } }
        }
    }
    // Actions with a completion signal refresh only after storage commits.
    Process { id: saveSnippet; onExited: (code) => { if (code === 0) { root.editingSnippet = false; snippetTitle.clear(); snippetShortcut.clear(); snippetBody.clear(); source.refresh(); search.forceActiveFocus(); } } }
    Process { id: historyAction; onExited: { source.refresh(); captureStatus.refresh(); } }
    Component.onCompleted: { adoptRoute(); search.forceActiveFocus(); }
    Connections {
        target: root.screenState
        function onLauncherCategoryChanged(): void { root.adoptRoute(); }
        function onLauncherQueryChanged(): void { root.adoptRoute(); }
        function onLauncherChanged(): void { if (root.screenState.launcher) { source.refresh(); search.forceActiveFocus(); } }
    }
}
