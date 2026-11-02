// The control bar's menus as WysunM3 Menu models: speed, subtitles, audio track and «more» (its entries depend on
// the kind of file and on whether the bar is compact), and what each entry does.
import QtQuick

QtObject {
    id: root

    property var player
    property var image
    property bool compact
    readonly property var speeds: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4]

    signal submenu(string which)
    signal infoRequested

    function clock(seconds) {
        const s = Math.max(0, Math.floor(seconds || 0));
        const m = Math.floor(s / 60), r = s % 60;
        return m + ":" + (r < 10 ? "0" : "") + r;
    }

    function checkIcon(on) {
        return on ? "check" : "";
    }

    function model(which) {
        const p = player;
        if (which === "speed")
            return speeds.map(s => ({
                        id: "speed:" + s,
                        text: s + "×" + (s === 1 ? " · Normal" : ""),
                        icon: checkIcon(Math.abs(p.speed - s) < 0.001)
                    }));
        if (which === "subtitles") {
            const tracks = p.subtitleTracks;
            const delay = (p.subDelay >= 0 ? "+" : "") + p.subDelay.toFixed(1).replace(".", ",") + " s";
            return [{
                    id: "sub:-1",
                    text: "Desactivados",
                    icon: checkIcon(!tracks.some(t => t.selected))
                }].concat(tracks.map(t => ({
                        id: "sub:" + t.id,
                        text: t.label,
                        icon: checkIcon(t.selected)
                    })), [{divider: true}, {
                    id: "subfile",
                    text: "Cargar archivo…",
                    icon: "folder_open"
                }, {
                    id: "subearlier",
                    text: "Adelantar 0,1 s",
                    shortcut: delay,
                    disabled: tracks.length === 0
                }, {
                    id: "sublater",
                    text: "Retrasar 0,1 s",
                    disabled: tracks.length === 0
                }]);
        }
        if (which === "audio")
            return p.audioTracks.map(t => ({
                        id: "audio:" + t.id,
                        text: t.label,
                        icon: checkIcon(t.selected),
                        shortcut: t.detail
                    }));
        // more
        const entries = [{
                id: "info",
                text: "Información",
                icon: "info",
                shortcut: "I"
            }];
        if (p.kindName === "video" || p.kindName === "audio") {
            const ab = p.abLoop;
            const state = ab.length === 0 ? "desactivado" : ab.length === 1 ? "marcando B" : clock(ab[0]) + "–" + clock(ab[1]);
            entries.push({
                id: "loop",
                text: "Bucle del archivo",
                icon: checkIcon(p.looping),
                shortcut: "Mayús+L"
            }, {
                id: "ab",
                text: "Bucle A-B · " + state,
                shortcut: "L"
            });
            if (p.kindName === "video") {
                const paused = p.state !== "playing";
                entries.push({
                    id: "prevframe",
                    text: "Fotograma anterior",
                    shortcut: ",",
                    disabled: !paused
                }, {
                    id: "nextframe",
                    text: "Fotograma siguiente",
                    shortcut: ".",
                    disabled: !paused
                }, {
                    id: "saveframe",
                    text: "Guardar fotograma",
                    icon: "photo_camera",
                    shortcut: "S"
                });
            }
            if (compact) {
                entries.push({divider: true}, {
                    id: "back",
                    text: "Retroceder 10 s",
                    icon: "replay_10"
                }, {
                    id: "ahead",
                    text: "Avanzar 10 s",
                    icon: "forward_10"
                }, {
                    id: "speedmenu",
                    text: "Velocidad…",
                    icon: "speed"
                });
                if (p.kindName === "video")
                    entries.push({
                        id: "submenu",
                        text: "Subtítulos…",
                        icon: "closed_caption"
                    });
                if (p.audioTracks.length > 1)
                    entries.push({
                        id: "audiomenu",
                        text: "Pista de audio…",
                        icon: "audiotrack"
                    });
            }
        } else if (p.kindName === "image") {
            entries.push({
                id: "rotr",
                text: "Girar a la derecha",
                icon: "rotate_right",
                shortcut: "R"
            }, {
                id: "rotl",
                text: "Girar a la izquierda",
                icon: "rotate_left",
                shortcut: "Mayús+R"
            }, {
                id: "copyimage",
                text: "Copiar imagen",
                icon: "content_copy",
                shortcut: "Ctrl+C"
            });
        }
        entries.push({divider: true}, {
            id: "copypath",
            text: "Copiar ruta",
            icon: "link"
        }, {
            id: "reveal",
            text: "Mostrar en Files",
            icon: "folder_open"
        }, {
            id: "open",
            text: "Abrir…",
            icon: "file_open",
            shortcut: "Ctrl+O"
        }, {
            id: "trash",
            text: "Mover a la papelera",
            icon: "delete",
            shortcut: "Supr",
            danger: true
        });
        return entries;
    }

    function trigger(id) {
        const p = player;
        const [name, value] = id.split(":");
        switch (name) {
        case "speed":
            return p.setSpeed(Number(value));
        case "sub":
            return p.selectSubtitle(Number(value));
        case "audio":
            return p.selectAudio(Number(value));
        case "subfile":
            return p.chooseSubtitles();
        case "subearlier":
            return p.shiftSubtitles(-0.1);
        case "sublater":
            return p.shiftSubtitles(0.1);
        case "info":
            return root.infoRequested();
        case "loop":
            return p.toggleLoop();
        case "ab":
            return p.markLoop();
        case "prevframe":
            return p.step(-1);
        case "nextframe":
            return p.step(1);
        case "saveframe":
            return p.saveFrame();
        case "back":
            return p.skip(-10);
        case "ahead":
            return p.skip(10);
        case "speedmenu":
            return root.submenu("speed");
        case "submenu":
            return root.submenu("subtitles");
        case "audiomenu":
            return root.submenu("audio");
        case "rotr":
            return image.rotate(1);
        case "rotl":
            return image.rotate(-1);
        case "copyimage":
            return p.copyImage();
        case "copypath":
            return p.copyPath();
        case "reveal":
            return p.reveal();
        case "open":
            return p.chooseFiles();
        case "trash":
            return p.trash();
        }
    }
}
