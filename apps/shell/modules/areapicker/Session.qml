pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun
import Wysun.I18n
import qs.services
import qs.utils

// One screenshot from open to close, shared by the picker windows of every output.
// phase: "select" → "actions" | "edit" | "ocr" (or straight to delivery in quick
// mode); only the output under the pointer (screenName) takes the keyboard.
QtObject {
    id: root

    // "quick": copy (and save) as soon as a region is chosen;
    // "actions": choose afterwards between copy, save as, annotate or text;
    // "record": choose afterwards what to record, then hand the region to Wysun Recorder.
    property string mode: "quick"
    // Folder for saved PNGs; empty uses ~/Pictures/Screenshots.
    property string saveDir
    property bool autoSave: true

    property string phase: "select"
    // Recording only: what the person chose to record ("screen", "window", "area").
    property string pick
    property string screenName
    property rect selection
    property bool busy
    property string ocrText
    property bool ocrRunning

    readonly property string outputDir: saveDir || `${Paths.pictures}/Screenshots`
    readonly property string scratchDir: `${Paths.cache}/screenshots`

    property Process ocr: Process {
        stdout: StdioCollector {
            onStreamFinished: {
                root.ocrText = text.trim();
                root.ocrRunning = false;
            }
        }
        onExited: code => {
            if (code !== 0)
                root.ocrRunning = false;
        }
    }

    signal finished

    function stamp(): string {
        return Qt.formatDateTime(new Date(), "yyyy-MM-dd_hh-mm-ss-zzz");
    }

    // Grabs `item` cropped to the selection, then calls done(path) with a scratch PNG.
    function render(item: Item, done: var): void {
        busy = true;
        const r = selection;
        const file = Qt.resolvedUrl(`${scratchDir}/capture-${stamp()}.png`);
        CUtils.saveItem(item, file, Qt.rect(Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)), path => {
            busy = false;
            done(path);
        }, () => {
            busy = false;
            Quickshell.execDetached(["notify-send", "-a", "Wysun", "-u", "critical", Tr.tr("Screenshot failed"), Tr.tr("The capture could not be written.")]);
        });
    }

    function copyImage(path: string): void {
        Quickshell.execDetached(["sh", "-c", 'wl-copy --type image/png < "$1"', "sh", path]);
    }

    // The copy in flight, so its outcome reaches the caller only once the file really exists.
    property var pendingSave

    property Process saver: Process {
        onExited: code => {
            const pending = root.pendingSave;
            root.pendingSave = null;
            if (pending)
                code === 0 ? pending.done(pending.target) : pending.failed();
        }
    }

    // Publishes the scratch PNG in the screenshots folder. done(target) runs after the file is in place;
    // failed() runs when it could not be written, and nothing may then assume the file exists.
    function keep(path: string, done: var, failed: var): void {
        const target = `${outputDir}/Screenshot_${stamp()}.png`;
        pendingSave = { target: target, done: done, failed: failed };
        saver.command = ["sh", "-c", 'mkdir -p "$(dirname "$2")" && cp -n -- "$1" "$2" && test -s "$2"', "sh", path, target];
        saver.running = true;
    }

    function notifyFailure(): void {
        Quickshell.execDetached(["notify-send", "-a", "Wysun", "-u", "critical", Tr.tr("Screenshot not saved"), Tr.tr("The file could not be written to %1.").arg(Paths.shortenHome(outputDir))]);
    }

    // Copy (and save when the shortcut asks for it), notify and close.
    function deliver(item: Item, save: bool): void {
        render(item, path => {
            copyImage(path);
            const announce = saved => {
                const body = saved ? Tr.tr("Copied to the clipboard and saved to %1").arg(Paths.shortenHome(saved)) : Tr.tr("Copied to the clipboard");
                Quickshell.execDetached(["notify-send", "-a", "Wysun", "-i", path, Tr.tr("Screenshot taken"), body]);
                finished();
            };
            if (!save)
                return announce("");
            keep(path, announce, () => {
                notifyFailure();
                finished();   // the copy to the clipboard did succeed
            });
        });
    }

    // Copy, save, and open the saved picture in Wysun Player. The viewer is launched only once the file is
    // published; if saving fails the overlay stays open so the capture can be saved again.
    function view(item: Item): void {
        render(item, path => {
            copyImage(path);
            keep(path, saved => {
                Quickshell.execDetached(["wysun", "player", "--", saved]);
                finished();
            }, notifyFailure);
        });
    }

    // Copy, close the overlay and ask where to save through the portal (Wysun Files).
    function saveAs(item: Item): void {
        render(item, path => {
            copyImage(path);
            Quickshell.execDetached(["python3", "-I", Quickshell.shellPath("modules/areapicker/save_as.py"), path, outputDir, `Screenshot_${stamp()}.png`]);
            finished();
        });
    }

    // Hands the selection to the recorder (countdown, then Wysun Recorder's detached
    // worker) and closes the overlay; the HUD and the utilities card follow it from there.
    function startRecording(output: ShellScreen, wholeOutput: bool): void {
        const r = selection;
        Recorder.launch(output.name, Qt.rect(r.x, r.y, r.width, r.height), wholeOutput, wholeOutput ? "monitor" : "region",
            [Math.round(output.x + r.x), Math.round(output.y + r.y), Math.round(r.width), Math.round(r.height)]);
        finished();
    }

    function recognise(item: Item): void {
        phase = "ocr";
        ocrText = "";
        ocrRunning = true;
        render(item, path => {
            ocr.command = ["tesseract", path, "-", "-l", "spa+eng", "--psm", "6"];
            ocr.running = true;
        });
    }

    function copyText(text: string): void {
        Quickshell.execDetached(["wl-copy", "--", text]);
        Quickshell.execDetached(["notify-send", "-a", "Wysun", Tr.tr("Text copied"), text.length > 120 ? text.slice(0, 117) + "…" : text]);
        finished();
    }
}
