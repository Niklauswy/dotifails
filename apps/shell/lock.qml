// Entrada del bloqueo QML opt-in de Wysun. Vive en la raíz de la shell para
// que las importaciones relativas de Appearance, Logic.js, servicios y
// componentes sigan dentro del config folder de Quickshell. No sustituye a
// shell.qml: es un proceso/configuración independiente que solo arranca
// wysun-lock cuando el usuario activa el backend "qml".
// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell
import "modules/lock" as LockModule

ShellRoot {
    LockModule.LockRoot {}
}
