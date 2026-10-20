import QtQuick

QtObject {
    property string surface: ""
    property string screenName: ""
    property real anchorX: 36
    property real anchorY: 200
    property string phase: "closed"
    property string returnFocus: ""
    property var returnFocusItem: null
    readonly property bool opened: surface !== ""

    function open(kind, screen, x, y, focusTarget, focusItem) {
        surface = kind;
        screenName = screen;
        anchorX = typeof x === "number" && isFinite(x) ? x : anchorX;
        anchorY = typeof y === "number" && isFinite(y) ? y : anchorY;
        returnFocus = focusTarget || "";
        returnFocusItem = focusItem || null;
        phase = "opening";
    }

    function close() {
        if (!opened) return;
        var restoreItem = returnFocusItem;
        phase = "closing";
        surface = "";
        returnFocus = "";
        returnFocusItem = null;
        if (restoreItem) Qt.callLater(function() {
            if (restoreItem && restoreItem.visible && restoreItem.enabled)
                restoreItem.forceActiveFocus();
        });
    }
}
