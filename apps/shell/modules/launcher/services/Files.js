.pragma library

const IMAGES = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "avif", "svg", "ico"];
const ICONS = {
    video: ["mp4", "mkv", "webm", "mov", "avi"], audio: ["mp3", "flac", "ogg", "wav", "m4a", "opus"],
    picture_as_pdf: ["pdf"], folder_zip: ["zip", "tar", "gz", "xz", "7z", "rar", "zst"],
    code: ["py", "js", "ts", "qml", "cpp", "c", "h", "rs", "go", "java", "sh", "lua", "json", "html", "css"],
    description: ["txt", "md", "log", "csv", "toml", "yaml", "yml", "ini", "conf"],
    slideshow: ["pptx", "odp"], table_chart: ["xlsx", "ods"], article: ["doc", "docx", "odt", "tex"]
};
const MATERIAL = {video: "movie", audio: "music_note"};

function extension(path) {
    const name = path.slice(path.lastIndexOf("/") + 1);
    const dot = name.lastIndexOf(".");
    return dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
}

function isImage(path) {
    return IMAGES.includes(extension(path));
}

// Backup/variant suffixes that hide the real type: `init.lua.bak`, `hyprland.lua.bak-20261021`, `notes.md~`, `a.conf.old`.
const BACKUP_SUFFIX = /^(bak|backup|bkp|backed|orig|old|save|saved|swp|tmp|new|rej|dist|disabled|bak[-_.].*|backup[-_.].*|old[-_.].*|orig[-_.].*|[0-9]+)$/;

function baseName(path) {
    return path.slice(path.lastIndexOf("/") + 1);
}

// The name with backup suffixes removed, so a backup is judged by what it is a backup of.
function logicalName(path) {
    let name = baseName(path);
    for (;;) {
        const dot = name.lastIndexOf(".");
        if (name.length > 1 && name.endsWith("~"))
            name = name.slice(0, -1);
        else if (dot > 0 && BACKUP_SUFFIX.test(name.slice(dot + 1).toLowerCase()))
            name = name.slice(0, dot);
        else
            return name;
    }
}

function isDotfile(path) {
    const name = logicalName(path);
    return name.length > 1 && name[0] === "." && extension(name) === "";
}

// Everything that is not clearly binary opens in Neovim: unknown extensions, no extension, dotfiles, backups.
const NOT_TEXT = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "avif", "heic", "tif", "tiff", "ico", "psd", "xcf", "kra", "blend",
    "mp4", "mkv", "webm", "mov", "avi", "m4v", "mpg", "mpeg", "mp3", "flac", "ogg", "opus", "wav", "m4a", "aac",
    "pdf", "doc", "docx", "odt", "xls", "xlsx", "ods", "ppt", "pptx", "odp", "epub", "mobi", "djvu",
    "zip", "tar", "gz", "xz", "bz2", "7z", "rar", "zst", "tgz", "lz4", "iso", "img", "dmg", "deb", "rpm", "apk", "appimage", "jar", "war",
    "exe", "dll", "so", "o", "a", "bin", "class", "pyc", "wasm", "ttf", "otf", "woff", "woff2",
    "db", "sqlite", "sqlite3", "mdb", "parquet", "npy", "pkl", "pickle", "mo", "qm", "lock-wal", "swp"];

function isEditable(path) {
    return !NOT_TEXT.includes(extension(logicalName(path)));
}

function icon(path, isDir) {
    if (isDir)
        return "folder";
    const name = logicalName(path);
    if (isDotfile(path) || extension(name) === "")
        return "code";
    const ext = extension(name);
    if (IMAGES.includes(ext))
        return "image";
    for (const k in ICONS)
        if (ICONS[k].includes(ext))
            return MATERIAL[k] || k;
    return "draft";
}

function row(path, isDir, home) {
    const slash = path.lastIndexOf("/");
    const name = path.slice(slash + 1) || path;
    const dir = path.slice(0, slash) || "/";
    return {
        kind: "file", key: "file:" + path, path, isDir, title: name,
        subtitle: home && dir.startsWith(home) ? "~" + dir.slice(home.length) : dir,
        icon: icon(path, isDir), type: isDir ? "Folder" : "File", editable: !isDir && isEditable(path),
        l: name.toLowerCase(), a: path.toLowerCase()
    };
}
