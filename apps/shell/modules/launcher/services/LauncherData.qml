pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun.Config

// Rows for the Wysun data modes (clipboard, files, snippets, windows, emoji,
// calculator history). The Python provider shares storage with the Qt palette.
Singleton {
    id: root

    readonly property var modes: ({
            clip: ["clip", "clipboard", "portapapeles", "historial"],
            files: ["files", "file", "archivos"],
            snippets: ["snip", "snippets", "snippet"],
            windows: ["win", "windows", "ventanas"],
            emoji: ["emoji"],
            calc: ["hist", "history"]
        })
    readonly property string script: `${Quickshell.env("WYSUN_APP_DIR") || `${Quickshell.env("HOME")}/.local/share/orbit/app`}/launcher_data.py`

    property var rows: []
    property string rowsMode: ""
    property string rowsText: ""
    property bool loading: false
    property string pendingMode: ""
    property string pendingText: ""

    // ">clip foo" -> {mode: "clip", text: "foo"}; null if not a data mode.
    function parse(search: string, prefix: string): var {
        if (!search.startsWith(prefix))
            return null;
        const body = search.slice(prefix.length);
        const space = body.indexOf(" ");
        if (space < 0)
            return null;
        const word = body.slice(0, space).toLowerCase();
        for (const mode in modes)
            if (modes[mode].indexOf(word) >= 0)
                return {
                    mode: mode,
                    text: body.slice(space + 1)
                };
        return null;
    }

    function webRow(query: string): var {
        return {
            kind: "web",
            title: "Buscar en DuckDuckGo",
            subtitle: query,
            icon: "travel_explore",
            query: query
        };
    }

    function runRow(command: string): var {
        return {
            kind: "run",
            title: "Ejecutar en la terminal",
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

    function request(mode: string, text: string): void {
        if (mode === rowsMode && text === rowsText && !loading)
            return;
        pendingMode = mode;
        pendingText = text;
        debounce.restart();
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

    function remove(row: var): bool {
        if (row.kind === "clip")
            run(["delete-clip", String(row.id)]);
        else if (row.kind === "snippet")
            run(["delete-snippet", String(row.id)]);
        else
            return false;
        rows = rows.filter(r => r !== row);
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

    Timer {
        id: debounce

        interval: 65
        onTriggered: {
            proc.pendingRun = true;
            if (!proc.running)
                proc.startNext();
        }
    }

    Process {
        id: proc

        property bool pendingRun: false
        property string mode
        property string text

        function startNext(): void {
            pendingRun = false;
            mode = root.pendingMode;
            text = root.pendingText;
            root.loading = true;
            command = ["python3", "-I", root.script, "query", mode, text];
            running = true;
        }

        onExited: {
            if (pendingRun)
                startNext();
            else
                root.loading = false;
        }

        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const parsed = JSON.parse(text);
                    if (proc.mode === root.pendingMode && proc.text === root.pendingText) {
                        root.rows = parsed;
                        root.rowsMode = proc.mode;
                        root.rowsText = proc.text;
                    }
                } catch (e) {
                    root.rows = [];
                }
            }
        }
    }
}
