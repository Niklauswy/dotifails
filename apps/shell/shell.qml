pragma ComponentBehavior: Bound
import Quickshell
import Quickshell.Hyprland
import "Logic.js" as Logic

ShellRoot {
    id: root
    Preferences { id: prefs }
    ShellController { id: shellState; preferences: prefs; resources: stats }
    SystemClock { id: wallClock; precision: SystemClock.Minutes }
    ResourceStats {
        id: stats
        enabled: prefs.bar.left.concat(prefs.bar.center, prefs.bar.right).indexOf("resources") >= 0
            && Quickshell.screens.some(s => Logic.barPresentation(s.width - 24).showResources
                && Logic.monitorEnabled(prefs.environment, s.name, prefs.nativeBarData) && !Hyprland.monitorFor(s)?.activeWorkspace?.hasFullscreen)
    }
    Variants {
        model: Quickshell.screens
        Desktop { preferences: prefs }
    }
    Variants {
        model: Quickshell.screens
        Bar { preferences: prefs; controller: shellState; clock: wallClock; resources: stats }
    }
    Surface { preferences: prefs; controller: shellState; clock: wallClock }
}
