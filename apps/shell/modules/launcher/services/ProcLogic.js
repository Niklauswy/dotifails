.pragma library

// Figures for the launcher's process pane (ProcessPane.qml) from `ps -eo pid=,ppid=,cputimes=,rss=,comm=` (the third
// column is cumulative CPU seconds; withRates() turns two samples into % of one core, since ps' own pcpu is a
// lifetime average):
// a program's CPU (% of one core), memory and process count, summed over the windows' process trees or over the
// processes with one name. Tested with node (tests/shell_bridge/test_launcher_processes.py).

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

// The processes of the trees rooted at `pids`: {cpu, memory (bytes), count}.
function aggregate(table, pids) {
    var children = {};
    Object.keys(table).forEach(function (k) {
        var p = table[k];
        (children[p.ppid] = children[p.ppid] || []).push(p.pid);
    });
    var seen = {}, stack = (pids || []).slice(), cpu = 0, rss = 0, count = 0;
    while (stack.length) {
        var pid = stack.pop();
        if (seen[pid] || !table[pid])
            continue;
        seen[pid] = true;
        cpu += table[pid].cpu;
        rss += table[pid].rss;
        count++;
        (children[pid] || []).forEach(function (c) { stack.push(c); });
    }
    return {cpu: Math.round(cpu * 10) / 10, memory: rss * 1024, count: count};
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

function pushSample(history, value) {
    var next = (history || []).concat([value]);
    return next.length > HISTORY ? next.slice(next.length - HISTORY) : next;
}
