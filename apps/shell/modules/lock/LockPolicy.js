.pragma library
// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Estados y jerarquía de modules/lock/Center.qml, Content.qml y
// center/{Clock,PasswordInput,InputField,StateMessage}.qml, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse THIRD_PARTY.md y
// LICENSES/GPL-3.0.txt. La autenticación es un cliente PamContext propio de
// Wysun; no se porta Pam.qml ni su IPC.

var MAX_LENGTH = 256;

function text(state, detail) {
    switch (state) {
    case "authenticating":
        return "Comprobando…";
    case "failed":
        return "Contraseña incorrecta. Inténtalo de nuevo.";
    case "maxtries":
        return "Demasiados intentos. Espera un momento antes de reintentar.";
    case "error":
        return detail ? "No se pudo autenticar: " + detail
                      : "No se pudo autenticar. Revisa la configuración de PAM.";
    case "success":
        return "Sesión desbloqueada";
    default:
        return "Introduce tu contraseña";
    }
}

function isError(state) {
    return state === "failed" || state === "maxtries" || state === "error";
}

// Apply one key event to the private buffer. Only printable text is appended;
// Enter submits, Backspace edits and Escape clears. The buffer never leaves
// this process and is cleared before the PAM response is sent.
function key(buffer, key, textValue, control) {
    buffer = typeof buffer === "string" ? buffer : "";
    // Qt.Key_Return = 13, Qt.Key_Enter = 10, Qt.Key_Backspace = 8, Qt.Key_Escape = 27.
    if (key === 13 || key === 10)
        return { buffer: buffer, submit: true };
    if (key === 8)
        return { buffer: control ? "" : buffer.slice(0, -1), submit: false };
    if (key === 27)
        return { buffer: "", submit: false };
    if (!control && typeof textValue === "string" && /^[^\x00-\x1f\x7f-\x9f]+$/.test(textValue)
            && buffer.length < MAX_LENGTH)
        return { buffer: buffer + textValue, submit: false };
    return { buffer: buffer, submit: false };
}

function mask(length) {
    var count = Math.max(0, Math.min(MAX_LENGTH, Math.round(length || 0)));
    return count === 0 ? "" : Array(count + 1).join("•");
}

function scale(height) {
    var value = typeof height === "number" && isFinite(height) ? height : 1440;
    return Math.max(0.7, Math.min(1.25, value / 1440));
}

function layout(width, height) {
    var ratio = scale(height);
    var available = Math.max(0, (typeof width === "number" && isFinite(width) ? width : 1280) - 48);
    var column = Math.min(520 * ratio, available);
    return {
        scale: ratio,
        width: column,
        gap: Math.round(16 * ratio),
        clockSize: Math.round(84 * ratio),
        dateSize: Math.round(14 * ratio),
        labelSize: Math.round(13 * ratio),
        fieldHeight: Math.round(52 * ratio),
        mediaHeight: Math.round(64 * ratio)
    };
}

function mediaEnabled(value) {
    return value === true || value === "1";
}
