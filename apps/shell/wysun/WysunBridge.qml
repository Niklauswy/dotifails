// Wysun integration; original Caelestia components and motion remain authoritative.
import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.utils

Scope {
    id: root
    readonly property var surfaces: ({ dashboard: 'dashboard', test: 'dashboard', windows: 'dashboard',
        launcher: 'launcher', menu: 'utilities', quicksettings: 'utilities', notifications: 'sidebar', session: 'session' })
    function current() { return ShellState.forActive(); }
    function close() {
        for (const screen of Quickshell.screens) {
            const state = ShellState.forScreen(screen);
            if (state) for (const name of Object.values(surfaces)) state[name] = false;
        }
    }
    function show(kind, toggle) {
        const state = current(), field = surfaces[kind];
        if (!state || !field) return false;
        const value = toggle ? !state[field] : true;
        close(); state[field] = value;
        if (kind === 'windows') state.dashboardTab = 3;
        return true;
    }
    IpcHandler {
        target: 'wysunShell'
        function toggle(surface: string): bool { return root.show(surface, true); }
        function open(surface: string): bool { return root.show(surface, false); }
        function close(): void { root.close(); }
        function reloadPreferences(): void { environment.reload(); }
        function openThemeSettings(): bool { Quickshell.execDetached(['wysun', 'settings', 'theme']); return true; }
        function theme(): string { return JSON.stringify({ name: Colours.scheme, variant: Colours.flavour }); }
        function status(): string {
            const state = root.current();
            return JSON.stringify({ implementation: 'caelestia', revision: '6c70d5cb',
                screens: Quickshell.screens.map(s => s.name),
                open: state ? Object.keys(root.surfaces).filter(k => state[root.surfaces[k]]) : [],
                scheme: Colours.scheme });
        }
    }
    FileView {
        id: environment
        path: (Quickshell.env('XDG_CONFIG_HOME') || Paths.home + '/.config') + '/orbit/environment.json'
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try { Wallpapers.wysunWallpaper = JSON.parse(text()).wallpaper || {}; }
            catch (error) { console.warn('Wysun: fondo inválido; se conserva el anterior'); }
        }
    }
}
