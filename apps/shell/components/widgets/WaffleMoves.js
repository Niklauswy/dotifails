// The waffle's moves (Waffle.qml): poses for mascot.frag, as plain functions of time.
//   dance(beat)    32 beats with headphones; the caller runs `beat` at the music's tempo
//   story(seconds) a 16 s loop: waves, yawns, sleeps standing, wakes with a start, stretches, waves
.pragma library

function clamp01(v) {
    return Math.max(0, Math.min(1, v));
}
function ease(v) {
    const x = clamp01(v);
    return x * x * (3 - 2 * x);
}
function bump(t, from, to) {
    return Math.sin(Math.PI * clamp01((t - from) / (to - from)));
}

// ------------------------------------------------ the dance (music panel)
// 32 beats, one per beat of the song (Waffle.qml runs them at the music's tempo).
// Nothing turns faster than once every two beats, so the eyes never dart around.
function dance(b) {
    const p = {turn: 0, walk: 0, stride: 0, wave: 0, waving: 0, squash: 0, tuck: 0, talk: 0, blink: 0, mood: 0, hop: 0};
    const inBeat = b % 1;
    // Every beat lands with a gentle bob.
    const bob = -0.12 * Math.exp(-inBeat * 6) + 0.04 * Math.sin(inBeat * Math.PI);
    p.squash = bob;
    if (b < 8) {
        // The groove: swaying slowly, eyes shut with delight, singing along.
        p.turn = 0.12 * Math.sin(Math.PI * b / 4);
        p.mood = 2;
        p.blink = b > 1.5 && b < 6.5 ? 1 : 0;
        p.talk = b > 2 && b < 6 ? 0.35 + 0.35 * Math.sin(b * Math.PI) : 0;
    } else if (b < 16) {
        // Side steps: two to the right, two to the left, twice.
        const k = b - 8;
        p.turn = 0.22 * Math.sin(Math.PI * k / 4);
        p.walk = k / 2;
        p.stride = 0.6 * ease(k * 2) * ease((8 - k) * 2);
        p.talk = 0.3 + 0.3 * Math.sin(b * Math.PI);
        p.blink = Math.abs(k - 5) < 0.1 ? 1 : 0;
    } else if (b < 24) {
        // A slow wave to the audience, then two hops with the legs tucked.
        const k = b - 16;
        if (k < 4) {
            p.waving = ease(k * 2) * ease((4 - k) * 2);
            p.wave = k * 0.75;
            p.talk = 0.5 + 0.4 * Math.sin(b * Math.PI);
        } else {
            const h = Math.max(bump(k, 4.2, 5.6), bump(k, 6.2, 7.6));
            p.hop = h;
            p.tuck = 0.8 * h;
            p.squash = h > 0.05 ? 0.3 * h : bob * 1.6;
            p.mood = 2;
        }
    } else {
        // Down low, then up with the arms high, a held pose, and back into the groove.
        const k = b - 24;
        const down = bump(k, 0, 3);
        const up = bump(k, 3, 6.5);
        p.squash = -0.3 * down + 0.45 * up + bob * (1 - Math.max(down, up));
        p.mood = up > 0.3 ? 2 : 0;
        p.talk = up > 0.5 ? 0.8 : 0;
        p.blink = Math.abs(k - 7) < 0.1 ? 1 : 0;
    }
    return p;
}

// ------------------------------------------------ the story (session panel)
function story(t) {
    const p = {turn: 0, walk: 0, stride: 0, wave: 0, waving: 0, squash: 0, tuck: 0, talk: 0, blink: 0, mood: 0, hop: 0};
    p.squash = 0.03 * Math.sin(t * 2.2);                    // breathing
    if (t < 2) {
        p.waving = ease(t * 4) * ease((2 - t) * 4);
        p.wave = t * 1.5;
        p.talk = 0.5 + 0.5 * Math.sin(t * 9);
    } else if (t < 3.2) {
        p.blink = Math.abs(t - 2.8) < 0.08 ? 1 : 0;
    } else if (t < 5) {
        // A big yawn: stretching up, mouth wide, eyes heavy.
        const y = bump(t, 3.2, 5);
        p.squash = 0.4 * y;
        p.mood = y > 0.3 ? 3 : 0;
        p.blink = 0.65 * y;
    } else if (t < 9.5) {
        // Asleep standing up: eyes shut, swaying, nodding.
        const sway = Math.sin((t - 5) * 1.6);
        p.blink = 1;
        p.mood = 1;
        p.turn = 0.07 * sway;
        p.squash = -0.06 + 0.05 * Math.sin((t - 5) * 2.4);
    } else if (t < 10.3) {
        // Startled awake: a jump, eyes wide.
        const h = bump(t, 9.5, 10.3);
        p.hop = h;
        p.tuck = 0.7 * h;
        p.squash = 0.4 * h;
        p.mood = 3;
    } else if (t < 11.8) {
        // Looking around: what did I miss?
        const k = (t - 10.3) / 1.5;
        p.turn = 0.3 * Math.sin(k * Math.PI * 2);
        p.mood = k < 0.5 ? 3 : 0;
    } else if (t < 13) {
        // A good stretch.
        p.squash = 0.45 * bump(t, 11.8, 13);
        p.blink = bump(t, 11.8, 13) > 0.6 ? 1 : 0;
        p.mood = 2;
    } else if (t < 15) {
        p.waving = ease((t - 13) * 4) * ease((15 - t) * 4);
        p.wave = (t - 13) * 1.5;
        p.talk = 0.5 + 0.5 * Math.sin(t * 9);
    }
    return p;
}

// ------------------------------------------------ the nap (music panel, nothing playing)
// Asleep standing up, headphones on: eyes shut, swaying and nodding, a slow breath; loops every 8 s.
function nap(t) {
    const p = {turn: 0, walk: 0, stride: 0, wave: 0, waving: 0, squash: 0, tuck: 0, talk: 0, blink: 1, mood: 1, hop: 0};
    p.turn = 0.07 * Math.sin(t * Math.PI / 4);
    p.squash = -0.06 + 0.05 * Math.sin(t * Math.PI / 2);
    return p;
}
