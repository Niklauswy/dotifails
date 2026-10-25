pragma Singleton

import QtQuick
import Quickshell
import Wysun
import "Translate.js" as Translate

// Live translation for the ";" prefix. The panel calls ask() on every query change: typing is
// debounced, answers are cached, and a late reply for an older query is ignored.
// state: "idle" | "waiting" (debounce) | "loading" | "done" | "error"
Singleton {
    id: root

    property string text
    // Language asked for with ";en …"; empty lets the text decide the direction.
    property string wanted
    property string state: "idle"
    property string result
    property string from
    property string target
    property string fault
    // Other ways to say it and, for one word, its meanings by part of speech; they belong to `answered`.
    property var variants: []
    property var meanings: []
    property string answered

    readonly property bool busy: state === "waiting" || state === "loading"

    property int serial
    property var cache: ({})

    function ask(query: string, language: string): void {
        if (query === text && language === wanted)
            return;
        text = query;
        wanted = language;
        serial++;
        if (!query) {
            clear();
            return;
        }
        target = language || Translate.guessTarget(query);
        const hit = cache[key(query, language)];
        if (hit) {
            finish(hit);
            return;
        }
        fault = "";
        state = "waiting";
        debounce.restart();
    }

    function clear(): void {
        if (state === "idle" && !text)
            return;
        debounce.stop();
        text = "";
        wanted = "";
        state = "idle";
        result = "";
        from = "";
        fault = "";
        variants = [];
        meanings = [];
        answered = "";
        serial++;
    }

    function key(query: string, language: string): string {
        return `${language}|${query}`;
    }

    function finish(hit: var): void {
        result = hit.text;
        from = hit.from;
        target = hit.target;
        variants = hit.alternatives ?? [];
        meanings = hit.meanings ?? [];
        answered = text;
        state = "done";
    }

    function fail(why: string): void {
        fault = why;
        state = "error";
    }

    function store(hit: var, lang: string, asked: string, query: string): void {
        hit.target = lang;
        cache[key(query, asked)] = hit;
        finish(hit);
    }

    // Google's app endpoint first (it carries alternatives); text already in the target language
    // goes the other way (Spanish stays Spanish → English).
    function request(language: string, flipped: bool): void {
        const id = serial, query = text, asked = wanted;
        const lang = flipped ? Translate.otherTarget(language) : language;
        state = "loading";
        Requests.get(Translate.atUrl(query, lang), body => {
            if (id !== serial)
                return;
            let hit;
            try {
                hit = Translate.parseAt(body);
            } catch (error) {
                plain(id, query, asked, lang);
                return;
            }
            if (!flipped && !asked && hit.from && hit.from === lang) {
                request(language, true);
                return;
            }
            store(hit, lang, asked, query);
        }, () => {
            if (id === serial)
                plain(id, query, asked, lang);
        }, {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"});
    }

    // The extension endpoint: no alternatives, but it rarely refuses.
    function plain(id: int, query: string, asked: string, lang: string): void {
        Requests.get(Translate.googleUrl(query, lang), body => {
            if (id !== serial)
                return;
            try {
                store(Translate.parseGoogle(body), lang, asked, query);
            } catch (error) {
                fallback(id, query, asked, lang);
            }
        }, () => {
            if (id === serial)
                fallback(id, query, asked, lang);
        }, {"User-Agent": "Mozilla/5.0"});
    }

    // Google refused or failed: MyMemory with the opposite language as the guessed source.
    function fallback(id: int, query: string, asked: string, lang: string): void {
        Requests.get(Translate.memoryUrl(query, Translate.otherTarget(lang), lang), body => {
            if (id !== serial)
                return;
            try {
                store(Translate.parseMemory(body), lang, asked, query);
            } catch (error) {
                fail("No translation came back");
            }
        }, () => {
            if (id === serial)
                fail("No connection");
        });
    }

    Timer {
        id: debounce

        interval: 320
        onTriggered: root.request(root.target, false)
    }
}
