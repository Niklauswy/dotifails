.pragma library

// Pure helpers for the launcher's translator (";" prefix): query parsing, direction guess,
// request URLs and response parsing. Network and state live in Translator.qml.

var LANGS = {
    es: "Spanish", en: "English", fr: "French", de: "German", pt: "Portuguese", it: "Italian",
    ja: "Japanese", zh: "Chinese", ko: "Korean", ru: "Russian", ar: "Arabic", nl: "Dutch",
    pl: "Polish", tr: "Turkish", sv: "Swedish", uk: "Ukrainian", ca: "Catalan", la: "Latin"
};

// "en hola" -> translate "hola" into English; anything else leaves the direction to guessTarget().
function splitQuery(rest) {
    var text = rest.trim();
    var m = /^([a-z]{2})\s+(\S[\s\S]*)$/i.exec(text);
    if (m && LANGS[m[1].toLowerCase()])
        return {target: m[1].toLowerCase(), text: m[2].trim()};
    return {target: "", text: text};
}

var SPANISH = ["de", "la", "el", "que", "los", "las", "un", "una", "por", "para", "con", "como", "es", "en", "y", "se", "qué", "cómo", "donde", "dónde", "hola", "gracias", "quiero", "necesito", "tengo", "está", "estoy", "muy", "pero", "más", "del", "al", "mi", "tu", "lo", "no", "sí", "cuál", "cuánto", "buenas", "días", "noches"];
var ENGLISH = ["the", "and", "is", "are", "you", "i", "to", "of", "in", "it", "that", "for", "with", "this", "have", "what", "how", "where", "hello", "thanks", "please", "my", "your", "not", "can", "do", "does", "was", "be", "on", "at", "good", "morning"];

// Spanish text goes to English; everything else to Spanish.
function guessTarget(text) {
    var words = text.toLowerCase().split(/[^a-záéíóúüñ]+/).filter(Boolean);
    var es = /[áéíóúñ¿¡]/i.test(text) ? 2 : 0, en = 0;
    words.forEach(function (w) {
        if (SPANISH.indexOf(w) >= 0)
            es++;
        if (ENGLISH.indexOf(w) >= 0)
            en++;
    });
    return es > en ? "en" : "es";
}

function otherTarget(target) {
    return target === "es" ? "en" : "es";
}

function languageName(code) {
    return LANGS[code] || (code ? code.toUpperCase() : "");
}

function googleUrl(text, target) {
    return "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=" + encodeURIComponent(target) + "&q=" + encodeURIComponent(text);
}

// MyMemory has no auto-detect for every pair, so it is the fallback with a guessed source.
function memoryUrl(text, source, target) {
    return "https://api.mymemory.translated.net/get?q=" + encodeURIComponent(text) + "&langpair=" + encodeURIComponent(source + "|" + target);
}

// [["texto","en"]] (or a bare ["texto"]) -> {text, from}
function parseGoogle(body) {
    var data = JSON.parse(body);
    var head = Array.isArray(data) ? data[0] : null;
    if (Array.isArray(head))
        return {text: String(head[0] || ""), from: String(head[1] || "")};
    if (typeof head === "string")
        return {text: head, from: ""};
    throw new Error("unexpected response");
}

function parseMemory(body) {
    var data = JSON.parse(body);
    var text = data && data.responseData && data.responseData.translatedText;
    if (!text || Number(data.responseStatus) !== 200)
        throw new Error("no translation");
    return {text: String(text), from: ""};
}

function openUrl(text, target) {
    return "https://translate.google.com/?sl=auto&tl=" + encodeURIComponent(target || guessTarget(text)) + "&text=" + encodeURIComponent(text) + "&op=translate";
}

// translate.google.com's app endpoint: besides the text it carries other ways to say it and, for a
// single word, meanings by part of speech. Tried first; googleUrl() is the plainer fallback.
function atUrl(text, target) {
    return "https://translate.google.com/translate_a/single?client=at&sl=auto&tl=" + encodeURIComponent(target)
        + "&dt=t&dt=at&dt=bd&q=" + encodeURIComponent(text);
}

function sameText(a, b) {
    return a.trim().toLowerCase().replace(/[.!?¿¡]+/g, "") === b.trim().toLowerCase().replace(/[.!?¿¡]+/g, "");
}

// -> {text, from, alternatives: [best first], meanings: [{pos, words}]}
function parseAt(body) {
    var d = JSON.parse(body);
    if (!Array.isArray(d) || !Array.isArray(d[0]))
        throw new Error("unexpected response");
    var text = d[0].map(function (part) { return (part && part[0]) || ""; }).join("");
    if (!text)
        throw new Error("empty translation");
    var alternatives = [];
    // Only a single sentence has alternatives that make sense on their own.
    var segment = Array.isArray(d[5]) && d[5].length === 1 ? d[5][0] : null;
    if (segment && Array.isArray(segment[2])) {
        alternatives = segment[2]
            .map(function (a) { return {text: String(a[0] || ""), score: (a[4] && a[4][0]) || 0}; })
            .filter(function (a) { return a.text && !sameText(a.text, text); })
            .sort(function (x, y) { return y.score - x.score; })
            .map(function (a) { return a.text; });
    }
    var meanings = (Array.isArray(d[1]) ? d[1] : []).map(function (m) {
        return {pos: String(m[0] || ""), words: (m[1] || []).slice(0, 6).filter(function (w) { return !sameText(w, text); })};
    }).filter(function (m) { return m.words.length > 0; });
    return {text: text, from: String(d[2] || ""), alternatives: alternatives.slice(0, 4), meanings: meanings.slice(0, 3)};
}

// Search suggestions: Google's own, or YouTube's.
function suggestUrl(site, query) {
    return "https://suggestqueries.google.com/complete/search?client=firefox&hl=es" + (site === "youtube" ? "&ds=yt" : "") + "&q=" + encodeURIComponent(query);
}

function parseSuggest(body, query) {
    var d = JSON.parse(body);
    if (!Array.isArray(d) || !Array.isArray(d[1]))
        return [];
    return d[1].filter(function (x) { return typeof x === "string" && x && !sameText(x, query); }).slice(0, 8);
}

