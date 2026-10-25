#version 440
// Wysun boot · the project file. A glowing line-art folder as the terminal shows it: a top card with
// tabs (the project's name goes on it), a hinge band with two rings and accordion clips, a lower
// panel with a foot. Browsing works like a split-flap index: the top card falls forward over the
// hinge, uncovering the next card, and its back lands over the lower panel.
//   flip   0..1  one card falling (0 and 1 are the resting states)
//   lit    0..1  the chosen card lights up (the click)
//   fade   0..1  the folder dissolves (the file opens)
// Units: the frame's height is 1, the origin is its centre, y grows downwards.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float aspect;    // width / height
    float flip;
    float lit;
    float fade;
    vec4 ink;        // phosphor
    vec4 core;       // the hot centre of a line
};

const float STROKE = 0.0048;
const float HINGE = -0.03;          // where the cards meet the band
const float PANEL = 0.33;           // height of a card
const float PI = 3.14159265;

float box(vec2 p, vec2 a, vec2 b, float r) {
    vec2 c = (a + b) * 0.5;
    vec2 h = (b - a) * 0.5;
    vec2 q = abs(p - c) - h + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float hash(float n) {
    return fract(sin(n * 91.3458) * 47453.5453);
}

// A card as a filled shape (signed), with its two tabs on top; y measured up from the hinge.
float cardShape(vec2 q) {
    float d = box(q, vec2(-0.24, HINGE - PANEL), vec2(0.24, HINGE), 0.016);
    d = min(d, box(q, vec2(-0.19, HINGE - PANEL - 0.03), vec2(-0.11, HINGE - PANEL + 0.01), 0.008));
    d = min(d, box(q, vec2(0.1, HINGE - PANEL - 0.036), vec2(0.21, HINGE - PANEL + 0.01), 0.01));
    return d;
}

float lowerShape(vec2 p) {
    return min(box(p, vec2(-0.24, 0.03), vec2(0.24, 0.33), 0.016), box(p, vec2(0.05, 0.25), vec2(0.21, 0.37), 0.014));
}

// The band and its hardware, always in front of the cards.
float hardware(vec2 p) {
    float d = abs(box(p, vec2(-0.262, -0.022), vec2(0.262, 0.022), 0.02));
    for (int k = -1; k <= 1; k += 2) {
        float x = float(k) * 0.09;
        d = min(d, abs(box(p, vec2(x - 0.013, -0.05), vec2(x + 0.013, 0.05), 0.012)));
        for (int r = 0; r < 3; r++) {
            float rx = float(k) * (0.282 + 0.024 * float(r));
            d = min(d, abs(box(p, vec2(rx - 0.008, -0.065), vec2(rx + 0.008, 0.065), 0.006)));
        }
    }
    return d;
}

// The falling card in screen space: squashed towards the hinge by |cos|, its free edge nearer to the
// viewer (wider). Returns its signed distance (gradient-corrected) and whether p is on its back.
float falling(vec2 p, out float back, out vec2 local) {
    float angle = flip * PI;
    float c = cos(angle);
    float squash = max(abs(c), 0.02);
    back = c < 0.0 ? 1.0 : 0.0;
    float along = (c >= 0.0 ? HINGE - p.y : p.y - HINGE) / squash;      // distance from the hinge on the card
    float widen = 1.0 + 0.18 * sin(angle) * clamp(along / PANEL, 0.0, 1.2);
    local = vec2(p.x / widen, HINGE - along);
    float e = 0.002;
    float d = cardShape(local);
    vec2 grad = vec2(cardShape(local + vec2(e, 0.0)) - d, cardShape(local + vec2(0.0, e)) - d) / e;
    d /= max(length(grad / vec2(widen, squash)), 1e-3);
    if (along < -0.01)
        d = 1.0;        // the card never reaches past its hinge
    return d;
}

void main() {
    vec2 p = (qt_TexCoord0 - 0.5) * vec2(aspect, 1.0);

    float onBack;
    vec2 local;
    float moving = flip > 0.0 && flip < 1.0 ? falling(p, onBack, local) : 1.0;
    bool covered = moving < 0.0;

    // The resting cards: the next one on top (hidden where the falling card covers it), the lower panel.
    float d = hardware(p);
    if (!covered || onBack > 0.5)
        d = min(d, abs(cardShape(p)));
    if (!covered || onBack < 0.5)
        d = min(d, abs(lowerShape(p)));
    if (flip > 0.0 && flip < 1.0) {
        d = min(d, abs(moving));
        // The back of a card: a few ruled lines.
        if (onBack > 0.5 && covered && abs(local.x) < 0.2 && local.y < HINGE - 0.06 && local.y > HINGE - PANEL + 0.05) {
            float ruled = abs(fract((HINGE - local.y) / 0.07) - 0.5) * 0.07;
            d = min(d, ruled * abs(cos(flip * PI)));
        }
    }
    d = max(d - STROKE, 0.0);

    float line = 1.0 - smoothstep(0.0, 0.0026, d);
    float glow = 0.5 * exp(-d * 75.0) + 0.2 * exp(-d * 26.0);
    // The chosen card glows from inside when it is clicked.
    float card = cardShape(p);
    float inner = lit * 0.22 * (1.0 - smoothstep(-0.01, 0.0, card));
    float intensity = (line * (1.0 + lit * 0.4) + glow + inner) * (1.0 - fade);

    // The file opens: sparks rise out of the hinge as the folder dissolves.
    float sparks = 0.0;
    for (int i = 0; i < 40; i++) {
        float n = float(i);
        float age = fade * 1.4 - hash(n) * 0.4;
        if (age <= 0.0)
            continue;
        vec2 spark = vec2(mix(-0.26, 0.26, hash(n + 7.1)), HINGE - age * mix(0.25, 0.6, hash(n + 3.3)));
        float r = length(p - spark);
        sparks += (1.0 - smoothstep(0.6, 1.4, age)) * (exp(-r * r * 60000.0) + 0.3 * exp(-r * 80.0));
    }
    intensity += sparks;

    vec3 colour = mix(ink.rgb, core.rgb, clamp(line * (0.55 + lit * 0.3) * (1.0 - fade) + sparks * 0.4, 0.0, 1.0));
    vec2 edge = abs(qt_TexCoord0 - 0.5) * 2.0;
    intensity *= 1.0 - smoothstep(0.82, 1.0, max(edge.x, edge.y));
    float alpha = clamp(intensity, 0.0, 1.0);
    fragColor = vec4(colour * alpha, alpha) * qt_Opacity;
}
