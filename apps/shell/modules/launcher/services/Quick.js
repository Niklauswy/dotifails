.pragma library

// Answers the launcher can give on its own, from what was typed: open a link, start a timer, run a
// small developer tool, or quit a hungry app. Pure data in, rows out; the
// panel does the acting (Results.root puts these ahead of the fuzzy matches, like the calculator).

var TLDS = ("com org net io dev app ai co mx es edu gov me tv xyz info us uk de fr it br ar cl pe ca au jp cn ru nl se no fi pl ch " +
    "at be eu tech cloud online site blog wiki gg fm ly sh to cc so id in kr tw hk sg nz za").split(" ");

// A link typed or pasted: a scheme, www., localhost, an address or a domain with a real ending.
// "notes.txt" and "main.py" stay files.
function link(q) {
    if (/\s/.test(q))
        return null;
    if (/^https?:\/\/\S+$/i.test(q))
        return {href: q, label: q.replace(/^https?:\/\//i, "").replace(/\/$/, "")};
    if (/^(localhost|\d{1,3}(?:\.\d{1,3}){3})(:\d+)?(\/\S*)?$/i.test(q))
        return {href: "http://" + q, label: q};
    var m = /^(?:www\.)?((?:[a-z0-9-]+\.)+([a-z]{2,}))(:\d+)?(\/\S*)?$/i.exec(q);
    if (m && (/^www\./i.test(q) || TLDS.indexOf(m[2].toLowerCase()) >= 0))
        return {href: "https://" + q, label: q.replace(/\/$/, "")};
    return null;
}

// "90" is minutes; "45s", "10m", "1h", "1h30m" are explicit. Returns seconds, or 0 when it is not a time.
function duration(text) {
    if (/^\d+$/.test(text))
        return Number(text) * 60;
    var m = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/i.exec(text);
    if (!m || (!m[1] && !m[2] && !m[3]))
        return 0;
    return Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0);
}

function human(seconds) {
    var h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60;
    var out = [];
    if (h)
        out.push(h + " h");
    if (m)
        out.push(m + " min");
    if (s)
        out.push(s + " s");
    return out.join(" ");
}

function clock(date) {
    return ("0" + date.getHours()).slice(-2) + ":" + ("0" + date.getMinutes()).slice(-2);
}

// "timer 10m tea", "in 5m call mom"
function timer(q, now) {
    var m = /^(?:timer|in)\s+(\S+)(?:\s+([\s\S]+))?$/i.exec(q);
    if (!m)
        return null;
    var seconds = duration(m[1]);
    if (!seconds || seconds > 86400)
        return null;
    var label = (m[2] || "").trim();
    var rings = new Date(now + seconds * 1000);
    return {kind: "timer", key: "timer", title: "Timer · " + human(seconds), subtitle: (label ? "“" + label + "” · " : "") + "rings at " + clock(rings),
            icon: "timer", type: "Timer", seconds: seconds, label: label, section: ""};
}

// --- small tools ----------------------------------------------------------------------------------

var B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function utf8(text) {
    var bytes = [];
    var s = unescape(encodeURIComponent(text));
    for (var i = 0; i < s.length; i++)
        bytes.push(s.charCodeAt(i));
    return bytes;
}

function base64(text) {
    var b = utf8(text), out = "";
    for (var i = 0; i < b.length; i += 3) {
        var n = (b[i] << 16) | ((b[i + 1] || 0) << 8) | (b[i + 2] || 0);
        out += B64[(n >> 18) & 63] + B64[(n >> 12) & 63] + (i + 1 < b.length ? B64[(n >> 6) & 63] : "=") + (i + 2 < b.length ? B64[n & 63] : "=");
    }
    return out;
}

function unbase64(text) {
    var clean = text.replace(/[^A-Za-z0-9+\/]/g, "");
    var bytes = "";
    for (var i = 0; i < clean.length; i += 4) {
        var chunk = clean.slice(i, i + 4);
        var n = 0;
        for (var j = 0; j < 4; j++)
            n = (n << 6) | (j < chunk.length ? B64.indexOf(chunk[j]) : 0);
        bytes += String.fromCharCode((n >> 16) & 255);
        if (chunk.length > 2)
            bytes += String.fromCharCode((n >> 8) & 255);
        if (chunk.length > 3)
            bytes += String.fromCharCode(n & 255);
    }
    try {
        return decodeURIComponent(escape(bytes));
    } catch (e) {
        return null;
    }
}

function uuid(random) {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
        var r = Math.floor(random() * 16);
        return (c === "x" ? r : (r & 3) | 8).toString(16);
    });
}

function pad(n) {
    return ("0" + n).slice(-2);
}

function localDate(date) {
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()) + " " + pad(date.getHours()) + ":" + pad(date.getMinutes()) + ":" + pad(date.getSeconds());
}

// A generated value stays put while the same query is on screen; `seed` changes when the launcher reopens.
var uuidSeed = null, uuidValue = "";

function steadyUuid(seed, random) {
    if (seed !== uuidSeed || !uuidValue) {
        uuidSeed = seed;
        uuidValue = uuid(random);
    }
    return uuidValue;
}

function value(id, title, subtitle, icon) {
    return {kind: "value", key: "tool:" + id, title: title, subtitle: subtitle, icon: icon, type: "Copy", value: title, section: ""};
}

// uuid · b64 text · unb64 text · urlenc text · urldec text · ts [epoch|date]
function tools(q, now, random, seed) {
    var m;
    if (/^uuid$/i.test(q))
        return value("uuid", steadyUuid(seed, random), "UUID v4 · Enter copies it", "fingerprint");
    if ((m = /^(?:b64|base64)\s+([\s\S]+)$/i.exec(q)))
        return value("b64", base64(m[1]), "Base64 of “" + m[1].slice(0, 40) + "”", "data_object");
    if ((m = /^(?:unb64|b64d|base64d)\s+([\s\S]+)$/i.exec(q))) {
        var plain = unbase64(m[1]);
        return plain === null ? null : value("unb64", plain, "Decoded from Base64", "data_object");
    }
    if ((m = /^(?:urlenc|urlencode)\s+([\s\S]+)$/i.exec(q)))
        return value("urlenc", encodeURIComponent(m[1]), "URL-encoded", "link");
    if ((m = /^(?:urldec|urldecode)\s+([\s\S]+)$/i.exec(q))) {
        try {
            return value("urldec", decodeURIComponent(m[1]), "URL-decoded", "link");
        } catch (e) {
            return null;
        }
    }
    if ((m = /^(?:ts|timestamp|epoch)(?:\s+([\s\S]+))?$/i.exec(q))) {
        var arg = (m[1] || "").trim();
        if (!arg)
            return value("ts", String(Math.floor(now / 1000)), "Unix time now · " + localDate(new Date(now)), "schedule");
        if (/^\d{9,13}$/.test(arg)) {
            var ms = arg.length > 10 ? Number(arg) : Number(arg) * 1000;
            return value("ts", localDate(new Date(ms)), "Local time of " + arg, "schedule");
        }
        var parsed = Date.parse(arg.replace(" ", "T"));
        return isNaN(parsed) ? null : value("ts", String(Math.floor(parsed / 1000)), "Unix time of " + arg, "schedule");
    }
    return null;
}

// --- quitting apps --------------------------------------------------------------------------------

// Never offered, whatever its CPU: the session itself.
var PROTECTED = ["hyprland", "quickshell", "systemd", "dbus-daemon", "xwayland", "pipewire", "wireplumber", "pipewire-pulse", "login", "sshd", "greetd", "init", "ps", "awk", "sort", "sh", "grep", "head"];

// Lines are "name<TAB>count<TAB>cpu%<TAB>MB" as the panel's `ps` helper prints them.
function killRows(items, wanted) {
    var rows = [];
    (items || []).forEach(function (line) {
        var f = line.split("\t");
        if (f.length < 4 || PROTECTED.indexOf(f[0].toLowerCase()) >= 0)
            return;
        var count = Number(f[1]);
        rows.push({kind: "kill", key: "kill:" + f[0], title: "Quit " + f[0], subtitle: count + (count === 1 ? " process" : " processes") + " · " + f[2] + "% CPU · " + f[3] + " MB",
                   icon: "dangerous", type: "Quit", name: f[0], section: wanted ? "Matching processes" : "Using the most CPU"});
    });
    return rows;
}

// -> rows to show ahead of the fuzzy matches (possibly none). `more.now` and `more.random` are injected
// for tests. Runs on every keystroke, so each check is an anchored match that fails on its first
// characters, and nothing is allocated unless something matched.
function rows(q, more) {
    var out = [];
    var l = link(q);
    if (l)
        out.push({kind: "link", key: "link", title: "Open " + l.label, subtitle: "In your browser", icon: "language", type: "Link", url: l.href, section: ""});
    var now = more.now || Date.now();
    var r = timer(q, now);
    if (r)
        out.push(r);
    r = tools(q, now, more.random || Math.random, more.seed);
    if (r)
        out.push(r);
    return out;
}
