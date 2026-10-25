// Wysun Lock entry. A separate Quickshell process started by wysun-lock, never by the shell: if the
// shell restarts or crashes the lock is unaffected, and the lock loads none of the shell's services.
// It lives at the shell root so relative imports and Quickshell.shellPath() resolve inside the config.
import QtQuick
import Quickshell
import "modules/lockscreen"

ShellRoot {
    LockRoot {}
}
