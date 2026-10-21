pragma Singleton

import QtQuick
import Quickshell
import Wysun.Config
import Wysun.Models
import qs.utils

// Application index, built once from the desktop entries and kept as plain JS rows so that
// filtering is an in-memory scan. Frequencies come from the AppDb (sqlite) usage counters.
Singleton {
    id: root

    property var rows: []

    function launch(row: var): void {
        appDb.incrementFrequency(row.id);
        row.freq = (row.freq || 0) + 1;
        run(row.entry, row.runInTerminal);
    }

    function run(entry: var, inTerminal: bool): void {
        if (inTerminal)
            Quickshell.execDetached({
                command: [...GlobalConfig.general.apps.terminal, `${Quickshell.shellDir}/assets/wrap_term_launch.sh`, ...entry.command],
                workingDirectory: entry.workingDirectory
            });
        else
            entry.execute();
    }

    function rebuild(): void {
        const out = [];
        const apps = appDb.apps;
        for (let i = 0; i < apps.length; i++) {
            const a = apps[i];
            const name = a.name || a.id;
            out.push({
                kind: "app", key: "app:" + a.id, id: a.id, title: name,
                subtitle: a.comment || a.genericName || "Application",
                icon: a.entry?.icon ?? "", type: "Application",
                l: name.toLowerCase(),
                a: [a.genericName, a.keywords, a.comment, a.categories, a.startupClass, a.id].join(" ").toLowerCase(),
                freq: a.frequency, entry: a.entry, runInTerminal: a.entry?.runInTerminal ?? false
            });
        }
        rows = out;
    }

    AppDb {
        id: appDb

        path: `${Paths.state}/apps.sqlite`
        favouriteApps: GlobalConfig.launcher.favouriteApps
        entries: DesktopEntries.applications.values.filter(a => !Strings.testRegexList(GlobalConfig.launcher.hiddenApps, a.id))
        onAppsChanged: rebuildTimer.restart()
    }

    Timer {
        id: rebuildTimer

        interval: 40
        onTriggered: root.rebuild()
    }

    Component.onCompleted: rebuild()
}
