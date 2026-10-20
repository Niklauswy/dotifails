pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "services" as Services
import "modules/rail" as RailModule
import "modules/frame" as FrameModule
import "modules/popouts" as PopoutModule
import "modules/osd" as OsdModule

ShellRoot {
    id: root
    Preferences { id: prefs }
    Services.Colours { id: colours }
    OutputManager { id: outputs }
    ShellState { id: shellState }
    Motion { id: motion; reducedMotion: prefs.appearance.reducedMotion }
    ShellController { id: controller; preferences: prefs; state: shellState }
    SystemClock { id: wallClock; precision: SystemClock.Minutes }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/Rubik-Variable.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }
    FontLoader {
        source: Quickshell.shellPath("assets/fonts/MaterialSymbolsRounded.ttf")
        onStatusChanged: if (status === FontLoader.Ready) Appearance.refreshFonts()
    }
    Variants {
        model: Quickshell.screens
        Desktop { preferences: prefs }
    }
    Variants {
        model: Quickshell.screens
        RailModule.Rail { preferences: prefs; controller: controller; clock: wallClock; motion: motion; outputs: outputs }
    }
    Variants {
        model: Quickshell.screens
        FrameModule.ScreenFrame { preferences: prefs; outputs: outputs }
    }
    Variants {
        model: Quickshell.screens
        PopoutModule.PopoutHost { controller: controller; motion: motion }
    }
    OsdModule.Osd { motion: motion }
}
