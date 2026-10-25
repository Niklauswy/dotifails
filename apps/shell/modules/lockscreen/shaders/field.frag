#version 440
// Wysun lock · the refinement field. A grid of digits that drift and breathe; a box dragged with the
// mouse picks the ones inside it, a cluster turns «scary» on every keystroke, a band sweeps while
// the password is verified, everything scrambles red when it is refused and drains downward into
// the bins when it is accepted. Glyphs come from a 10-cell atlas rendered with the shell's mono font.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float cols;
    float rows;
    float aspect;     // field width / height
    vec4 selection;   // field uv of the box dragged with the mouse: two corners
    float selecting;  // 0 .. 1, a box is being dragged
    vec2 cluster;     // field uv of the agitated cluster
    float agitation;  // 0 .. 1
    float sweep;      // 0 .. 1 band position, negative = off
    float alert;      // 0 .. 1 red
    float scramble;   // 0 .. 1 digits re-roll fast
    float drain;      // 0 .. 1 digits fall into the bins
    float dance;      // 0 .. 1 easter egg: the field sways and pulses (Music Dance Experience)
    vec4 base;
    vec4 ink;
    vec4 danger;
    vec2 target;      // field uv of the group waiting to be refined
    float targetGlow; // 0 .. 1, shown while idle until a box catches it
};

layout(binding = 1) uniform sampler2D atlas;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float glyph(float digit, vec2 p) {
    if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0)
        return 0.0;
    return texture(atlas, vec2((digit + p.x) / 10.0, p.y)).a;
}

void main() {
    vec2 grid = vec2(cols, rows);
    vec2 g = qt_TexCoord0 * grid;
    vec2 cell = floor(g);
    float lit = 0.0;
    float heat = 0.0;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            vec2 c = cell + vec2(float(dx), float(dy));
            if (c.x < 0.0 || c.y < 0.0 || c.x >= cols || c.y >= rows)
                continue;
            float h = hash(c + 0.37);
            // Digits change rarely at rest, constantly when scrambled.
            float epoch = floor(time * (0.04 + scramble * 14.0) + h * 40.0);
            float digit = floor(hash(c + epoch * 1.73) * 10.0);
            vec2 centre = c + 0.5;
            centre += vec2(sin(time * (0.5 + h * 0.6) + h * 6.283), cos(time * (0.4 + h * 0.5) + h * 9.0)) * 0.09;
            vec2 cuv = centre / grid;
            // Digits inside the dragged box are picked: larger and brighter, but calm.
            vec2 lo = min(selection.xy, selection.zw);
            vec2 hi = max(selection.xy, selection.zw);
            float near = selecting * step(lo.x, cuv.x) * step(cuv.x, hi.x) * step(lo.y, cuv.y) * step(cuv.y, hi.y);
            float scary = agitation * smoothstep(0.13, 0.0, length((cuv - cluster) * vec2(aspect, 1.0)));
            // The group waiting to be refined: it trembles and swells until a box catches it.
            float wanted = targetGlow * smoothstep(0.13, 0.02, length((cuv - target) * vec2(aspect, 1.0)));
            float nervous = scary + alert * 0.6 + wanted * (0.75 + 0.25 * sin(time * 3.0 + h * 6.0));
            float tick = floor(time * 22.0);
            centre += (vec2(hash(c + tick), hash(c - tick)) - 0.5) * 0.32 * nervous;
            // Drain: each column falls at its own pace into the bins below.
            float delay = hash(vec2(c.x, 7.0)) * 0.35 + (rows - c.y) / rows * 0.25;
            float fall = clamp((drain - delay) / (1.0 - delay), 0.0, 1.0);
            centre.y += fall * fall * rows * 1.3;
            // Easter egg, the Music Dance Experience: the field sways, and rings of light pulse out of
            // the middle bin, where the mascot dances, on every beat.
            centre.y += sin(time * 7.0 + c.x * 0.55 + c.y * 0.2) * 0.38 * dance;
            float beat = pow(abs(sin(time * 3.1416 * 2.0)), 6.0);
            float ring = pow(0.5 + 0.5 * sin(length((cuv - vec2(0.5, 1.1)) * vec2(aspect, 1.0)) * 14.0 - time * 9.0), 6.0);
            float party = dance * (ring * 0.8 + beat * 0.35);
            float scale = 1.0 + near * 0.55 + scary * 0.9 + party * 0.5 + wanted * (0.85 + 0.25 * sin(time * 2.0 + h * 4.0));
            vec2 local = (g - centre) / (scale * vec2(0.62, 0.78)) + 0.5;
            float a = glyph(digit, vec2(local.x, local.y));
            float band = sweep >= 0.0 ? exp(-abs(cuv.y - sweep) * 18.0) : 0.0;
            float brightness = 0.42 + 0.58 * clamp(nervous + band + near + party, 0.0, 1.0) + 0.12 * sin(time * 1.3 + h * 20.0);
            lit = max(lit, a * brightness * (1.0 - fall * 0.7));
            heat = max(heat, a * clamp(nervous + band, 0.0, 1.0));
        }
    }
    vec3 tone = mix(ink.rgb, danger.rgb, alert);
    vec3 colour = base.rgb + tone * lit * 1.15 + tone * heat * 0.35;
    fragColor = vec4(colour, 1.0) * qt_Opacity;
}
