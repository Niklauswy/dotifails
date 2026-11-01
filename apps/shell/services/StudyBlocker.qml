pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import "StudyApps.js" as Apps

// Study mode: windows of apps that are not allowed move silently to special:wysun-study while a session runs
// and go back to their workspace when it ends. Nothing is ever closed. If the shell starts with no live
// session and windows are still parked there (a crash), they are given back.
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

    function windows(): var {
        return Hypr.toplevels.values.map(t => ({
            address: t.address,
            class: t.lastIpcObject?.class || t.wayland?.appId || "",
            workspace: t.workspace?.name ?? ""
        }));
    }

    function allowed(): var {
        return Study.session?.config?.allowed ?? Study.prefs.allowed;
    }

    function hideAll(): void {
        const parked = Study.session?.hidden ?? [];
        const known = parked.map(h => h.address);
        const fresh = Apps.toHide(windows(), allowed()).filter(w => !known.includes(w.address));
        for (const w of fresh)
            move(w.address, Apps.HIDDEN_WORKSPACE);
        if (fresh.length)
            Study.setHidden(parked.concat(fresh));
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
        if (workspace === Apps.HIDDEN_WORKSPACE || workspace.startsWith("special:") || Apps.isAllowed(cls, allowed()))
            return;
        move(addr, Apps.HIDDEN_WORKSPACE);
        Study.setHidden((Study.session?.hidden ?? []).concat([{address: addr, workspace: workspace}]));
        const entry = DesktopEntries.heuristicLookup(cls);
        Study.countDistraction(Study.appName(cls), entry?.icon || "");
    }

    onActiveChanged: {
        if (!ready)
            return;
        if (active)
            hideAll();
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
        onTriggered: root.active ? root.hideAll() : root.restoreAll()
    }

    Connections {
        target: Hyprland

        function onRawEvent(event: HyprlandEvent): void {
            if (root.active && event.name === "openwindow")
                root.handleOpened(event.data);
        }
    }
}
