// Prints where the camera preview and the solid marker sit, and what dragging the preview saves (see
// tests/test_shell_camera.py). The test runs it as the shell.qml of a throwaway shell dir that holds a stub
// services/Recorder.qml, services/Colours.qml, a Wallpapers stub, utils/ and components/. No camera is opened.
import QtQuick
import Quickshell
import qs.components.camera

ShellRoot {
    FloatingWindow {
        id: win

        implicitWidth: 1000
        implicitHeight: 600

        CameraPreview {
            id: preview

            objectName: "preview"
            area: Qt.rect(100, 50, 800, 450)
            live: false
        }

        CameraMarkerShape {
            id: marker

            area: Qt.rect(100, 50, 800, 450)
            style: ({ shape: "rounded", size: "large", corner: "top-left" })
        }

        Timer {
            interval: 1200
            running: true
            onTriggered: {
                const box = item => ({ x: item.x, y: item.y, width: item.width, height: item.height });
                const out = { preview: box(preview), marker: box(marker.shape), radius: marker.shape.radius };
                // Drag the bubble (bottom-right at rest) into the top-left quadrant of the area.
                preview.beginDrag(preview.x + 10, preview.y + 10);
                preview.moveDrag(200, 120);
                out.dragging = preview.dragging;
                out.during = box(preview);
                preview.endDrag();
                out.afterMove = box(preview);
                // A drag that ends in the corner it already is in saves nothing.
                preview.beginDrag(preview.x + 10, preview.y + 10);
                preview.moveDrag(preview.x + 14, preview.y + 14);
                preview.endDrag();
                console.info("CAMERA " + JSON.stringify(out));
                Qt.quit();
            }
        }
    }
}
