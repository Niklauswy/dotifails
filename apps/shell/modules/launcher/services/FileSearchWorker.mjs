// Runs FileSearch off the GUI thread: parsing the tree index and scanning it per keystroke take tens
// of milliseconds on tens of thousands of paths, which would otherwise drop frames while typing.
// Messages: {index: text} replaces the index; {q, scope, limit} searches it. Replies carry the query
// they answer so the caller can drop stale ones.
import * as FileSearch from "./FileSearch.mjs";

let index = null;
let last = null;

WorkerScript.onMessage = function (m) {
    if (m.index !== undefined) {
        index = FileSearch.parse(m.index);
        last = null;
        WorkerScript.sendMessage({ready: true});
        return;
    }
    last = FileSearch.search(index, m.q, m.scope, m.limit, last);
    WorkerScript.sendMessage({q: m.q, scope: m.scope, rows: last.rows.map(h => [index.p[h.i], index.d[h.i]])});
};
