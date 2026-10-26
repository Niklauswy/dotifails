// The window-level layer menus, dialogs, tooltips and snackbars draw in. Put one last in the app's root item
// (it fills it, above everything) and pass it as their `host`, or adopt() any item into it. Without a host, an
// overlay uses the top item of its own tree, which is the same thing when the app root fills the window.
import QtQuick

Item {
    id: root

    anchors.fill: parent
    z: 1000

    function adopt(item) {
        item.parent = root;
        return item;
    }
}
