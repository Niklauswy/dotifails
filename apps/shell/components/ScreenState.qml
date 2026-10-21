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
    property string launcherCategory
    property bool emoji
    property bool cheatsheet
    property string launcherQuery

    // Dashboard state
    property int dashboardTab
    property date dashboardDate: new Date()
}
