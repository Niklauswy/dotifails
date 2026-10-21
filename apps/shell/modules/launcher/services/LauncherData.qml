pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun.Config

// Shared activation helpers. Request streams belong to each widget (DataSource).
Singleton {
    id: root

    readonly property string script: `${Quickshell.env("WYSUN_APP_DIR") || `${Quickshell.env("HOME")}/.local/share/orbit/app`}/launcher_data.py`

    function webRow(query: string): var {
        return {
            kind: "web",
            title: "Search DuckDuckGo",
            subtitle: query,
            icon: "travel_explore",
            query: query
        };
    }

    function runRow(command: string): var {
        return {
            kind: "run",
            title: "Run in terminal",
            subtitle: command,
            icon: "terminal",
            command: command
        };
    }

    function openFolder(row: var): bool {
        if (row.kind !== "file")
            return false;
        Quickshell.execDetached(["xdg-open", row.path.slice(0, row.path.lastIndexOf("/")) || "/"]);
        return true;
    }

    function copyPath(row: var): bool {
        if (row.kind !== "file")
            return false;
        Quickshell.execDetached(["wl-copy", "--", row.path]);
        return true;
    }

    function run(args: var): void {
        Quickshell.execDetached(["python3", "-I", script, "act", ...args]);
    }

    function copy(row: var): void {
        if (row.kind === "clip" && row.clip_kind === "image")
            run(["copy-image", String(row.id)]);
        else
            Quickshell.execDetached(["wl-copy", "--", row.value ?? row.title]);
        if (row.kind === "calc" && row.query)
            run(["record-calc", row.query, row.value]);
    }

    // Copy, then paste into the window that was focused before the launcher.
    function paste(row: var): bool {
        if (["clip", "snippet", "emoji", "calc"].indexOf(row.kind) < 0)
            return false;
        copy(row);
        run(["paste"]);
        return true;
    }

    // Returns true when the launcher should close.
    function activate(row: var): bool {
        switch (row.kind) {
        case "clip":
        case "snippet":
        case "emoji":
        case "calc":
            copy(row);
            return true;
        case "file":
            Quickshell.execDetached(["xdg-open", row.path]);
            return true;
        case "window":
            run(["focus-window", row.wid]);
            return true;
        case "snippet-new":
            run(["save-snippet", ...row.args]);
            return true;
        case "run":
            Quickshell.execDetached([...GlobalConfig.general.apps.terminal, `${Quickshell.shellDir}/assets/wrap_term_launch.sh`, "sh", "-c", row.command]);
            return true;
        case "web":
            Quickshell.execDetached(["xdg-open", `https://duckduckgo.com/?q=${encodeURIComponent(row.query)}`]);
            return true;
        }
        return false;
    }

}
