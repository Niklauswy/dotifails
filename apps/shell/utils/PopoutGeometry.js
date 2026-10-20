.pragma library

function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
}

function popoutGeometry(hostWidth, hostHeight, anchorX, anchorY, targetWidth, targetHeight, progress) {
    var p = clamp(typeof progress === "number" && isFinite(progress) ? progress : 0, 0, 1);
    var startWidth = 72;
    var startHeight = 64;
    var boundedTargetWidth = Math.min(hostWidth, targetWidth);
    var boundedTargetHeight = Math.min(hostHeight, targetHeight);
    var startX = clamp(anchorX - startWidth / 2, 0, Math.max(0, hostWidth - startWidth));
    var startY = clamp(anchorY - startHeight / 2, 0, Math.max(0, hostHeight - startHeight));
    var endX = (hostWidth - boundedTargetWidth) / 2;
    var endY = (hostHeight - boundedTargetHeight) / 2;
    return {
        x: startX + (endX - startX) * p,
        y: startY + (endY - startY) * p,
        width: startWidth + (boundedTargetWidth - startWidth) * p,
        height: startHeight + (boundedTargetHeight - startHeight) * p
    };
}
