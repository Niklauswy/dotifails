pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun.Config
import Wysun.I18n
import qs.utils
import "AiUsageLogic.js" as Logic

// AI provider accounts, limits, local token usage, service status and running agents
// (modules/aiusage/backend.py). The last result is cached, so the panel paints at once after a
// restart. Settings live in ${Paths.config}/ai-usage.json; hidden accounts and disabled providers
// count for nothing (tabs, totals, bar indicator, alerts). Refresh is adaptive by default: every
// minute while an agent works or the panel is open, every idleInterval otherwise.
Singleton {
    id: root

    property int refCount: 0
    property var snapshot: null
    property string range: "30d"
    property string metric: "cost"
    // Notified windows and stages, kept across restarts.
    property var alerted: ({})
    readonly property bool loading: loader.running

    readonly property var defaults: ({
            showUsed: true,
            absoluteResets: false,
            paceGuide: true,
            workDays: "auto",
            billing: true,
            compact: false,
            hidePersonal: false,
            status: true,
            notifyLow: true,
            notifyReset: true,
            upcoming: true,
            confetti: true,
            refresh: "adaptive",
            indicatorStyle: "meters",
            indicatorFollows: "focused",
            selected: "",
            providers: ({
                    claude: true,
                    codex: true,
                    opencode: true
                }),
            hidden: []
        })
    property var settings: defaults

    readonly property var accounts: snapshot?.accounts ?? []
    readonly property var agents: snapshot?.agents ?? []
    readonly property var status: snapshot?.status ?? ({})
    readonly property var enabledProviders: Object.keys(settings.providers ?? {}).filter(p => settings.providers[p])
    readonly property var visibleAccounts: Logic.visibleAccounts(accounts, settings.hidden, enabledProviders)
    readonly property var visibleAgents: agents.filter(a => enabledProviders.includes(a.provider) && !(settings.hidden ?? []).includes(a.accountId))
    // Providers with at least one visible account, in a stable order.
    readonly property var providers: ["claude", "codex", "opencode"].filter(p => visibleAccounts.some(a => a.provider === p))
    readonly property var tightest: Logic.tightest(visibleAccounts)
    readonly property bool anyBusy: visibleAgents.some(a => a.busy)
    readonly property int interval: Logic.refreshInterval(settings.refresh, anyBusy, refCount > 0, Tokens.sizes.aiUsage)

    // The provider whose agent runs in the focused window; the last one is kept while other windows have focus.
    readonly property string focusedAddress: Hypr.activeToplevel?.address ?? ""
    property string lastFocusedProvider: ""
    readonly property var indicator: Logic.indicatorTarget(visibleAccounts, settings.indicatorFollows, lastFocusedProvider, settings.selected)

    signal weeklyReset

    onFocusedAddressChanged: updateFocus()
    onAgentsChanged: updateFocus()

    function updateFocus(): void {
        const provider = Logic.focusedProvider(visibleAgents, windows(), focusedAddress);
        if (provider)
            lastFocusedProvider = provider;
    }

    function refresh(): void {
        if (!loader.running)
            loader.running = true;
    }

    function account(id: string): var {
        return accounts.find(a => a.id === id) ?? null;
    }

    function tightestOf(provider: string): var {
        return Logic.tightest(providerAccounts(provider));
    }

    function providerName(provider: string): string {
        return provider === "claude" ? "Claude" : provider === "codex" ? "Codex" : provider === "opencode" ? "OpenCode" : provider;
    }

    function providerAccounts(provider: string): var {
        return visibleAccounts.filter(a => a.provider === provider);
    }

    function colour(id: string): color {
        return Colours.palette.m3primary;
    }

    // Colour of a used share: error when almost spent, tertiary (Wysun's warning) when getting there.
    function severityColour(usedPercent: real): color {
        const level = Logic.severity(usedPercent);
        return level === "error" ? Colours.palette.m3error : level === "warn" ? Colours.palette.m3tertiary : Colours.palette.m3primary;
    }

    function pace(limit: var): var {
        return Logic.pace(limit, Date.now() / 1000, settings.workDays);
    }

    function isStale(account: var): bool {
        return Logic.isStale(account, Date.now() / 1000, interval || Tokens.sizes.aiUsage.idleInterval);
    }

    function names(account: var): var {
        const index = accounts.filter(a => a.provider === account.provider).indexOf(account);
        return Logic.mask(account, settings.hidePersonal, Math.max(0, index));
    }

    function limitTitle(limit: var): string {
        if (limit.label)
            return limit.label;
        if (limit.id === "session")
            return Tr.tr("Session");
        if (limit.id === "weekly")
            return Tr.tr("Weekly");
        if (limit.id === "monthly")
            return Tr.tr("Monthly");
        return limit.id.replace(/^weekly_/, "");
    }

    function limitName(limit: var): string {
        if (limit.id === "session")
            return Tr.tr("session limit");
        if (limit.id === "weekly")
            return Tr.tr("weekly limit");
        if (limit.id === "monthly")
            return Tr.tr("monthly limit");
        // TRANSLATORS: %1 = a model family with its own weekly limit, such as "Opus"
        return Tr.tr("%1 weekly limit").arg(limit.label ?? limit.id.replace(/^weekly_/, ""));
    }

    function setSetting(key: string, value: var): void {
        const next = Object.assign({}, settings);
        next[key] = value;
        settings = next;
        prefsFile.setText(JSON.stringify(next, null, 2));
    }

    function setProvider(provider: string, on: bool): void {
        const providers = Object.assign({}, settings.providers);
        providers[provider] = on;
        setSetting("providers", providers);
    }

    function setHidden(id: string, hide: bool): void {
        const hidden = (settings.hidden ?? []).filter(h => h !== id);
        if (hide)
            hidden.push(id);
        setSetting("hidden", hidden);
    }

    function notify(title: string, body: string, urgency: string): void {
        Quickshell.execDetached(["notify-send", "-a", "Wysun", "-u", urgency, "-i", "utilities-system-monitor", title, body]);
    }

    function resetText(resetsAt: var): string {
        return resetsAt ? Qt.formatDateTime(new Date(resetsAt * 1000), "ddd hh:mm") : "";
    }

    function alertText(item: var): var {
        const who = names(item.account);
        const title = `${item.account.providerName} · ${who.label}`;
        if (item.kind === "low") {
            const reset = resetText(item.limit.resetsAt);
            // TRANSLATORS: %1 = percent left, %2 = limit name such as "weekly limit"
            return [title, Tr.tr("%1% of the %2 left.").arg(item.remaining).arg(limitName(item.limit)) + (reset ? " " + Tr.tr("Resets %1.").arg(reset) : ""), item.remaining <= Tokens.sizes.aiUsage.alertThreshold / 2 ? "critical" : "normal"];
        }
        if (item.kind === "restored")
            return [title, Tr.tr("The %1 has reset.").arg(limitName(item.limit)), "low"];
        if (item.kind === "upcoming")
            // TRANSLATORS: %1 = limit name, %2 = reset time, %3 = percent still unused
            return [title, Tr.tr("The %1 resets %2 with %3% unused.").arg(limitName(item.limit)).arg(resetText(item.limit.resetsAt)).arg(item.remaining), "normal"];
        const command = item.account.provider === "opencode" ? "opencode auth login" : "claude";
        return [title, item.expired ? Tr.tr("The sign-in has expired. Run %1 to sign in again.").arg(command) : Tr.tr("The sign-in expires %1. Open %2 to renew it.").arg(resetText(item.expiresAt)).arg(command), "normal"];
    }

    function checkAlerts(previous: var, next: var): void {
        const visible = list => list ? Logic.visibleAccounts(list.accounts ?? [], settings.hidden, enabledProviders) : null;
        const result = Logic.alerts(visible(previous), visible(next), settings, alerted, Date.now() / 1000, Tokens.sizes.aiUsage.alertThreshold);
        for (const item of result.notify) {
            const text = alertText(item);
            notify(text[0], text[1], text[2]);
        }
        if (result.weeklyReset && settings.confetti)
            weeklyReset();
        if (JSON.stringify(result.seen) !== JSON.stringify(alerted)) {
            alerted = result.seen;
            alertsFile.setText(JSON.stringify(result.seen));
        }
    }

    function apply(next: var): void {
        const previous = snapshot;
        snapshot = next;
        if (alertsFile.ready)
            checkAlerts(previous, next);
    }

    // Opens a command in Wysun's terminal (same choice as wysun-terminal: ghostty, else foot).
    function openTerminal(argv: var): void {
        Quickshell.execDetached(["sh", "-c", 'if command -v ghostty >/dev/null 2>&1; then exec ghostty -e "$@"; else exec foot "$@"; fi', "sh"].concat(argv));
    }

    function windows(): var {
        return Hypr.toplevels.values.map(t => ({
                    pid: t.lastIpcObject?.pid ?? 0,
                    address: t.address,
                    title: t.title ?? ""
                }));
    }

    // Window of a running agent, or "" when it cannot be told apart.
    function sessionWindow(agent: var): string {
        return Logic.windowForSession(agent, windows()) ?? "";
    }

    function focusSession(agent: var): bool {
        const address = sessionWindow(agent);
        if (!address)
            return false;
        Hypr.dispatch(Hypr.usingLua ? `hl.dsp.focus({window="address:0x${address}"})` : `focuswindow address:0x${address}`);
        return true;
    }

    // Creates the folder of a new account (backend.py --prepare-account) and opens the provider's own sign-in.
    function addAccount(provider: string): void {
        prepare.provider = provider;
        prepare.running = true;
    }

    Process {
        id: prepare

        property string provider

        command: ["python3", "-I", Quickshell.shellPath("modules/aiusage/backend.py"), "--prepare-account", provider]
        stdout: StdioCollector {
            onStreamFinished: {
                const folder = text.trim();
                if (prepare.provider === "claude" && folder)
                    root.openTerminal(["env", `CLAUDE_CONFIG_DIR=${folder}`, "claude"]);
                else if (prepare.provider === "codex" && folder)
                    root.openTerminal(["env", `CODEX_HOME=${folder}`, "codex", "login"]);
                else if (prepare.provider === "opencode")
                    root.openTerminal(["opencode", "auth", "login"]);
            }
        }
    }

    Process {
        id: loader

        command: ["python3", "-I", Quickshell.shellPath("modules/aiusage/backend.py")].concat(root.settings.status ? [] : ["--no-status"])
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
        id: prefsFile

        path: `${Paths.config}/ai-usage.json`
        printErrors: false
        onLoaded: {
            try {
                root.settings = Object.assign({}, root.defaults, JSON.parse(text()));
            } catch (error) {
                root.settings = root.defaults;
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

    // Opening the panel always refreshes, also in manual mode.
    onRefCountChanged: {
        if (refCount > 0)
            refresh();
    }

    Timer {
        interval: Math.max(1000, root.interval)
        running: root.interval > 0
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
