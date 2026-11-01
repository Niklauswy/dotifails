.pragma library

// Study mode sessions: pure functions over plain objects, so a session survives JSON (study.json) and a
// shell restart resumes it exactly. Times are epoch milliseconds; durations in minutes.

var MINUTE = 60000;
var RHYTHMS = {25: {focus: 25, brk: 5, long: 15}, 50: {focus: 50, brk: 10, long: 20}, 90: {focus: 90, brk: 20, long: 30}};

function rhythmOf(rhythm) {
    return RHYTHMS[rhythm] || RHYTHMS[25];
}

// null = "Libre": no total, blocks until stopped.
function blockCount(durationMin, rhythm) {
    if (!durationMin)
        return null;
    var r = rhythmOf(rhythm);
    return Math.max(1, Math.round(durationMin / (r.focus + r.brk)));
}

function longBreakAfter(blocks) {
    return blocks && blocks >= 4 ? Math.ceil(blocks / 2) : null;
}

// Break after block `index` (1-based). Free sessions get a long one after every 4th block.
function breakMinutes(index, blocks, rhythm) {
    var r = rhythmOf(rhythm);
    var isLong = blocks === null || blocks === undefined ? index % 4 === 0 : index === longBreakAfter(blocks);
    return isLong ? r.long : r.brk;
}

function summaryLine(durationMin, rhythm) {
    var r = rhythmOf(rhythm), n = blockCount(durationMin, rhythm);
    if (n === null)
        return "Bloques de " + r.focus + " min hasta que pares";
    var text = n + (n > 1 ? " bloques" : " bloque") + " de " + r.focus + " min";
    return longBreakAfter(n) ? text + " · descanso largo a mitad" : text;
}

function copy(s) {
    var out = {};
    for (var k in s)
        out[k] = s[k];
    return out;
}

function start(config, now) {
    var r = rhythmOf(config.rhythm);
    return {
        config: config, blocks: blockCount(config.duration, config.rhythm), block: 1, blocksDone: 0,
        phase: "focus", phaseStart: now, phaseEnd: now + r.focus * MINUTE,
        paused: false, pausedAt: 0, focusMs: 0, distractions: 0, startedAt: now, done: false, hidden: []
    };
}

function isLast(s) {
    return s.blocks !== null && s.block >= s.blocks;
}

// Ends the running focus block at `end` (theoretical end or the moment it is cut short).
function endFocus(s, end, now) {
    s.focusMs += Math.max(0, end - s.phaseStart);
    s.blocksDone += 1;
    if (isLast(s)) {
        s.phase = "done";
        s.done = true;
        s.phaseStart = s.phaseEnd = end;
    } else {
        s.phase = "break";
        s.phaseStart = end;
        s.phaseEnd = (now === undefined ? end : now) + breakMinutes(s.block, s.blocks, s.config.rhythm) * MINUTE;
    }
}

// Advances finished phases. A break never rolls into the next block on its own: it waits in "ready".
function tick(session, now) {
    var s = copy(session);
    if (s.paused || s.done)
        return s;
    if (s.phase === "focus" && now >= s.phaseEnd)
        endFocus(s, s.phaseEnd);
    if (s.phase === "break" && now >= s.phaseEnd)
        s.phase = "ready";
    return s;
}

function startNext(session, now) {
    var s = copy(session);
    if (s.done || (s.phase !== "ready" && s.phase !== "break"))
        return s;
    s.block += 1;
    s.phase = "focus";
    s.paused = false;
    s.phaseStart = now;
    s.phaseEnd = now + rhythmOf(s.config.rhythm).focus * MINUTE;
    return s;
}

function skipToBreak(session, now) {
    var s = copy(session);
    if (s.phase !== "focus" || s.done)
        return s;
    if (s.paused)
        s = resume(s, now);
    endFocus(s, now, now);
    return s;
}

function pause(session, now) {
    var s = copy(session);
    if (!s.paused && !s.done) {
        s.paused = true;
        s.pausedAt = now;
    }
    return s;
}

function resume(session, now) {
    var s = copy(session);
    if (s.paused) {
        var shift = now - s.pausedAt;
        s.phaseStart += shift;
        s.phaseEnd += shift;
        s.paused = false;
        s.pausedAt = 0;
    }
    return s;
}

function stop(session, now) {
    var s = copy(session);
    if (s.done)
        return s;
    if (s.phase === "focus") {
        var at = s.paused ? s.pausedAt : Math.min(now, s.phaseEnd);
        s.focusMs += Math.max(0, at - s.phaseStart);
    }
    s.phase = "done";
    s.done = true;
    s.paused = false;
    return s;
}

function progress(session, now) {
    var at = session.paused ? session.pausedAt : now;
    var span = session.phaseEnd - session.phaseStart;
    if (session.phase === "ready" || session.phase === "done" || span <= 0)
        return 1;
    return Math.max(0, Math.min(1, (at - session.phaseStart) / span));
}

function remainingMin(session, now) {
    var at = session.paused ? session.pausedAt : now;
    return Math.max(0, Math.ceil((session.phaseEnd - at) / MINUTE));
}

function historyRecord(session, now) {
    return {
        start: session.startedAt, end: now, rhythm: session.config.rhythm, blocksDone: session.blocksDone,
        blocksPlanned: session.blocks, focusMin: Math.round(session.focusMs / MINUTE), distractions: session.distractions
    };
}

// Focus minutes per day, Monday to Sunday, of the week containing `now` (local time).
function weekTotals(records, now) {
    var d = new Date(now);
    var monday = new Date(d.getFullYear(), d.getMonth(), d.getDate() - (d.getDay() + 6) % 7).getTime();
    var totals = [0, 0, 0, 0, 0, 0, 0];
    for (var i = 0; i < records.length; i++) {
        var r = records[i], day = new Date(r.start);
        var idx = Math.round((new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime() - monday) / 86400000);
        if (idx >= 0 && idx < 7)
            totals[idx] += r.focusMin || 0;
    }
    return totals;
}
