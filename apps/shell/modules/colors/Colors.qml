import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root
    property var window: null
    function open(toggle: bool): bool {
        if (window && toggle) { close(); return true; }
        if (!window) window = windowComponent.createObject(root);
        else { window.visible = true;  }
        return !!window;
    }
    function close(): void { if (window) { window.destroy(); window = null; } }

    // Eyedropper straight from the shortcut: no panel first. The picked colour
    // is copied as HEX and the panel opens on it (saved to the recents there).
    // With the panel already open, its own picker runs instead.
    function pick(): bool {
        if (window) { window.sample(); return true; }
        if (!picker.running) picker.running = true;
        return true;
    }
    Process {
        id: picker
        // hyprpicker is Hyprland's native eyedropper (a declared dependency); the
        // portal PickColor route hangs when the GTK portal answers outside GNOME.
        command: ['hyprpicker', '--format=hex', '--no-fancy', '--render-inactive']
        stdout: StdioCollector { onStreamFinished: root.picked(text) }
    }
    function picked(output: string): void {
        // The colour is hyprpicker's last line; earlier lines may be its own logs.
        const found = output.match(/#[0-9a-fA-F]{6}/g);
        if (!found)
            return;  // cancelled with Esc or right click: no colour printed
        const hex = found[found.length - 1].toUpperCase();
        Quickshell.clipboardText = hex;
        // Then the panel opens on that colour, ready to copy other formats or save it.
        if (!window) window = windowComponent.createObject(root, {pickedColor: hex});
        else window.adopt(hex);
    }

    Component {
        id: windowComponent
        ColorWindow {
            id: colorWindow
            Component.onDestruction: if (root.window === colorWindow) root.window = null
        }
    }
}
