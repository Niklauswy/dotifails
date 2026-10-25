#version 440
// Wysun boot · the terminal. The office CRT seen from the desk: a cream case, a dark slate face, a
// bulging glass that holds the ceiling lights' reflections, a camera eye and a knob. Plymouth draws
// the file, the header progress and the messages on the glass.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 res;           // canvas size in pixels
    vec2 glassCentre;   // pixels
    vec2 glassHalf;     // pixels
    vec4 room;          // the wall behind the desk
    vec4 shell;         // cream plastic case
    vec4 bezel;         // dark slate face
    vec4 glass;         // phosphor glass, powered
    vec4 glare;         // ceiling lights
};

float box(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// A pillow-shaped CRT tube: a superellipse, in pixels (approximate distance, fine for soft edges).
float tube(vec2 p, vec2 half_) {
    vec2 q = abs(p) / half_;
    float n = 5.0;
    float k = pow(pow(q.x, n) + pow(q.y, n), 1.0 / n);
    return (k - 1.0) * min(half_.x, half_.y);
}

float blob(vec2 p, vec2 centre, vec2 radius) {
    vec2 q = (p - centre) / radius;
    return exp(-dot(q, q) * 2.2);
}

void main() {
    vec2 px = qt_TexCoord0 * res;
    vec2 caseCentre = glassCentre + vec2(25.0, 0.0);
    vec2 caseHalf = glassHalf + vec2(155.0, 125.0);

    // The wall: dark green, a lamp somewhere above on the left.
    vec3 colour = room.rgb * (0.7 + 0.45 * exp(-length(px - vec2(res.x * 0.12, -res.y * 0.2)) / (res.x * 0.55)));

    // The case drops a soft shadow on the wall.
    float dCase = box(px - caseCentre, caseHalf, 150.0);
    colour *= 1.0 - 0.55 * exp(-max(dCase, 0.0) / 45.0);

    // Cream plastic rim, rounded away at its outer edge.
    float rim = 1.0 - smoothstep(-1.0, 1.0, dCase);
    vec3 plastic = shell.rgb * (0.86 + 0.1 * (1.0 - qt_TexCoord0.y) - 0.05 * qt_TexCoord0.x);
    plastic *= 1.0 - 0.4 * smoothstep(-16.0, 0.0, dCase);
    colour = mix(colour, plastic, rim);

    // The slate face, slightly lighter towards the top where the room light lands.
    float dFace = box(px - caseCentre, caseHalf - 20.0, 132.0);
    float face = 1.0 - smoothstep(-1.0, 1.0, dFace);
    vec3 slate = bezel.rgb * (0.85 + 0.3 * (1.0 - qt_TexCoord0.y));
    slate *= 1.0 - 0.25 * smoothstep(-26.0, 0.0, dFace);      // the face bends into the rim
    slate += glare.rgb * 0.035 * smoothstep(-60.0, -6.0, dFace) * (1.0 - smoothstep(-6.0, 0.0, dFace));
    colour = mix(colour, slate, face);

    // Screws on the sides of the face, the camera eye above the glass, the knob below to the right.
    for (int side = -1; side <= 1; side += 2) {
        vec2 screw = caseCentre + vec2(float(side) * (caseHalf.x - 52.0), 0.0);
        float d = length(px - screw);
        colour = mix(colour, bezel.rgb * 0.55, 1.0 - smoothstep(6.0, 7.5, d));
        colour += glare.rgb * 0.06 * (1.0 - smoothstep(0.0, 3.0, length(px - screw + vec2(1.5, 1.5))));
    }
    vec2 eye = vec2(glassCentre.x, glassCentre.y - glassHalf.y - 52.0);
    float dEye = length(px - eye);
    colour = mix(colour, bezel.rgb * 0.3, 1.0 - smoothstep(10.0, 12.0, dEye));
    colour = mix(colour, bezel.rgb * 0.75, 1.0 - smoothstep(10.0, 12.0, abs(dEye - 13.0) + 10.0));
    colour += glare.rgb * 0.25 * (1.0 - smoothstep(0.0, 3.0, length(px - eye + vec2(3.0, 3.0))));
    vec2 knob = caseCentre + caseHalf - vec2(95.0, 70.0);
    float dKnob = length(px - knob);
    colour = mix(colour, bezel.rgb * 0.4, 1.0 - smoothstep(22.0, 24.0, dKnob));
    colour += glare.rgb * 0.05 * (1.0 - smoothstep(14.0, 22.0, length(px - knob + vec2(6.0, 6.0))));

    // The recess around the tube, then the glass itself.
    float dRecess = tube(px - glassCentre, glassHalf + 16.0);
    colour = mix(colour, bezel.rgb * 0.22, 1.0 - smoothstep(-2.0, 2.0, dRecess));
    vec2 g = (px - glassCentre) / glassHalf;       // -1..1 across the glass
    float dGlass = tube(px - glassCentre, glassHalf);
    float inside = 1.0 - smoothstep(-1.5, 1.5, dGlass);
    // The glass bulges: brighter in the middle, falling off towards the corners and into the recess.
    vec3 screen = glass.rgb * (1.08 - 0.42 * dot(g * g, vec2(0.8, 1.0)));
    screen *= 1.0 - 0.55 * smoothstep(-40.0, 0.0, dGlass);
    screen *= 1.0 - 0.18 * smoothstep(-0.2, -1.0, g.y);    // the face's shadow on the top of the glass
    // Ceiling lights reflected in the top of the glass, and a broad sheen on the lower left.
    float lights = blob(g, vec2(-0.56, -0.8), vec2(0.17, 0.065))
                 + blob(g, vec2(-0.04, -0.84), vec2(0.17, 0.06)) * 1.1
                 + blob(g, vec2(0.5, -0.8), vec2(0.15, 0.06)) * 0.9;
    screen += glare.rgb * lights * 0.42;
    screen += glare.rgb * 0.035 * blob(g, vec2(-0.45, 0.55), vec2(0.6, 0.45));
    // Fine scanlines of the phosphor.
    screen *= 0.965 + 0.035 * cos(px.y * 3.14159 * 2.0 / 3.0);
    colour = mix(colour, screen, inside);

    // The room is dim: a vignette pulls the eye to the glass.
    vec2 v = qt_TexCoord0 - vec2(0.48, 0.5);
    colour *= 1.0 - dot(v, v) * 0.9;
    fragColor = vec4(colour, 1.0) * qt_Opacity;
}
