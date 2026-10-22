pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Wysun
import Wysun.I18n
import qs.services
import qs.utils

// One screenshot from open to close, shared by the picker windows of every output.
// phase: "select" → "actions" | "edit" | "ocr"; only the output under the
// pointer (screenName) takes the keyboard and shows the selection.
QtObject {
    id: root

    // "actions" (choose after selecting) or "annotate" (straight to the editor).
    property string mode: "actions"
    // Folder for saved PNGs; empty uses ~/Pictures/Screenshots.
    property string saveDir
    property bool autoSave: true

    property string phase: "select"
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

    function keep(path: string): string {
        const target = `${outputDir}/Screenshot_${stamp()}.png`;
        Quickshell.execDetached(["sh", "-c", 'mkdir -p "$(dirname "$2")" && cp -n "$1" "$2"', "sh", path, target]);
        return target;
    }

    // Copy (and save when the shortcut asks for it), notify and close.
    function deliver(item: Item, save: bool): void {
        render(item, path => {
            copyImage(path);
            const saved = save ? keep(path) : "";
            const body = saved ? Tr.tr("Copied to the clipboard and saved to %1").arg(Paths.shortenHome(saved)) : Tr.tr("Copied to the clipboard");
            Quickshell.execDetached(["notify-send", "-a", "Wysun", "-i", path, Tr.tr("Screenshot taken"), body]);
            finished();
        });
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
