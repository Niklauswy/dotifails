#version 440
// The farewell mascot: an original 1930s rubber-hose office clock. A big round clock face with a
// bezel and hour marks, short thin legs in big round shoes, thin arms with cuffs and white gloves.
// One pose per frame, driven by BootArt.qml:
//   turn     -1..1  0 faces the viewer; walking it turns a little (about ±0.3, three-quarter view) to
//                   the right (+) or the left (−): a flat clock face never shows its profile
//   walk     0..1   phase of the walk cycle (short bouncy steps, arms swinging against the legs)
//   stride   0..1   how much of the walk is applied (0 stands still)
//   wave     0..1   phase of a wave of the right hand; waving 0..1 how much
//   squash   −1..1  squash (−) and stretch (+) around the feet, for hops and anticipation
//   tuck     0..1   legs pulled up in the air
//   talk     0..1   mouth open; blink 0..1 eyelids closed
//   mood     0 cheer, 1 woe, 2 frolic (wide eyes, raised brows, laughing grin), 3 dread: the face's temper
// Units: the frame's height is 1, the origin is its centre, y grows downwards; the feet stand at GROUND.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float aspect;
    float turn;
    float walk;
    float stride;
    float wave;
    float waving;
    float squash;
    float tuck;
    float talk;
    float blink;
    float mood;
    float headphones;   // 1: wears headphones (the music panel)
    float plain;        // 1: no phosphor halo (for GIFs, whose transparency is all or nothing)
    vec4 ink;       // the face and the shoes
    vec4 core;      // gloves, eye whites, highlights
    vec4 base;      // the inked lines
};

const float PI = 3.14159265;
const float GROUND = 0.43;
const float RADIUS = 0.245;
const float LINE = 0.0075;      // legs and arms: thin inked lines

float segment(vec2 p, vec2 a, vec2 b) {
    vec2 v = b - a;
    return length(p - a - v * clamp(dot(p - a, v) / dot(v, v), 0.0, 1.0));
}

// A thin limb with a soft bend, as two segments.
float limb(vec2 p, vec2 a, vec2 b, float bend) {
    vec2 n = normalize(vec2(-(b - a).y, (b - a).x));
    vec2 k = (a + b) * 0.5 + n * bend;
    return min(segment(p, a, k), segment(p, k, b)) - LINE;
}

float ellipse(vec2 p, vec2 r) {
    return (length(p / r) - 1.0) * min(r.x, r.y);
}

mat2 rotation(float a) {
    return mat2(cos(a), -sin(a), sin(a), cos(a));
}

// A puffy cartoon glove pointing up in its own frame: palm, thumb and three fat fingers.
float glove(vec2 p) {
    float d = ellipse(p, vec2(0.04, 0.042));
    d = min(d, ellipse(p - vec2(-0.04, -0.012), vec2(0.016, 0.026)));
    for (int i = 0; i < 3; i++) {
        float x = float(i - 1) * 0.024;
        d = min(d, ellipse(p - vec2(x, -0.045 + abs(float(i - 1)) * 0.008), vec2(0.0125, 0.026)));
    }
    return d;
}

float arc(vec2 p, vec2 centre, float radius, float from, float to) {
    vec2 q = p - centre;
    float a = atan(q.x, -q.y);
    if (a < from || a > to) {
        vec2 e1 = centre + radius * vec2(sin(from), -cos(from));
        vec2 e2 = centre + radius * vec2(sin(to), -cos(to));
        return min(length(p - e1), length(p - e2));
    }
    return abs(length(q) - radius);
}

void main() {
    vec2 p = (qt_TexCoord0 - 0.5) * vec2(aspect, 1.0);
    float facing = turn >= 0.0 ? 1.0 : -1.0;
    // The same direction without the jump at the front: what moves with it (feet, arms, lean) must
    // pass smoothly through facing the viewer.
    float heading = clamp(turn / 0.15, -1.0, 1.0);
    float side = abs(turn);

    // Squash and stretch around the feet, keeping the volume.
    float s = 1.0 + 0.3 * squash;
    p = vec2(p.x * s, GROUND + (p.y - GROUND) / s);

    // Short bouncy steps: the head drops on every footfall and springs up between them.
    float cycle = walk * 2.0 * PI;
    float bob = stride * (-0.03 * abs(sin(cycle)) + 0.012) - tuck * 0.04;
    vec2 centre = vec2(0.0, -0.07 + bob);
    float lean = stride * heading * 0.05 + stride * 0.04 * sin(cycle);  // a waddle
    vec2 body = rotation(lean) * (p - centre);

    // Legs and shoes.
    float lines = 1.0;
    float shoes = 1.0;
    for (int i = 0; i < 2; i++) {
        float k = i == 0 ? -1.0 : 1.0;
        float phase = cycle + (i == 0 ? 0.0 : PI);
        vec2 hip = centre + vec2(k * 0.065, RADIUS - 0.02);
        float swing = stride * 0.05 * sin(phase);      // short steps: the feet never cross
        float lift = stride * 0.04 * max(0.0, cos(phase)) + tuck * 0.09;
        vec2 foot = vec2(hip.x + heading * swing + k * 0.012, GROUND - 0.03 - lift);
        lines = min(lines, limb(p, hip, foot, k * 0.006 * (1.0 - side) + tuck * 0.03 * k));
        vec2 toe = vec2(mix(k * 0.03, heading * 0.04, side), 0.0);
        vec2 shoe = p - foot - toe - vec2(0.0, 0.006);
        shoes = min(shoes, ellipse(shoe, vec2(0.068, 0.036)));
        shoes = min(shoes, ellipse(shoe - vec2(-toe.x * 0.6, -0.018), vec2(0.03, 0.02)));    // the heel's top
    }

    // Arms from the rim of the clock, with striped cuffs and gloves.
    float gloves = 1.0;
    float cuffs = 1.0;
    for (int i = 0; i < 2; i++) {
        float k = i == 0 ? -1.0 : 1.0;
        vec2 shoulder = centre + rotation(-lean) * vec2(k * RADIUS * mix(0.97, 0.3, side), 0.05);
        float swing = stride * 0.08 * sin(cycle + (i == 0 ? PI : 0.0));
        vec2 rest = shoulder + vec2(k * mix(0.085, 0.05, side) + heading * swing, 0.085);
        vec2 up = shoulder + vec2(k * 0.07, -0.12);
        vec2 hand = mix(rest, up, max(squash, 0.0) * 0.9 + tuck * 0.5);
        float angle = k * (1.3 - 0.5 * max(squash, 0.0)) + (mood == 1.0 ? k * 0.6 : 0.0);
        if (mood == 1.0 && waving == 0.0)
            hand = shoulder + vec2(k * mix(0.06, 0.02, side), 0.13);          // woe: arms hang
        if (i == 1 && waving > 0.0) {
            float w = sin(wave * 2.0 * PI);
            vec2 raised = shoulder + vec2(0.1 + 0.04 * w, -0.15 + 0.012 * abs(w));
            hand = mix(hand, raised, waving);
            angle = mix(angle, 0.45 * sin(wave * 2.0 * PI - 0.9), waving);    // the wrist trails
        }
        vec2 dir = normalize(hand - shoulder);
        lines = min(lines, limb(p, shoulder, hand - dir * 0.03, k * 0.01));
        vec2 cuff = hand - dir * 0.035;
        cuffs = min(cuffs, ellipse(rotation(-atan(dir.x, dir.y)) * (p - cuff), vec2(0.022, 0.013)));
        gloves = min(gloves, glove(rotation(angle) * (p - hand)));
    }

    float head = length(body) - RADIUS;
    // Headphones: a band over the top of the head and two cups on its sides.
    float phones = 1.0;
    if (headphones > 0.5) {
        float band = arc(body, vec2(0.0, 0.0), RADIUS * 1.09, -1.3, 1.3) - 0.014;
        float cups = min(ellipse(body - vec2(-RADIUS * 1.02, 0.0), vec2(0.045, 0.075)),
                         ellipse(body - vec2(RADIUS * 1.02, 0.0), vec2(0.045, 0.075)));
        phones = min(band, cups);
    }
    float shapes = min(min(min(head, shoes), min(gloves, cuffs)), phones);
    float silhouette = min(shapes, lines);

    // Fill colours; everything inked with a heavy dark contour.
    vec3 colour = base.rgb;                                  // legs and arms are ink lines
    if (shoes < 0.0) colour = ink.rgb * 0.85;
    if (cuffs < 0.0) colour = mix(core.rgb, ink.rgb, 0.4);
    if (gloves < 0.0) colour = core.rgb;
    if (head < 0.0) colour = mix(ink.rgb, core.rgb, 0.15);
    bool onPhones = phones < 0.0;

    if (head < 0.0) {
        // The bezel: a second ring inside the rim.
        float bezel = abs(length(body) - RADIUS * 0.9) - 0.004;
        colour = mix(colour, base.rgb, (1.0 - smoothstep(0.0, 0.003, bezel)) * 0.85);
        // Hour marks: bars at 12, 3, 6 and 9, dots at the other hours. They turn with the head.
        for (int i = 0; i < 12; i++) {
            float a = float(i) * PI / 6.0;
            vec2 v = vec2(sin(a) * mix(1.0, 0.7, side), -cos(a));
            float m = (i % 3 == 0) ? segment(body, v * 0.205, v * 0.165) - 0.007 : length(body - v * 0.19) - 0.006;
            colour = mix(colour, base.rgb, 1.0 - smoothstep(0.0, 0.003, m));
        }

        vec2 face = body - vec2(turn * 0.07, 0.0);
        float woe = mood == 1.0 ? 1.0 : 0.0;
        float frolic = mood == 2.0 ? 1.0 : 0.0;
        float dread = mood == 3.0 ? 1.0 : 0.0;

        // Eyes: tall ovals with pupils and a highlight; the far one narrows in profile.
        for (int i = -1; i <= 1; i += 2) {
            float k = float(i);
            float far = (k * facing < 0.0) ? side : 0.0;
            vec2 eye = face - vec2(k * 0.062 * (1.0 - 0.3 * side), -0.06);
            vec2 size = vec2(0.042 * (1.0 - 0.45 * far), 0.062) * (1.0 + 0.15 * dread);
            float open = max(1.0 - blink, 0.0);
            open *= 1.0 + 0.08 * frolic;                           // frolic: eyes wide with delight
            if (woe > 0.0)
                open = min(open, 0.75);                            // heavy lids
            if (open < 0.1) {
                // A closed eye: a curved line.
                // ^ ^ when laughing; u u when sleepy or sad (woe). `eye` is already relative to the eye.
                float lid = arc(vec2(eye.x, woe > 0.0 ? -eye.y - 0.012 : eye.y), vec2(0.0, 0.03), 0.046, -1.15, 1.15) - 0.0085;
                colour = mix(colour, base.rgb, 1.0 - smoothstep(0.0, 0.003, lid));
            } else {
                float white = ellipse(eye, vec2(size.x, size.y * open));
                colour = mix(colour, base.rgb, 1.0 - smoothstep(0.0, 0.004, abs(white) - 0.004));
                colour = mix(colour, core.rgb, 1.0 - smoothstep(-0.002, 0.002, white + 0.004));
                // The lid drawn as a line across the top when it is heavy.
                if (open < 1.0) {
                    float lidLine = abs(eye.y + size.y * open * 0.75) - 0.004;
                    colour = mix(colour, base.rgb, (1.0 - smoothstep(0.0, 0.003, lidLine)) * step(white, 0.0));
                }
                // The eyes look where it walks.
                vec2 look = vec2(heading * 0.016, -0.012 + woe * 0.028 - frolic * 0.01);
                float pupilSize = dread > 0.0 ? 0.012 : 0.022;
                float pupil = ellipse(eye - look - vec2(0.0, 0.008), vec2(pupilSize * (1.0 - 0.4 * far), pupilSize * 1.5));
                colour = mix(colour, base.rgb, (1.0 - smoothstep(-0.002, 0.002, pupil)) * step(white, 0.0));
                float shine = length(eye - look - vec2(0.008, -0.006)) - 0.006;
                colour = mix(colour, core.rgb, (1.0 - smoothstep(-0.001, 0.001, shine)) * step(white, 0.0));
            }
            // Brows: worried (inner ends up) for woe and dread, raised arcs otherwise.
            float raise = dread * 0.02;
            float brow;
            if (woe + dread > 0.0)
                brow = segment(face, vec2(k * 0.062 - 0.032, -0.155 - raise - (k < 0.0 ? 0.0 : 0.025) * (woe + dread)),
                                     vec2(k * 0.062 + 0.032, -0.155 - raise - (k < 0.0 ? 0.025 : 0.0) * (woe + dread))) - 0.005;
            else
                brow = arc(face, vec2(k * 0.062 * (1.0 - 0.3 * side), -0.11 - frolic * 0.012), 0.05, -0.6, 0.6) - 0.004;
            colour = mix(colour, base.rgb, 1.0 - smoothstep(0.0, 0.003, brow));
        }

        // The mouth, by temper.
        vec2 mouth = face - vec2(0.0, 0.07);
        float line = 1.0;
        float hole = 1.0;
        if (woe > 0.0) {
            line = arc(face, vec2(0.0, 0.135), 0.05, -1.0, 1.0) - 0.006;              // a frown
            // A tear when sad and awake; none while it sleeps.
            if (blink < 0.5) {
                float tear = ellipse(face - vec2(0.095, 0.0), vec2(0.012, 0.02));
                colour = mix(colour, core.rgb, 1.0 - smoothstep(-0.002, 0.002, tear));
                line = min(line, abs(tear) - 0.002);
            }
        } else if (dread > 0.0) {
            hole = ellipse(mouth - vec2(0.0, 0.01), vec2(0.026, 0.034));               // a small gasp
        } else {
            // Cheer and frolic: a wide grin that opens when it talks (frolic laughs with it wide open).
            float open = max(talk, frolic * 0.8);
            hole = max(ellipse(mouth, vec2(0.075, 0.025 + 0.045 * open)), -mouth.y - 0.004);
            line = arc(face, vec2(0.0, 0.0), 0.085, 2.2, 4.08) - 0.005;
            if (open > 0.05)
                line = 1.0;
        }
        colour = mix(colour, base.rgb, 1.0 - smoothstep(0.0, 0.003, line));
        colour = mix(colour, base.rgb, 1.0 - smoothstep(-0.002, 0.002, hole));
        float tongue = ellipse(mouth - vec2(0.0, 0.05), vec2(0.034, 0.022));
        float tongueIn = max(tongue, hole);
        colour = mix(colour, mix(ink.rgb, core.rgb, 0.3) * 0.75, (1.0 - smoothstep(-0.002, 0.002, tongueIn)) * step(0.05, max(talk, frolic)) * (1.0 - woe - dread));
        // A small nose.
        float nose = ellipse(face - vec2(turn * 0.02, 0.0), vec2(0.012, 0.009));
        colour = mix(colour, base.rgb, 1.0 - smoothstep(0.0, 0.002, nose));
    }

    // The headphones sit over everything on the head: dark band, cups in the face colour with a shine.
    if (onPhones) {
        colour = mix(base.rgb, ink.rgb, 0.35);
        vec2 cup = vec2(abs(body.x) - RADIUS * 1.02, body.y);
        if (length(cup / vec2(0.045, 0.075)) < 1.0)
            colour = mix(ink.rgb, core.rgb, 0.1) * (0.8 + 0.4 * step(0.3, -cup.y / 0.075 - cup.x / 0.045 * 0.5));
    }

    // The inked contour around every filled shape, and a faint phosphor glow outside.
    float outline = 1.0 - smoothstep(0.003, 0.0075, abs(shapes));
    float inside = 1.0 - smoothstep(-0.002, 0.002, silhouette);
    colour = mix(colour, base.rgb, outline * inside);
    float glow = 0.22 * exp(-max(silhouette, 0.0) * 100.0) * (1.0 - plain);
    float alpha = clamp(inside + glow, 0.0, 1.0);
    colour = mix(ink.rgb, colour, inside);
    fragColor = vec4(colour * alpha, alpha) * qt_Opacity;
}
