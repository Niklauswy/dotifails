// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Base: 6c70d5cb0cbf31413d300699540c858ad28c1539; véanse LICENSE y UPSTREAM.json.
//@ pragma Env QS_CRASHREPORT_URL=https://github.com/caelestia-dots/shell/issues/new?template=crash.yml
//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1
//@ pragma DefaultEnv QS_DROP_EXPENSIVE_FONTS=1
//@ pragma DefaultEnv QSG_RENDER_LOOP=threaded
//@ pragma DefaultEnv QT_QUICK_FLICKABLE_WHEEL_DECELERATION=10000

import QtQuick
import Quickshell
import Caelestia.Config
import qs.services
import qs.wysun
import qs.modules.areapicker
import qs.modules.background
import qs.modules.drawers
import qs.modules.lock
import qs.daemons

ShellRoot {
    id: root

    settings.watchFiles: true

    Component.onCompleted: {
        // Force certain singletons to load on shell init instead of lazily
        Notifs;
        Players;
        Brightness;
        Weather.reload();

        if (GlobalConfig.utilities.vpn.enabled)
            VPN;
    }

    FontLoader {
        source: Quickshell.shellPath("assets/google-sans-flex/GoogleSansFlex-VariableFont_GRAD,ROND,opsz,slnt,wdth,wght.ttf")
    }

    Binding {
        target: ShellState
        property: "shellRoot"
        value: root
    }

    FontLoader { source: Quickshell.shellPath("assets/fonts/MaterialSymbolsRounded.ttf") }

    // Modules
    Background {}
    Drawers {}
    AreaPicker {}
    WysunBridge {}

    // Daemons
    BatteryMonitor {}
    IdleInhibit {}

}
