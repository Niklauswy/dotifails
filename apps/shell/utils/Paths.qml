// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Base: 6c70d5cb0cbf31413d300699540c858ad28c1539; véanse LICENSE y UPSTREAM.json.
pragma Singleton

import QtQuick
import Quickshell
import Wysun
import Wysun.Config

Singleton {
    id: root

    readonly property string home: Quickshell.env("HOME")
    readonly property string pictures: Quickshell.env("XDG_PICTURES_DIR") || `${home}/Pictures`
    readonly property string videos: Quickshell.env("XDG_VIDEOS_DIR") || `${home}/Videos`

    readonly property string data: `${Quickshell.env("XDG_DATA_HOME") || `${home}/.local/share`}/wysun`
    readonly property string state: `${Quickshell.env("XDG_STATE_HOME") || `${home}/.local/state`}/wysun`
    readonly property string cache: `${Quickshell.env("XDG_CACHE_HOME") || `${home}/.cache`}/wysun`
    readonly property string config: `${Quickshell.env("XDG_CONFIG_HOME") || `${home}/.config`}/wysun`

    readonly property string imagecache: `${cache}/imagecache`
    readonly property string notifimagecache: `${imagecache}/notifs`
    readonly property string wallsdir: Quickshell.env("WYSUN_WALLPAPERS_DIR") || absolutePath(GlobalConfig.paths.wallpaperDir)
    readonly property string recsdir: Quickshell.env("WYSUN_RECORDINGS_DIR") || `${videos}/Recordings`
    readonly property string libdir: Quickshell.env("WYSUN_LIB_DIR") || "/usr/lib/wysun"

    function toLocalFile(path: url): string {
        path = Qt.resolvedUrl(path);
        return path.toString() ? CUtils.toLocalFile(path) : "";
    }

    function absolutePath(path: string): string {
        return toLocalFile(path.replace(/~|(\$({?)HOME(}?))+/, home));
    }

    function shortenHome(path: string): string {
        return path.replace(home, "~");
    }
}
