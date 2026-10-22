.pragma library
.import "Search.js" as Search
.import "Calc.js" as Calc
.import "Files.js" as Files

// Pure result builders. `ctx` is a snapshot of the in-memory indexes (apps, commands,
// clipboard, files, usage); nothing here touches processes or the filesystem.

function tag(rows, section) {
    return rows.map(r => Object.assign({}, r, {section}));
}

function appBoost(r) {
    return Math.min(Math.log(1 + (r.freq || 0)) * 25, 120);
}

// Deterministic order: frequency, then name, then key.
function byFrequency(a, b) {
    return (b.freq || 0) - (a.freq || 0) || (a.l < b.l ? -1 : a.l > b.l ? 1 : 0) || (a.key < b.key ? -1 : 1);
}

// Suggestions are frozen while the launcher is open: `snapshot` is the list taken on open.
// Entries are refreshed from live data when still present, but never reordered, added or
// dropped, so transient source updates cannot move what is on screen.
function keepOrder(snapshot, live) {
    const byKey = {};
    live.forEach(r => byKey[r.key] = r);
    return snapshot.map(r => byKey[r.key] ? Object.assign({}, byKey[r.key], {section: "Suggestions", pinned: r.pinned}) : r);
}

function suggestions(ctx) {
    const out = [], seen = {};
    const add = (r, pinned) => {
        if (r && !seen[r.key]) {
            seen[r.key] = true;
            out.push(Object.assign({}, r, {section: "Suggestions", pinned: !!pinned}));
        }
    };
    ctx.pins.forEach(r => add(r, true));
    ctx.apps.filter(r => r.freq > 0).sort(byFrequency).slice(0, ctx.maxApps).forEach(r => add(r));
    ctx.recents.forEach(r => add(r));
    if (out.length < 6) {
        const wanted = ["cmd:clipboard", "cmd:emoji", "cmd:wallpaper", "cmd:files", "cmd:settings"];
        ctx.commands.filter(c => wanted.includes(c.key)).forEach(c => add(c));
    }
    return out.slice(0, 9);
}

function root(query, ctx) {
    const q = query.trim();
    if (!q)
        return suggestions(ctx);
    const ts = Search.terms(q);
    let rows = [];
    const calc = Calc.evaluate(q);
    if (calc)
        rows.push({kind: "calc", key: "calc", title: calc.result, subtitle: calc.expression, icon: "calculate", type: "Calculator", value: calc.value, expression: calc.expression, section: ""});
    const groups = [];
    const group = (name, hits) => {
        if (hits.length)
            groups.push({name, rows: hits.map(h => h.item), top: hits[0].score});
    };
    group("Applications", Search.rankScored(ts, ctx.apps, ctx.maxApps, appBoost));
    group("Commands", Search.rankScored(ts, ctx.commands, 4));
    if (ctx.files.length)
        groups.push({name: "Files", rows: ctx.files.slice(0, 8), top: 350});
    group("Clipboard", Search.rankScored(ts, ctx.clips, 3));
    groups.sort((x, y) => y.top - x.top); // stable: ties keep the order above
    for (const g of groups)
        rows = rows.concat(tag(g.rows, g.name));
    rows.push({kind: "web", key: "web", title: "Search the web for “" + q + "”", subtitle: "DuckDuckGo", icon: "travel_explore", type: "Web", query: q, section: "Fallbacks"});
    rows.push({kind: "run", key: "run", title: "Run “" + q + "” in a terminal", subtitle: "Executes exactly what you typed", icon: "terminal", type: "Terminal", command: q, section: "Fallbacks"});
    return rows;
}

function dayLabel(stamp) {
    const now = new Date(), d = new Date(stamp * 1000);
    const day = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day(now) - day(d)) / 86400000);
    return diff <= 0 ? "Today" : diff === 1 ? "Yesterday" : "Earlier";
}

function filtered(query, list, limit) {
    const q = query.trim();
    return q ? Search.rank(Search.terms(q), list, limit) : list.slice(0, limit);
}

function view(id, query, ctx, target, filter) {
    switch (id) {
    case "clipboard":
        return filtered(query, ctx.clips.filter(r => !filter || filter === "all" || r.clip_kind === filter), 150).map(r => Object.assign({}, r, {section: dayLabel(r.stamp)}));
    case "files":
        const keep = r => !filter || filter === "all" || (filter === "image" ? !r.isDir && Files.isImage(r.path) : r.isDir);
        if (query.trim())
            return tag(ctx.files.filter(keep), "Results");
        return tag(filter && filter !== "all" ? [] : ctx.places, "Places").concat(tag(ctx.recentFiles.filter(keep).slice(0, 40), "Recent Files"));
    case "browse": {
        const keep2 = r => !filter || filter === "all" || (filter === "image" ? !r.isDir && Files.isImage(r.path) : r.isDir);
        const rows = (query.trim() ? Search.rank(Search.terms(query), ctx.browse, 800) : ctx.browse).filter(keep2);
        return tag(rows.filter(r => r.isDir), "Folders").concat(tag(rows.filter(r => !r.isDir), "Files"));
    }
    case "apps": {
        const sorted = query.trim() ? Search.rank(Search.terms(query), ctx.apps, 200, appBoost) : ctx.apps.slice().sort((a, b) => a.l < b.l ? -1 : 1);
        return tag(sorted, "Applications");
    }
    case "openwith":
        return tag(Search.rank(Search.terms(query), ctx.apps, 200, appBoost).map(r => Object.assign({}, r, {kind: "openwith", target})), "Open With");
    case "calc-history":
        return tag(filtered(query, ctx.calcHistory, 100), "History");
    }
    return [];
}

function emptyText(id, query) {
    if (query.trim() && id === "root")
        return "No results for “" + query.trim() + "”";
    return {
        clipboard: "Your next copy starts the history.\nText, images, colours and links.",
        files: query.trim() ? "No files match." : "No recent files.",
        browse: query.trim() ? "Nothing in this folder matches." : "This folder is empty.",
        "calc-history": "Copy a calculator result and it shows up here.",
        apps: "No applications match."
    }[id] || "Nothing here.";
}
