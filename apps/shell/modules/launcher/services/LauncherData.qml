pragma Singleton

import Quickshell
import qs.utils

// Helpers shared by the launcher and the emoji drawer. Request streams belong to each widget.
Singleton {
    id: root

    // argv of the launcher's data provider (wysun_services.launcher_data) with `args`.
    function data(args: var): var {
        return Paths.python("wysun_services.launcher_data", args);
    }
    // Neovim-coloured code previews, cached on disk (wysun_services.code_preview): `codePreview(path)` is the argv.
    function codePreview(path: string): var {
        return Paths.python("wysun_services.code_preview", [path]);
    }

    function run(args: var): void {
        Quickshell.execDetached(data(["act", ...args]));
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
