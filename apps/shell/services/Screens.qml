pragma Singleton

import Quickshell
import Quickshell.Io
import Wysun.Config
import qs.utils
import "WidgetScreens.js" as WidgetScreens

Singleton {
    id: root

    readonly property list<ShellScreen> screens: Quickshell.screens.filter(s => GlobalConfig.forScreen(s.name).enabled)
    property var displayPreferences: ({})
    readonly property bool widgetsOnlyPrimary: displayPreferences.widgetScreens === "primary"
    readonly property string primaryName: WidgetScreens.primaryName(screens.map(s => s.name), displayPreferences)
    readonly property list<ShellScreen> widgetScreens: widgetsOnlyPrimary ? screens.filter(s => s.name === primaryName) : screens

    function hasWidgets(screen: ShellScreen): bool {
        return !!screen && widgetScreens.some(s => s.name === screen.name);
    }

    function drawerScreen(screen: ShellScreen): ShellScreen {
        return widgetsOnlyPrimary ? (widgetScreens[0] ?? null) : screen;
    }

    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Paths.home + "/.config") + "/orbit/environment.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try { root.displayPreferences = JSON.parse(text()).displays || {}; }
            catch (error) { console.warn("Wysun: keeping previous display preferences", error); }
        }
    }

    function isExcluded(screen: ShellScreen): bool {
        return !GlobalConfig.forScreen(screen.name).enabled;
    }
}
