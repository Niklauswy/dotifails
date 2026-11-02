.pragma library

// Pure logic of the AI usage panel: pace, visibility, refresh cadence, staleness, alerts and focus.
// Times are epoch seconds. Tested with node in tests/shell_bridge/test_ai_usage_logic.py.

// Fraction of [start, end) that falls on working days ("5": Mon–Fri, "6": Mon–Sat, else every day).
function workFraction(start, end, now, workDays) {
    const days = workDays === "5" ? 5 : workDays === "6" ? 6 : 7;
    if (days === 7)
        return (now - start) / (end - start);
    const works = t => {
        const day = new Date(t * 1000).getDay(); // 0 Sunday … 6 Saturday
        return day >= 1 && day <= days;
    };
    let total = 0, done = 0;
    for (let t = start; t < end; t += 900) {
        if (!works(t))
            continue;
        total += 900;
        if (t < now)
            done += Math.min(900, now - t);
    }
    return total > 0 ? done / total : (now - start) / (end - start);
}

// null without a reset; {early: true} before 3 % of the window; else the even-use comparison.
function pace(limit, now, workDays) {
    if (!limit || !limit.resetsAt || !limit.windowMinutes)
        return null;
    const span = limit.windowMinutes * 60;
    const start = limit.resetsAt - span;
    const elapsed = (now - start) / span;
    if (elapsed < 0.03)
        return { early: true };
    const weekly = limit.windowMinutes >= 7 * 1440;
    const expected = 100 * Math.min(1, Math.max(0, weekly ? workFraction(start, limit.resetsAt, now, workDays) : elapsed));
    const used = limit.usedPercent;
    const left = limit.resetsAt - now;
    const rate = used / Math.max(1, now - start);
    const runsOutIn = rate > 0 ? (100 - used) / rate : Infinity;
    return {
        expected: expected,
        delta: Math.round(used - expected),
        // Within the hour of the reset counts as lasting: an exactly even pace ends right at it.
        lasts: used < 100 && runsOutIn >= left - 3600,
        runsOutIn: runsOutIn,
        exhausted: used >= 100
    };
}

function severity(usedPercent) {
    return usedPercent >= 90 ? "error" : usedPercent >= 70 ? "warn" : "ok";
}

function visibleAccounts(accounts, hidden, enabledProviders) {
    return (accounts || []).filter(a => !(hidden || []).includes(a.id) && (enabledProviders || []).includes(a.provider));
}

// The signed-in limit with the least left: {account, limit, remaining} or null.
function tightest(accounts) {
    let best = null;
    for (const account of accounts || []) {
        if (account.source === "history")
            continue;
        for (const limit of account.limits || []) {
            const remaining = 100 - limit.usedPercent;
            if (!best || remaining < best.remaining)
                best = { account: account, limit: limit, remaining: remaining };
        }
    }
    return best;
}

// Milliseconds between refreshes; 0 means manual.
function refreshInterval(setting, anyBusy, panelOpen, tokens) {
    if (setting === "manual")
        return 0;
    if (setting === "adaptive" || !setting)
        return anyBusy || panelOpen ? tokens.refreshInterval : tokens.idleInterval;
    const fixed = Number(setting);
    return fixed > 0 ? fixed : tokens.refreshInterval;
}

function isStale(account, now, intervalMs) {
    if (!account)
        return false;
    if (account.error && account.error.kind)
        return true;
    if (!account.updatedAt)
        return false;
    return now - account.updatedAt > Math.max(3 * (intervalMs || 0) / 1000, 900);
}

function mask(account, hidePersonal, index) {
    if (!hidePersonal)
        return { label: account.label, email: account.email || "" };
    const domain = (account.email || "").split("@")[1];
    return { label: "Account " + (index + 1), email: domain ? "••••@" + domain : "" };
}

// Notifications due between two snapshots. `seen` maps keys to states and survives restarts; the caller
// formats the text. Kinds: low, restored, upcoming, expiry. weeklyReset is true when a weekly window rolled over.
function alerts(previous, next, settings, seen, now, threshold) {
    const state = Object.assign({}, seen || {});
    const notify = [];
    let weeklyReset = false;
    for (const account of next || []) {
        if (account.source === "history")
            continue;
        for (const limit of account.limits || []) {
            const prefix = `${account.id}:${limit.id}:`;
            const key = prefix + (limit.resetsAt || "");
            const remaining = Math.round(100 - limit.usedPercent);
            if (remaining <= threshold && !state[key]) {
                state[key] = "low";
                if (settings.notifyLow !== false)
                    notify.push({ kind: "low", key: key, account: account, limit: limit, remaining: remaining });
            }
            for (const old of Object.keys(state)) {
                if (old.startsWith(prefix) && old !== key && state[old] === "low" && remaining > threshold) {
                    state[old] = "restored";
                    if (settings.notifyReset !== false)
                        notify.push({ kind: "restored", key: old, account: account, limit: limit, remaining: remaining });
                }
            }
            if (limit.id === "weekly" && limit.resetsAt && limit.usedPercent < 100 && settings.upcoming !== false) {
                const left = limit.resetsAt - now;
                const stage = left <= 3600 ? "up1" : left <= 86400 ? "up24" : null;
                if (stage && left > 0 && !state[`${key}:${stage}`]) {
                    state[`${key}:up24`] = "done";
                    if (stage === "up1")
                        state[`${key}:up1`] = "done";
                    notify.push({ kind: "upcoming", key: `${key}:${stage}`, account: account, limit: limit, remaining: remaining });
                }
            }
            if (limit.id === "weekly" && previous) {
                const before = (previous.find(a => a.id === account.id)?.limits || []).find(l => l.id === "weekly");
                if (before && before.resetsAt && limit.resetsAt && limit.resetsAt - before.resetsAt > 3600 && before.resetsAt <= now)
                    weeklyReset = true;
            }
        }
        const session = account.session;
        // A sign-in its CLI renews by itself (refresh token) is never worth a notice.
        if (session && !session.renewable && (session.expired || (session.expiresAt && session.expiresAt - now <= 86400))) {
            const key = `${account.id}:session:${session.expiresAt || "expired"}`;
            if (!state[key]) {
                state[key] = "expiry";
                notify.push({ kind: "expiry", key: key, account: account, expired: !!session.expired, expiresAt: session.expiresAt });
            }
        }
    }
    const keys = Object.keys(state);
    for (const old of keys.slice(0, Math.max(0, keys.length - 128)))
        delete state[old];
    return { notify: notify, seen: state, weeklyReset: weeklyReset };
}

// The Hyprland window running an agent: the nearest ancestor that owns exactly one window. A terminal that
// runs every window in one process (ghostty) cannot tell its windows apart: null, never a guess.
function windowForSession(agent, toplevels) {
    for (const pid of agent.windowPids || []) {
        const own = (toplevels || []).filter(t => t.pid === pid);
        if (own.length === 1)
            return own[0].address;
        if (own.length > 1)
            return null;
    }
    return null;
}

// Adds one range of usage across accounts: totals, sessions, and models and projects merged and
// sorted by cost then tokens, with shares of the sum. A model whose price is unknown keeps a null cost.
function aggregateUsage(accounts, range) {
    const totals = { input: 0, cacheRead: 0, cacheWrite: 0, output: 0, processed: 0, cost: 0, savings: 0, unpriced: 0 };
    const models = {};
    const projects = {};
    let sessions = 0;
    let points = 0;
    const merge = (into, key, item, fields) => {
        const known = item.cost !== null && item.cost !== undefined;
        const row = into[key] || (into[key] = Object.assign({}, fields, { tokens: 0, cost: null }));
        row.tokens += item.tokens || 0;
        if (known)
            row.cost = (row.cost || 0) + item.cost;
    };
    for (const account of accounts || []) {
        const usage = account.usage && account.usage[range];
        if (!usage)
            continue;
        for (const field of Object.keys(totals))
            totals[field] += (usage.totals && usage.totals[field]) || 0;
        sessions += usage.sessionCount || 0;
        points = Math.max(points, usage.points || 0);
        for (const m of usage.models || [])
            merge(models, m.model, m, { model: m.model, provider: m.provider });
        for (const p of usage.projects || [])
            merge(projects, p.path || p.name, p, { name: p.name, path: p.path });
    }
    const ranked = rows => Object.values(rows).map(row => Object.assign(row, {
        tokenShare: totals.processed ? row.tokens / totals.processed : 0,
        costShare: totals.cost ? (row.cost || 0) / totals.cost : 0
    })).sort((a, b) => (b.cost || 0) - (a.cost || 0) || b.tokens - a.tokens);
    return { totals, sessions, points, models: ranked(models), projects: ranked(projects) };
}
