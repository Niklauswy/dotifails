pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import "StudyApps.js" as Apps

// Study mode: the blocked apps are closed while a session runs, so they stop using the machine (no video
// playing on, no memory held): their windows get a normal close request when the session starts and
// whenever one opens during it. Windows parked in special:wysun-study by older versions are given back.
Singleton {
    id: root

    readonly property bool ready: Study.loaded
    readonly property bool active: Study.active

    function address(a: string): string {
        return a.startsWith("0x") ? a : `0x${a}`;
    }

    function move(addr: string, name: string): void {
        const a = address(addr);
        const workspace = Apps.workspaceSelector(name);
        Hypr.dispatch(Hypr.usingLua ? `hl.dsp.window.move({ window = "address:${a}", workspace = "${workspace}", follow = false })`
                                    : `movetoworkspacesilent ${workspace},address:${a}`);
    }

    function close(addr: string): void {
        const a = address(addr);
        Hypr.dispatch(Hypr.usingLua ? `hl.dsp.window.close({ window = "address:${a}" })` : `closewindow address:${a}`);
    }

    function windows(): var {
        return Hypr.toplevels.values.map(t => ({
            address: t.address,
            class: t.lastIpcObject?.class || t.wayland?.appId || "",
            workspace: t.workspace?.name ?? ""
        }));
    }

    function blocked(): var {
        return Study.session?.config?.blocked ?? Study.prefs.blocked;
    }

    // Closes every window of a blocked app and tells the pill which apps were closed.
    function closeBlocked(): void {
        const all = windows();
        // Also those an older version parked in the hidden workspace (still running there).
        const parked = all.filter(w => w.workspace === Apps.HIDDEN_WORKSPACE && Apps.isBlocked(w.class, blocked()));
        const targets = Apps.toHide(all, blocked()).concat(parked);
        const names = [];
        let icon = "";
        for (const w of targets) {
            const cls = all.find(x => x.address === w.address)?.class ?? "";
            const name = Study.appName(cls);
            if (!names.includes(name)) {
                names.push(name);
                icon = icon || (DesktopEntries.heuristicLookup(cls)?.icon ?? "");
            }
            close(w.address);
        }
        if (names.length)
            Study.closedAtStart(names.join(", "), icon);
    }

    // Gives back every window parked in the hidden workspace: to its own workspace if recorded, else to the
    // focused monitor's active one.
    function restoreAll(): void {
        const records = Study.session?.hidden ?? [];
        const names = Hypr.workspaces.values.map(w => w.name);
        for (const t of Hypr.toplevels.values) {
            if (t.workspace?.name !== Apps.HIDDEN_WORKSPACE)
                continue;
            // Unknown or vanished workspace: the active one of the window's own monitor.
            const fallback = t.monitor?.activeWorkspace?.name ?? Hypr.focusedWorkspace?.name ?? "1";
            const rec = records.find(r => r.address === t.address);
            move(t.address, Apps.restoreTarget(rec ? rec.workspace : fallback, names, fallback));
        }
        if (records.length)
            Study.setHidden([]);
    }

    function handleOpened(data: string): void {
        const parts = data.split(",");
        if (parts.length < 3)
            return;
        const [addr, workspace, cls] = parts;
        if (workspace === Apps.HIDDEN_WORKSPACE || workspace.startsWith("special:") || !Apps.isBlocked(cls, blocked()))
            return;
        close(addr);
        const entry = DesktopEntries.heuristicLookup(cls);
        Study.countDistraction(Study.appName(cls), entry?.icon || "");
    }

    onActiveChanged: {
        if (!ready)
            return;
        if (active)
            closeBlocked();
        else
            restoreAll();
    }

    onReadyChanged: {
        if (!ready)
            return;
        Hyprland.refreshToplevels();
        recoverTimer.start();
    }

    // Toplevels arrive after the refresh: act once they are there.
    Timer {
        id: recoverTimer

        interval: 400
        onTriggered: root.active ? root.closeBlocked() : root.restoreAll()
    }

    Connections {
        target: Hyprland

        function onRawEvent(event: HyprlandEvent): void {
            if (root.active && event.name === "openwindow")
                root.handleOpened(event.data);
        }
    }
}
