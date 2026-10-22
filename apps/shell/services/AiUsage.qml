pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun.Config
import Wysun.I18n
import qs.utils

// AI provider accounts, limits and local token usage (modules/aiusage/backend.py).
// The last result is cached, so the panel paints at once after a restart; it
// refreshes every minute while a panel holds a Ref and every few minutes in the
// background, which is what drives the low-limit notifications.
Singleton {
    id: root

    property int refCount: 0
    property var snapshot: null
    // Selected tab: "overview" or an account id.
    property string tab: "overview"
    property string range: "24h"
    property string metric: "cost"
    // Notified windows, "<account>:<limit>:<resetsAt>" → "low", kept across restarts.
    property var alerted: ({})
    readonly property bool loading: loader.running
    readonly property var accounts: snapshot?.accounts ?? []
    readonly property var usage: snapshot?.usage ?? ({})
    readonly property var accountColours: [Colours.palette.m3primary, Colours.palette.m3tertiary, Colours.palette.m3secondary, Colours.palette.m3primaryFixedDim, Colours.palette.m3tertiaryFixedDim, Colours.palette.m3secondaryFixedDim]

    // The signed-in limit with the least left: { account, limit, remaining } or null.
    readonly property var tightest: {
        let best = null;
        for (const account of accounts) {
            if (account.source === "history")
                continue;
            for (const limit of account.limits ?? []) {
                const remaining = 100 - limit.usedPercent;
                if (!best || remaining < best.remaining)
                    best = { account: account, limit: limit, remaining: remaining };
            }
        }
        return best;
    }

    function refresh(): void {
        if (!loader.running)
            loader.running = true;
    }

    function account(id: string): var {
        return accounts.find(a => a.id === id) ?? null;
    }

    function colour(id: string): color {
        const index = accounts.findIndex(a => a.id === id);
        return accountColours[Math.max(0, index) % accountColours.length];
    }

    function limitName(id: string): string {
        if (id === "session")
            return Tr.tr("session limit");
        if (id === "weekly")
            return Tr.tr("weekly limit");
        // TRANSLATORS: %1 = a model family with its own weekly limit, such as "opus"
        return Tr.tr("%1 weekly limit").arg(id.replace(/^weekly_/, ""));
    }

    function notify(title: string, body: string, urgency: string): void {
        Quickshell.execDetached(["notify-send", "-a", "Wysun", "-u", urgency, "-i", "utilities-system-monitor", title, body]);
    }

    // Once per window: when a limit drops to the threshold, and when a window
    // that had notified comes back after its reset.
    function checkAlerts(previous: var, next: var): void {
        const threshold = Tokens.sizes.aiUsage.alertThreshold;
        const seen = Object.assign({}, alerted);
        let changed = false;
        for (const account of next?.accounts ?? []) {
            if (account.source === "history")
                continue;
            const name = `${account.providerName} · ${account.label}`;
            for (const limit of account.limits ?? []) {
                const prefix = `${account.id}:${limit.id}:`;
                const key = prefix + (limit.resetsAt ?? "");
                const remaining = Math.round(100 - limit.usedPercent);
                if (remaining <= threshold && !seen[key]) {
                    seen[key] = "low";
                    changed = true;
                    const reset = limit.resetsAt ? Qt.formatDateTime(new Date(limit.resetsAt * 1000), limit.windowMinutes > 1440 ? "ddd hh:mm" : "hh:mm") : "";
                    // TRANSLATORS: %1 = percent left, %2 = limit name such as "weekly limit"
                    const body = Tr.tr("%1% of the %2 left.").arg(remaining).arg(limitName(limit.id)) + (reset ? " " + Tr.tr("Resets %1.").arg(reset) : "");
                    notify(name, body, remaining <= threshold / 2 ? "critical" : "normal");
                }
                // A notified window of this limit with another reset time has rolled over.
                for (const old of Object.keys(seen)) {
                    if (old.startsWith(prefix) && old !== key && seen[old] === "low" && remaining > threshold) {
                        seen[old] = "restored";
                        changed = true;
                        notify(name, Tr.tr("The %1 has reset.").arg(limitName(limit.id)), "low");
                    }
                }
            }
        }
        if (changed) {
            // Keep only recent windows.
            const keys = Object.keys(seen);
            for (const old of keys.slice(0, Math.max(0, keys.length - 64)))
                delete seen[old];
            alerted = seen;
            alertsFile.setText(JSON.stringify(seen));
        }
    }

    function apply(next: var): void {
        const previous = snapshot;
        snapshot = next;
        if (tab !== "overview" && !account(tab))
            tab = "overview";
        if (alertsFile.ready)
            checkAlerts(previous, next);
    }

    Process {
        id: loader

        command: ["python3", "-I", Quickshell.shellPath("modules/aiusage/backend.py")]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.apply(JSON.parse(text));
                } catch (error) {
                    console.warn("AiUsage: invalid backend output", error);
                }
            }
        }
    }

    // Last result of the backend, for an instant first paint.
    FileView {
        path: `${Paths.cache}/ai-usage/snapshot.json`
        printErrors: false
        onLoaded: {
            if (root.snapshot)
                return;
            try {
                root.snapshot = JSON.parse(text());
            } catch (error) {
                console.warn("AiUsage: invalid cached snapshot", error);
            }
        }
    }

    FileView {
        id: alertsFile

        property bool ready

        path: `${Paths.state}/ai-usage/alerts.json`
        printErrors: false
        onLoaded: {
            try {
                root.alerted = JSON.parse(text()) ?? {};
            } catch (error) {
                root.alerted = {};
            }
            ready = true;
        }
        onLoadFailed: ready = true
    }

    Timer {
        interval: Tokens.sizes.aiUsage.refreshInterval
        running: root.refCount > 0
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Timer {
        interval: Tokens.sizes.aiUsage.backgroundInterval
        running: root.refCount === 0
        repeat: true
        onTriggered: root.refresh()
    }

    // First refresh soon after start, once the session has settled.
    Timer {
        interval: Tokens.sizes.aiUsage.refreshInterval / 12
        running: true
        onTriggered: root.refresh()
    }
}
