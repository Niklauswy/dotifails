// A list of songs (a TrackListModel) with the M3 list rhythm. Click plays (in `contextKeys`/`contextId`),
// double click too; Ctrl/Shift+click and long press select several, with a selection bar above the list;
// right click, the «más» button or the Menu key open the song menu. Keys: ↑/↓, Enter plays, Ctrl+Enter opens
// the artist, F toggles favourite, Ctrl+A selects all, Esc clears the selection.
import QtQuick
import WysunM3

ListView {
    id: root

    property string contextId
    // The list a click plays in; by default the rows shown (a search shows 5 but plays among all matches).
    property var contextKeys: null
    // Replaces what a click/Enter does with a row (e.g. the queue jumps instead of starting a context).
    property var playHandler: null
    property bool numbered: true
    property bool covers: true
    property bool albums: true
    property bool striped: true
    property var selection: ({})
    property int anchorIndex: -1
    readonly property var selectedKeys: Object.keys(selection).filter(k => selection[k])
    readonly property bool selecting: selectedKeys.length > 0

    signal playRequested(string key)
    signal artistRequested(string name)
    signal contextRequested(var keys, real x, real y)

    function keys() {
        return contextKeys ?? (model ? model.keys : []);
    }

    function play(index) {
        if (playHandler) {
            playHandler(index);
            return;
        }
        const key = model.keyAt(index);
        if (key !== "")
            player.play(key, keys(), contextId);
        playRequested(key);
    }

    function clearSelection() {
        selection = {};
        anchorIndex = -1;
    }

    function toggleSelected(index) {
        const key = model.keyAt(index);
        const next = Object.assign({}, selection);
        next[key] = !next[key];
        selection = next;
        anchorIndex = index;
        currentIndex = index;
    }

    function selectRange(index) {
        const from = Math.min(anchorIndex < 0 ? index : anchorIndex, index);
        const to = Math.max(anchorIndex < 0 ? index : anchorIndex, index);
        const next = {};
        for (let i = from; i <= to; ++i)
            next[model.keyAt(i)] = true;
        selection = next;
        currentIndex = index;
    }

    function selectAll() {
        const next = {};
        for (const key of model.keys)
            next[key] = true;
        selection = next;
    }

    function rowClicked(index, mouse) {
        forceActiveFocus(Qt.MouseFocusReason);
        if (mouse.button === Qt.RightButton) {
            const p = itemAtIndex(index).mapToItem(null, mouse.x, mouse.y);
            menuFor(index, p.x, p.y);
            return;
        }
        if (mouse.modifiers & Qt.ControlModifier)
            toggleSelected(index);
        else if (mouse.modifiers & Qt.ShiftModifier)
            selectRange(index);
        else if (selecting)
            toggleSelected(index);
        else {
            currentIndex = index;
            play(index);
        }
    }

    // The menu acts on the selection when the row is part of it, else on that row alone.
    function menuFor(index, x, y) {
        const key = model.keyAt(index);
        currentIndex = index;
        contextRequested(selection[key] ? selectedKeys : [key], x, y);
    }

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    activeFocusOnTab: true
    keyNavigationEnabled: true
    highlightMoveDuration: 0
    reuseItems: true
    cacheBuffer: MusicMetrics.trackRow * 10
    onModelChanged: clearSelection()
    Connections {
        target: root.model
        ignoreUnknownSignals: true

        function onModelReset() {
            root.clearSelection();
        }
    }

    Keys.onPressed: event => {
        if (currentIndex < 0 && count > 0 && (event.key === Qt.Key_Down || event.key === Qt.Key_Up))
            currentIndex = 0;
        switch (event.key) {
        case Qt.Key_Return:
        case Qt.Key_Enter:
            if (event.modifiers & Qt.ControlModifier)
                artistRequested(music.trackArtists(model.keyAt(currentIndex))[0] ?? "");
            else
                play(currentIndex);
            break;
        case Qt.Key_F:
            if (event.modifiers !== Qt.NoModifier)
                return;
            music.toggleFavorite(model.keyAt(currentIndex));
            break;
        case Qt.Key_Menu:
            {
                const item = itemAtIndex(currentIndex);
                if (item) {
                    const p = item.mapToItem(null, item.width / 3, item.height);
                    menuFor(currentIndex, p.x, p.y);
                }
            }
            break;
        case Qt.Key_A:
            if (!(event.modifiers & Qt.ControlModifier))
                return;
            selectAll();
            break;
        case Qt.Key_Escape:
            if (!selecting)
                return;
            clearSelection();
            break;
        case Qt.Key_Space:
            if (!selecting)
                return;
            toggleSelected(currentIndex);
            break;
        default:
            return;
        }
        event.accepted = true;
    }

    delegate: TrackRow {
        list: root
    }
}
