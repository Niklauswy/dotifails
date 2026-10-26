#version 440

// Card Bloom. Original Wysun code.
// The wallpaper picker's landed card swells into the new wallpaper: its rounded
// rectangle grows past the screen edges with a liquid, refracting lip, while the
// picture inside slides from the card's crop to the wallpaper in place. Outside
// the card everything is transparent, so the old desktop stays visible until the
// lip has crossed it.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    float cornerRadius; // the card's corner radius at progress 0, px
    vec4 cardRect;      // the card at progress 0: x, y, width, height in px
    vec2 screenSize;    // px
    vec4 tint;          // glow colour (the selection's accent)
};

layout(binding = 1) uniform sampler2D source; // the new wallpaper, filling the screen

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
    return 0.55 * noise(p) + 0.3 * noise(p * 2.03 + 17.0) + 0.15 * noise(p * 4.11 + 41.0);
}

float roundedBox(vec2 p, vec2 halfSize, float r) {
    vec2 q = abs(p) - halfSize + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

void main() {
    float p = clamp(progress, 0.0, 1.0);
    float unit = max(screenSize.x, screenSize.y);
    vec2 px = qt_TexCoord0 * screenSize;
    float swell = sin(3.14159265 * p); // 0 at both ends: the card starts and ends exact

    // The card's box grows from where it landed to past every screen edge; the
    // corners round out as it swells so the box overflows the screen corners too.
    float pad = 0.14 * unit;
    vec2 centre = mix(cardRect.xy + 0.5 * cardRect.zw, 0.5 * screenSize, p);
    vec2 halfSize = mix(0.5 * cardRect.zw, 0.5 * screenSize + pad, p);
    float radius = mix(cornerRadius, 0.25 * unit, smoothstep(0.0, 1.0, p));
    radius = min(radius, min(halfSize.x, halfSize.y));

    vec2 rel = px - centre;
    float d = length(rel);
    vec2 dir = d > 0.001 ? rel / d : vec2(0.0);

    // Liquid lip: lobes that drift around the box while it swells.
    float lobes = fbm(dir * 2.4 + vec2(1.7 * p, -1.3 * p)) - 0.5;
    float grain = noise(px / unit * 6.0 + 3.0 * p) - 0.5;
    float s = roundedBox(rel, halfSize, radius) - (0.09 * lobes + 0.012 * grain) * unit * swell; // < 0 inside

    // The picture: the card's crop of the wallpaper, stretched with the box, easing
    // into the wallpaper in place before the end.
    vec2 cardUv = (px - (centre - halfSize)) / (2.0 * halfSize);
    float boxAspect = halfSize.x / halfSize.y;
    float screenAspect = screenSize.x / screenSize.y;
    vec2 cropUv = cardUv;
    if (boxAspect < screenAspect)
        cropUv.x = 0.5 + (cardUv.x - 0.5) * boxAspect / screenAspect;
    else
        cropUv.y = 0.5 + (cardUv.y - 0.5) * screenAspect / boxAspect;
    vec2 uv = mix(cropUv, qt_TexCoord0, smoothstep(0.35, 1.0, p));

    // Rings left inside by the lip, and channels split along its normal.
    float behind = max(-s, 0.0);
    float rings = sin(behind / (0.03 * unit) - 16.0 * p) * exp(-behind / (0.12 * unit));
    uv -= dir * 0.004 * rings * swell;
    float lip = exp(-abs(s) / (0.03 * unit));
    vec2 split = dir * lip * 0.012 * swell;
    vec3 picture = vec3(texture(source, clamp(uv - split * 1.6, 0.0, 1.0)).r,
                        texture(source, clamp(uv - split * 0.4, 0.0, 1.0)).g,
                        texture(source, clamp(uv + split, 0.0, 1.0)).b);

    float edge = 1.5;
    float inside = smoothstep(edge, -edge, s);

    // Glow on the lip, in the accent; it fades out as the box leaves the screen.
    float strength = 1.0 - smoothstep(0.7, 1.0, p);
    float rim = (exp(-abs(s) / (0.004 * unit)) + 0.35 * exp(-abs(s) / (0.025 * unit))) * strength;
    vec3 glow = mix(tint.rgb, vec3(1.0), 0.35);

    // Sparks flung just ahead of the lip.
    float ahead = max(s, 0.0);
    float cellSize = unit / 120.0;
    vec2 cell = floor(px / cellSize);
    float h = hash(cell);
    float spark = 0.0;
    if (h > 0.955) {
        vec2 spot = vec2(hash(cell + 1.3), hash(cell + 7.1)) - 0.5;
        float dist = length(fract(px / cellSize) - 0.5 - spot * 0.6);
        float life = exp(-ahead / (0.05 * unit)) * smoothstep(-0.01 * unit, 0.0, s);
        spark = smoothstep(0.22, 0.0, dist) * life * (0.6 + 0.4 * sin(40.0 * p + 60.0 * h)) * swell;
    }

    // Premultiplied: the picture inside, light on the lip and the sparks outside.
    float light = clamp(rim * 0.8 + spark * 1.4, 0.0, 1.0);
    vec3 colour = picture * inside + glow * light;
    float alpha = inside + light * (1.0 - inside);
    fragColor = vec4(colour, alpha) * qt_Opacity;
}
