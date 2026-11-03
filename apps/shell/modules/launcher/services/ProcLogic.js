.pragma library

// Figures for the launcher's process pane (ProcessPane.qml) from `ps -eo pid=,ppid=,cputimes=,rss=,comm=` (the third
// column is cumulative CPU seconds; withRates() turns two samples into % of one core, since ps' own pcpu is a
// lifetime average):
// a program's CPU (% of one core), memory and process count, summed over the windows' process trees or over the
// processes with one name, and the pids to signal when closing one of those trees. Tested with node
// (tests/shell_bridge/test_launcher_processes.py).

var HISTORY = 60;

function parsePs(text) {
    var table = {};
    String(text || "").split("\n").forEach(function (line) {
        var m = /^\s*(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(.*)$/.exec(line);
        if (m)
            table[m[1]] = {pid: +m[1], ppid: +m[2], cpu: +m[3], rss: +m[4], comm: m[5]};
    });
    return table;
}

// Calls `visit(pid)` once for every process of the trees rooted at `pids`, children of a pid coming from `table`.
function walkTrees(table, pids, visit) {
    var children = {};
    Object.keys(table).forEach(function (k) {
        var p = table[k];
        (children[p.ppid] = children[p.ppid] || []).push(p.pid);
    });
    var seen = {}, stack = (pids || []).slice();
    while (stack.length) {
        var pid = stack.pop();
        if (seen[pid] || !table[pid])
            continue;
        seen[pid] = true;
        visit(pid);
        (children[pid] || []).forEach(function (c) { stack.push(c); });
    }
}

function isProtected(comm, protectedNames) {
    var name = String(comm || "").toLowerCase();
    return (protectedNames || []).some(function (p) { return String(p).toLowerCase() === name; });
}

// The processes of the trees rooted at `pids`: {cpu, memory (bytes), count}.
function aggregate(table, pids) {
    var cpu = 0, rss = 0, count = 0;
    walkTrees(table, pids, function (pid) {
        cpu += table[pid].cpu;
        rss += table[pid].rss;
        count++;
    });
    return {cpu: Math.round(cpu * 10) / 10, memory: rss * 1024, count: count};
}

// Pids of the trees rooted at `rootPids` that are not in `windowPids` (the pids that own the app's windows), never
// a PROTECTED name nor init: the ones to SIGTERM after closing a running app's windows.
function windowlessPids(table, rootPids, windowPids, protectedNames) {
    var windows = {}, out = [];
    (windowPids || []).forEach(function (pid) { windows[pid] = true; });
    walkTrees(table, rootPids, function (pid) {
        if (pid > 1 && !windows[pid] && !isProtected(table[pid].comm, protectedNames))
            out.push(pid);
    });
    return out;
}

// The whole trees rooted at `rootPids`, windows included, never a PROTECTED name nor init: the SIGKILL set.
function treePids(table, rootPids, protectedNames) {
    return windowlessPids(table, rootPids, [], protectedNames);
}

function byName(table, name) {
    var pids = Object.keys(table).filter(function (k) { return table[k].comm === name; }).map(Number);
    var sum = {cpu: 0, memory: 0, count: pids.length, pids: pids};
    pids.forEach(function (p) {
        sum.cpu += table[p].cpu;
        sum.memory += table[p].rss * 1024;
    });
    sum.cpu = Math.round(sum.cpu * 10) / 10;
    return sum;
}

// `cur` with each process' cpu as % of one core between `prev` and `cur` (`seconds` apart); new processes 0.
function withRates(cur, prev, seconds) {
    var out = {};
    Object.keys(cur).forEach(function (k) {
        var p = cur[k], old = prev ? prev[k] : null;
        var rate = old && seconds > 0 && old.comm === p.comm ? Math.max(0, (p.cpu - old.cpu) / seconds * 100) : 0;
        out[k] = {pid: p.pid, ppid: p.ppid, cpu: rate, total: p.cpu, rss: p.rss, comm: p.comm};
    });
    return out;
}

// True while a sample taken at `stamp` (seconds) is at most `maxAge` seconds old at `now`: a stale table may
// describe pids that have since been reused.
function isFresh(stamp, now, maxAge) {
    return stamp > 0 && now - stamp <= maxAge;
}

function pushSample(history, value) {
    var next = (history || []).concat([value]);
    return next.length > HISTORY ? next.slice(next.length - HISTORY) : next;
}
