// The item an overlay draws in: its explicit host, or the topmost item of its tree (the app root).
.pragma library

function find(item, host, contentItem) {
    if (host)
        return host;
    let top = item;
    while (top.parent && top.parent !== contentItem)
        top = top.parent;
    return top;
}
