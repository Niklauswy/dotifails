#version 440
// Wysun lock · the CRT the whole interface is shown on: barrel curvature, RGB convergence error,
// a cheap bloom, scanlines, grain, flicker, and the power-off collapse (to a line, then a dot).
// Unlocking as an elevator: the doors close over the tube, then open again on the desktop (`reveal`):
// a flat snapshot of it taken when locking, so the real desktop appears exactly where the doors part.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float lines;      // screen height in pixels, for scanlines
    float tear;       // 0 .. 1 glitch: RGB split and torn rows
    float power;      // 1 on .. 0 off
    float doors;      // 0 open .. 1 closed: the elevator (greeter → session)
    vec4 base;
    vec4 ink;
    float curve;      // barrel curvature; 0 keeps geometry exact (Plymouth's frame)
    float reveal;     // 0 classic; 0.5 the doors will open on the desktop; 1 they open on its snapshot, flat
    float film;       // 0 .. 1 the summit film is on: less bloom, so its painting is not washed out
};

layout(binding = 1) uniform sampler2D source;
layout(binding = 2) uniform sampler2D desktop;

// The elevator doors at uv; returns the steel colour and how much of it covers the pixel.
vec3 steelAt(vec2 uv, float half_, float side) {
    float grain = fract(sin(floor(uv.x * 1400.0) * 12.9898) * 43758.5453) * 0.08 + sin(uv.x * 420.0) * 0.02;
    float bevel = 1.0 - smoothstep(0.0, 0.012, side - half_);
    float sheen = 0.5 + 0.5 * sin((uv.x - 0.5) * 9.0 + uv.y * 2.0);
    vec3 steel = mix(base.rgb, ink.rgb, 0.22 + 0.1 * sheen);
    return steel * (0.55 + grain + 0.25 * (1.0 - uv.y)) + ink.rgb * bevel * 0.35;
}

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec2 barrel(vec2 uv) {
    vec2 c = uv * 2.0 - 1.0;
    c *= 1.0 + dot(c, c) * curve;
    return c * 0.5 + 0.5;
}

void main() {
    if (reveal > 0.5) {
        // The doors part on the desktop: everything flat and exact, so the last frame is the desktop itself.
        vec2 flat_ = qt_TexCoord0;
        float half_ = 0.5 * (1.0 - doors);
        float side = abs(flat_.x - 0.5);
        vec3 colour = texture(desktop, flat_).rgb;
        if (side > half_)
            colour = steelAt(flat_, half_, side);
        // Light from the room spills through the opening while it is still narrow.
        float seam = exp(-abs(side - half_) * lines * 0.05) * smoothstep(0.6, 0.95, doors);
        colour += vec3(0.35) * seam;
        fragColor = vec4(colour, 1.0) * qt_Opacity;
        return;
    }
    vec2 uv = barrel(qt_TexCoord0);
    // Power-off: squeeze vertically to a bright line, then horizontally to a dot.
    float sy = clamp(power * 2.0, 0.003, 1.0);
    float sx = clamp(power * 2.0 + 0.5, 0.004, 1.0);
    vec2 squeezed = vec2((uv.x - 0.5) / sx + 0.5, (uv.y - 0.5) / sy + 0.5);
    float tick = floor(time * 30.0);
    float row = floor(squeezed.y * 90.0);
    squeezed.x += (hash(vec2(row, tick)) - 0.5) * 0.08 * tear * step(0.7, hash(vec2(row + 3.0, tick)));
    vec2 split = vec2(0.0012 + tear * 0.009, 0.0);
    vec3 colour = vec3(texture(source, squeezed + split).r, texture(source, squeezed).g, texture(source, squeezed - split).b);
    // Bloom: a ring of taps around the pixel.
    vec3 glow = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785398;
        glow += texture(source, squeezed + vec2(cos(angle), sin(angle)) * vec2(0.0035, 0.006)).rgb;
    }
    colour += max(glow / 8.0 - base.rgb, 0.0) * 0.9 * (1.0 - film * 0.85);
    colour *= 0.86 + 0.14 * sin(qt_TexCoord0.y * lines * 1.5708);
    colour += (hash(qt_TexCoord0 * vec2(1733.0, 997.0) + fract(time * 13.0)) - 0.5) * 0.05;
    colour *= 0.985 + 0.015 * sin(time * 62.0);
    vec2 c = uv - 0.5;
    colour *= 1.0 - smoothstep(0.25, 0.75, length(c * vec2(1.0, 1.2))) * 0.55;
    if (squeezed.x < 0.0 || squeezed.x > 1.0 || squeezed.y < 0.0 || squeezed.y > 1.0)
        colour = vec3(0.0);
    // The collapsing line and dot glow white-hot.
    float line = (1.0 - sy) * exp(-abs(uv.y - 0.5) * lines * 0.08) * step(abs(uv.x - 0.5), sx * 0.5);
    colour += vec3(line);
    if (power <= 0.0)
        colour = vec3(0.0);
    // Elevator: two brushed-metal doors close from the sides; light leaks through the seam. When they will
    // open again on the desktop they are drawn flat over the whole screen instead (below), so closing and
    // opening are the very same doors.
    if (doors > 0.0 && reveal < 0.2) {
        float half_ = 0.5 * (1.0 - doors);
        float side = abs(uv.x - 0.5);
        if (side > half_) {
            // Brushed steel in the scheme's tint: fine vertical grain, a soft sheen and a bevelled edge.
            colour = steelAt(uv, half_, side);
        }
        float seam = exp(-abs(side - half_) * lines * 0.11) * smoothstep(0.8, 0.97, doors) * (1.0 - smoothstep(0.985, 1.0, doors));
        colour += (base.rgb + 0.6) * seam;
        // Fully closed the car goes dark, unless the doors are about to open on the desktop.
        if (reveal < 0.2)
            colour *= 1.0 - smoothstep(0.985, 1.0, doors);
    }
    // Outside the tube: the bezel is the canvas, darkened.
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0)
        colour = base.rgb * 0.35;
    if (doors > 0.0 && reveal >= 0.2) {
        vec2 flat_ = qt_TexCoord0;
        float half_ = 0.5 * (1.0 - doors);
        float side = abs(flat_.x - 0.5);
        if (side > half_)
            colour = steelAt(flat_, half_, side);
        float seam = exp(-abs(side - half_) * lines * 0.05) * smoothstep(0.6, 0.95, doors);
        colour += vec3(0.35) * seam;
    }
    fragColor = vec4(colour, 1.0) * qt_Opacity;
}
