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

function icon(path, isDir) {
    if (isDir)
        return "folder";
    const ext = extension(path);
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
        icon: icon(path, isDir), type: isDir ? "Folder" : "File",
        l: name.toLowerCase(), a: path.toLowerCase()
    };
}
