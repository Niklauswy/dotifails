import Quickshell

PersistentProperties {
    required property ShellScreen modelData

    // Drawer visibilities
    property bool bar
    property bool osd
    property bool session
    property bool launcher
    property bool overview
    property bool overviewKeyboard
    property bool dashboard
    property bool utilities
    property bool sidebar
    property bool aiUsage
    // Clicked inside: stays open when the pointer leaves, until Esc, a click outside or its toggle.
    property bool aiUsagePinned
    property string launcherCategory
    property bool emoji
    property bool cheatsheet
    property bool wallpapers
    property string launcherQuery

    // Dashboard state; dashboardKeyboard: opened from a shortcut that wants
    // the keyboard (Esc closes, media keys act on the active player).
    property bool dashboardKeyboard
    property int dashboardTab
    property date dashboardDate: new Date()

    onDashboardChanged: if (!dashboard) dashboardKeyboard = false
}
