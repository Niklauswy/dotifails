pragma Singleton

import Quickshell

// Helpers shared by the launcher and the emoji drawer. Request streams belong to each widget.
Singleton {
    id: root

    readonly property string appDir: Quickshell.env("WYSUN_APP_DIR") || `${Quickshell.env("HOME")}/.local/share/orbit/app`
    readonly property string script: `${appDir}/launcher_data.py`
    // Neovim-coloured code previews, cached on disk (code_preview.py): `codePreview(path)` is the argv.
    function codePreview(path: string): var {
        return ["python3", "-I", `${appDir}/code_preview.py`, path];
    }

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
