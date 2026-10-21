//@ pragma DefaultEnv QSG_RENDER_LOOP=threaded
//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1

import QtQuick
import Quickshell
import qs.modules.lock

// Entry point of the Wysun lock screen; started by `wysun-lock`, not by the shell.
ShellRoot {
    FontLoader {
        source: Quickshell.shellPath("assets/google-sans-flex/GoogleSansFlex-VariableFont_GRAD,ROND,opsz,slnt,wdth,wght.ttf")
    }

    FontLoader {
        source: Quickshell.shellPath("assets/fonts/MaterialSymbolsRounded.ttf")
    }

    Lock {}
}
