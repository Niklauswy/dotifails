#version 440

// Liquid Rift. Original Wysun code.
// A tear opens on the focused screen and spreads as an organic, refracting front
// across the whole desktop (every screen shares the same origin, so the front
// crosses monitor borders as one wave). The new wallpaper waits underneath; the
// old one is a film the wave pushes away, thins and tears, with chromatic fringes,
// a glow and a scatter of sparks on the torn lip.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float progress;
    float riftReach;   // desktop px the front must travel to clear every screen
    vec2 screenOrigin; // this screen's top-left, desktop px
    vec2 screenSize;   // this screen's size, px
    vec2 riftOrigin;   // where the tear opens, desktop px
};

layout(binding = 1) uniform sampler2D from;
layout(binding = 2) uniform sampler2D to;

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

vec4 sampleScreen(sampler2D tex, vec2 px) {
    return texture(tex, clamp((px - screenOrigin) / screenSize, vec2(0.0), vec2(1.0)));
}

void main() {
    float p = clamp(progress, 0.0, 1.0);
    // Exact endpoints keep captures of interrupted transitions seamless.
    if (p <= 0.0) {
        fragColor = texture(from, qt_TexCoord0) * qt_Opacity;
        return;
    }
    if (p >= 1.0) {
        fragColor = texture(to, qt_TexCoord0) * qt_Opacity;
        return;
    }

    float unit = max(screenSize.x, screenSize.y);
    vec2 px = screenOrigin + qt_TexCoord0 * screenSize;
    vec2 rel = px - riftOrigin;
    float d = length(rel);
    vec2 dir = d > 0.001 ? rel / d : vec2(0.0);

    // Slow tear, steady spread, soft landing; the front clears the farthest corner
    // shortly before the end so the settle has time to breathe.
    float t = smoothstep(0.0, 0.9, p);
    float radius = mix(-0.04 * unit, riftReach + 0.2 * unit, t);

    // Organic edge: angular lobes that drift as the front grows, plus fine grain.
    // Their size follows the radius so the tear starts as a drop, not a star.
    float lobes = fbm(dir * 2.4 + vec2(1.7 * p, -1.3 * p)) - 0.5;
    float grain = noise(px / unit * 5.0 + 3.0 * p) - 0.5;
    float wobble = (0.32 * lobes + 0.04 * grain) * min(0.55 * unit, max(radius, 0.0));
    float s = d - (radius + wobble); // < 0 inside the rift (new wallpaper)

    float fade = sin(3.14159265 * p);
    float ahead = max(s, 0.0);
    float behind = max(-s, 0.0);

    // Two layers. The new wallpaper sits underneath, still, from the first frame;
    // the old one is a film on top that the wave pushes outwards, lifts and thins
    // until it tears open. Nothing is darkened.
    float push = exp(-ahead / (0.14 * unit));
    float ripple = sin(ahead / (0.022 * unit) - 22.0 * p) * push;
    vec2 centre = screenOrigin + 0.5 * screenSize;
    float lift = 1.0 + 0.035 * t; // the film rises towards the viewer as it goes
    vec2 oldPx = centre + (px - centre) / lift - dir * (0.05 * push + 0.007 * ripple) * unit * fade;
    vec4 outgoing = sampleScreen(from, oldPx);
    // The lifted film catches light along the wave.
    outgoing.rgb *= 1.0 + 0.18 * push * fade;

    // Underneath: only the liquid rings left by the tear bend the new wallpaper.
    float rings = sin(behind / (0.03 * unit) - 16.0 * p) * exp(-behind / (0.16 * unit));
    vec2 newPx = px - dir * 0.006 * rings * unit * (1.0 - p);

    // The lip refracts: channels split along the front's normal.
    float lip = exp(-abs(s) / (0.035 * unit));
    vec2 split = dir * lip * 0.016 * unit * fade;
    vec4 incoming;
    incoming.r = sampleScreen(to, newPx - split * 1.6).r;
    incoming.g = sampleScreen(to, newPx - split * 0.4).g;
    incoming.b = sampleScreen(to, newPx + split).b;
    incoming.a = 1.0;

    // The film thins ahead of the tear, so the new wallpaper shows through first.
    float thin = smoothstep(0.07 * unit, 0.0, s) * 0.6 * smoothstep(0.0, 0.05 * unit, radius);
    float edge = 0.004 * unit;
    float film = smoothstep(-edge, edge, s) * (1.0 - thin);
    vec3 colour = mix(incoming.rgb, outgoing.rgb, film);

    // Glow on the torn rim, tinted by the new wallpaper.
    float rim = exp(-abs(s) / (0.006 * unit)) + 0.3 * exp(-abs(s) / (0.03 * unit));
    vec3 tint = mix(incoming.rgb, vec3(1.0), 0.5);
    colour += tint * rim * 0.7 * fade;

    // Sparks flung just ahead of the front.
    float cellSize = unit / 120.0;
    vec2 cell = floor(px / cellSize);
    float h = hash(cell);
    if (h > 0.955) {
        vec2 spot = vec2(hash(cell + 1.3), hash(cell + 7.1)) - 0.5;
        float dist = length(fract(px / cellSize) - 0.5 - spot * 0.6);
        float life = exp(-ahead / (0.05 * unit)) * smoothstep(-0.01 * unit, 0.0, s);
        float twinkle = 0.6 + 0.4 * sin(40.0 * p + 60.0 * h);
        colour += tint * smoothstep(0.22, 0.0, dist) * life * twinkle * 1.4 * fade;
    }

    fragColor = vec4(colour, 1.0) * qt_Opacity;
}
