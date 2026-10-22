pragma Singleton

import Quickshell

// Helpers shared by the launcher and the emoji drawer. Request streams belong to each widget.
Singleton {
    id: root

    readonly property string script: `${Quickshell.env("WYSUN_APP_DIR") || `${Quickshell.env("HOME")}/.local/share/orbit/app`}/launcher_data.py`

    function run(args: var): void {
        Quickshell.execDetached(["python3", "-I", script, "act", ...args]);
    }

    function copy(row: var): void {
        if (row.kind === "clip" && row.clip_kind === "image")
            run(["copy-image", String(row.id)]);
        else
            Quickshell.execDetached(["wl-copy", "--", row.value ?? row.title]);
        if (row.kind === "calc" && row.expression)
            run(["record-calc", row.expression, row.value]);
    }

    // Copy, then paste into the window that was focused before the launcher.
    function paste(row: var): bool {
        if (["clip", "emoji", "calc", "history"].indexOf(row.kind) < 0)
            return false;
        copy(row);
        run(["paste"]);
        return true;
    }
}
