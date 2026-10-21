// Wysun integration; original Wysun components and motion remain authoritative.
import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.utils
import qs.modules.nexus

Scope {
    id: root
    readonly property var surfaces: ({ dashboard: 'dashboard', test: 'dashboard', windows: 'dashboard',
        launcher: 'launcher', emoji: 'emoji', menu: 'utilities', quicksettings: 'utilities', notifications: 'sidebar', sidebar: 'sidebar', session: 'session' })
    function current() { return ShellState.forActive(); }
    function available(kind, state) {
        return kind !== 'launcher' || !!ShellState.componentsFor(state.modelData)?.panels?.launcher?.available;
    }
    function close() {
        for (const screen of Quickshell.screens) {
            const state = ShellState.forScreen(screen);
            if (state) for (const name of Object.values(surfaces)) state[name] = false;
        }
    }
    function show(kind, toggle) {
        const state = current(), field = surfaces[kind];
        if (!state || !field || !available(kind, state)) return false;
        const value = toggle ? !state[field] : true;
        close(); state[field] = value;
        if (kind === 'launcher' && value) state.launcherCategory = 'all';
        if (kind === 'windows') state.dashboardTab = 3;
        return true;
    }
    // Diagnostic: open a surface on a named output (e.g. when the focused one has a fullscreen app).
    function showOn(name, kind) {
        const field = surfaces[kind];
        const screen = Quickshell.screens.find(s => s.name === name);
        const state = screen ? ShellState.forScreen(screen) : null;
        if (!state || !field || !available(kind, state)) return false;
        close(); state[field] = true;
        return true;
    }
    IpcHandler {
        target: 'wysunShell'
        function toggle(surface: string): bool { return root.show(surface, true); }
        function open(surface: string): bool { return root.show(surface, false); }
        function openOn(output: string, surface: string): bool { return root.showOn(output, surface); }
        function category(mode: string): bool {
            if (!["all", "apps", "files", "clip", "snippets", "calc", "windows", "commands"].includes(mode)) return false;
            if (!root.show('launcher', false)) return false;
            root.current().launcherCategory = mode;
            return true;
        }
        // Programmatic plain-text search; category selection has its own IPC.
        function search(text: string): bool {
            if (!root.show('launcher', false)) return false;
            root.current().launcherQuery = text;
            return true;
        }
        // Brightness keys: go through the shell so the OSD reacts.
        function brightness(direction: string): bool {
            if (direction === 'up') Brightness.increaseBrightness(); else if (direction === 'down') Brightness.decreaseBrightness(); else return false;
            return true;
        }
        function close(): void { root.close(); }
        function reloadPreferences(): void { environment.reload(); }
        // Settings, connections and processes are Nexus pages (displays, shortcuts, processes, ...).
        function openRoute(route: string): bool { return WindowFactory.createRoute(route); }
        function openThemeSettings(): bool { Quickshell.execDetached(['wysun', 'settings', 'theme']); return true; }
        function theme(): string { return JSON.stringify({ name: Colours.scheme, variant: Colours.flavour }); }
        function status(): string {
            const state = root.current();
            return JSON.stringify({ implementation: 'wysun', revision: '6c70d5cb',
                screens: Quickshell.screens.map(s => s.name), focused: Hypr.focusedMonitor?.name ?? '',
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
