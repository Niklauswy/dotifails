// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: geometría de modules/bar/popouts/Wrapper.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
.pragma library

function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
}

function progressValue(progress) {
    return clamp(typeof progress === "number" && isFinite(progress) ? progress : 0, 0, 1);
}

// Interpolate a rectangle between an explicit origin (the rail control that
// opened the surface) and its final centred target. Interrupting a transition
// only changes the progress value, so the caller can retarget without a jump.
function interpolateRect(originX, originY, originWidth, originHeight, targetX, targetY, targetWidth, targetHeight, progress) {
    var p = progressValue(progress);
    return {
        x: originX + (targetX - originX) * p,
        y: originY + (targetY - originY) * p,
        width: originWidth + (targetWidth - originWidth) * p,
        height: originHeight + (targetHeight - originHeight) * p
    };
}

function centeredRect(hostWidth, hostHeight, targetWidth, targetHeight) {
    var width = Math.min(hostWidth, Math.max(0, targetWidth));
    var height = Math.min(hostHeight, Math.max(0, targetHeight));
    return {
        x: (hostWidth - width) / 2,
        y: (hostHeight - height) / 2,
        width: width,
        height: height
    };
}

function popoutGeometry(hostWidth, hostHeight, anchorX, anchorY, targetWidth, targetHeight, progress) {
    var startWidth = 72;
    var startHeight = 64;
    var boundedTargetWidth = Math.min(hostWidth, targetWidth);
    var boundedTargetHeight = Math.min(hostHeight, targetHeight);
    var startX = clamp(anchorX - startWidth / 2, 0, Math.max(0, hostWidth - startWidth));
    var startY = clamp(anchorY - startHeight / 2, 0, Math.max(0, hostHeight - startHeight));
    var endX = (hostWidth - boundedTargetWidth) / 2;
    var endY = (hostHeight - boundedTargetHeight) / 2;
    return interpolateRect(startX, startY, startWidth, startHeight, endX, endY, boundedTargetWidth, boundedTargetHeight, progress);
}
