pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun
import "Translate.js" as Translate

// What fills the launcher under a prefix: Google or YouTube suggestions for "?" and "!", and
// the person's own shell history for ">". Items belong to (kind, query); the panel only shows them
// while both still match what is typed.
Singleton {
    id: root

    // "google" | "youtube" (web suggestions) | "run" (shell history) | "proc" (what is running)
    property string kind
    property string query
    property var items: []

    property int serial

    function ask(site: string, text: string): void {
        if (site === kind && text === query)
            return;
        kind = site;
        query = text;
        serial++;
        if (site === "run" || site === "proc") {
            // A local pipeline per keystroke would be wasteful: wait for a pause in typing.
            local.restart();
            return;
        }
        if (!text) {
            items = [];
            debounce.stop();
            return;
        }
        debounce.restart();
    }

    function clear(): void {
        if (!kind && !items.length)
            return;
        debounce.stop();
        kind = "";
        query = "";
        items = [];
        serial++;
    }

    // The last few thousand history lines, newest first, the most recent duplicate winning, with
    // extended-history timestamps stripped; the whole file is never read.
    readonly property string historyScript: 'f="${HISTFILE:-$HOME/.zsh_history}"; [ -r "$f" ] || exit 0; ' +
        'tail -n 4000 "$f" | tac | sed "s/^: [0-9]*:[0-9]*;//" | LC_ALL=C grep -a -i -F -- "$1" | ' +
        'awk \'length($0) > 2 && length($0) < 160 && !seen[$0]++\' | head -8'

    // Name, process count, CPU %, MB: one line per program (names may hold spaces, so the name is
    // whatever follows the two numbers), busiest first, matching what was typed.
    readonly property string processScript: 'ps -eo pcpu=,rss=,comm= | awk \'{c = $1; r = $2; $1 = $2 = ""; sub(/^ +/, ""); ' +
        'n[$0]++; cpu[$0] += c; mem[$0] += r} END {for (k in n) printf "%s\\t%d\\t%.0f\\t%.0f\\n", k, n[k], cpu[k], mem[k] / 1024}\' | ' +
        'LC_ALL=C sort -t "$(printf \'\\t\')" -k3,3nr | LC_ALL=C grep -a -i -F -- "$1" | head -8'

    Timer {
        id: debounce

        interval: 150
        onTriggered: {
            const id = root.serial, site = root.kind, text = root.query;
            Requests.get(Translate.suggestUrl(site, text), body => {
                if (id !== root.serial)
                    return;
                try {
                    root.items = Translate.parseSuggest(body, text);
                } catch (error) {
                    root.items = [];
                }
            }, () => {
                if (id === root.serial)
                    root.items = [];
            });
        }
    }

    Timer {
        id: local

        interval: 120
        onTriggered: {
            history.running = false;
            history.command = ["sh", "-c", root.kind === "proc" ? root.processScript : root.historyScript, "sh", root.query];
            history.running = true;
        }
    }

    Process {
        id: history

        stdout: StdioCollector {
            onStreamFinished: {
                if (root.kind === "run" || root.kind === "proc")
                    root.items = text.split("\n").filter(Boolean);
            }
        }
    }
}
