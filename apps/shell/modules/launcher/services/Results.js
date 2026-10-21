.pragma library
.import "Search.js" as Search
.import "Calc.js" as Calc
.import "Files.js" as Files

// Pure result builders. `ctx` is a snapshot of the in-memory indexes (apps, commands, windows,
// clipboard, snippets, files, usage); nothing here touches processes or the filesystem.

function tag(rows, section) {
    return rows.map(r => Object.assign({}, r, {section}));
}

function appBoost(r) {
    return Math.min(Math.log(1 + (r.freq || 0)) * 25, 120);
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
    ctx.apps.filter(r => r.freq > 0).sort((a, b) => b.freq - a.freq).slice(0, ctx.maxApps).forEach(r => add(r));
    ctx.recents.forEach(r => add(r));
    if (out.length < 6) {
        const wanted = ["cmd:clipboard", "cmd:emoji", "cmd:windows", "cmd:wallpaper", "cmd:files", "cmd:system"];
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
    group("Windows", Search.rankScored(ts, ctx.windows, 3));
    if (ctx.files.length)
        groups.push({name: "Files", rows: ctx.files.slice(0, 8), top: 350});
    group("Clipboard", Search.rankScored(ts, ctx.clips, 3));
    group("Snippets", Search.rankScored(ts, ctx.snippets, 3));
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
    case "snippets": {
        const create = {kind: "cmd", key: "snippet-new", title: "Create Snippet", subtitle: "Name, abbreviation and text", icon: "add", type: "Action", form: "snippet", section: "Snippets"};
        return [create].concat(tag(filtered(query, ctx.snippets, 100), "Snippets"));
    }
    case "windows":
        return tag(filtered(query, ctx.windows, 100), "Open Windows");
    case "files":
        const keep = r => !filter || filter === "all" || (filter === "image" ? !r.isDir && Files.isImage(r.path) : r.isDir);
        return query.trim() ? tag(ctx.files.filter(keep), "Results") : tag(ctx.recentFiles.filter(keep).slice(0, 40), "Recent Files");
    case "apps": {
        const sorted = query.trim() ? Search.rank(Search.terms(query), ctx.apps, 200, appBoost) : ctx.apps.slice().sort((a, b) => a.l < b.l ? -1 : 1);
        return tag(sorted, "Applications");
    }
    case "openwith":
        return tag(Search.rank(Search.terms(query), ctx.apps, 200, appBoost).map(r => Object.assign({}, r, {kind: "openwith", target})), "Open With");
    case "system":
        return tag(filtered(query, ctx.systemCommands, 20), "System");
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
        snippets: "No snippets yet.\nPress Enter on Create Snippet to add one.",
        windows: "No open windows match.",
        files: query.trim() ? "No files match." : "No recent files.",
        "calc-history": "Copy a calculator result and it shows up here.",
        apps: "No applications match."
    }[id] || "Nothing here.";
}
