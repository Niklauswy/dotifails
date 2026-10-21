import QtQuick
import Quickshell

Scope {
    id: root
    property var window: null
    function open(toggle: bool): bool {
        if (window && toggle) { window.destroy(); window = null; return true; }
        if (!window) window = windowComponent.createObject(root);
        else window.visible = true;
        return !!window;
    }
    function close(): void { if (window) { window.destroy(); window = null; } }
    Component { id: windowComponent; ProcessWindow { id: processWindow; Component.onDestruction: if (root.window === processWindow) root.window = null } }
}
