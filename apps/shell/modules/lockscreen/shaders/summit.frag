#version 440
// Wysun lock · the founder's film breaking through the refinement screen. The film (FounderFilm.qml) is
// shown in clustered blots that spread as `reveal` grows, like the picture eating through the terminal;
// running `reveal` back down makes the terminal come back the same way.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float aspect;   // width / height
    float reveal;   // 0 the terminal .. 1 the film
};
layout(binding = 1) uniform sampler2D source;

float hash(vec2 p) {
    p = fract(p * vec2(127.1, 311.7));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void main() {
    // Blots: coarse cells whose order follows smooth noise (so they cluster) with a little scatter.
    vec2 blot = floor(qt_TexCoord0 * vec2(60.0 * aspect, 60.0));
    float order = noise(blot * 0.1) * 0.55 + noise(blot * 0.35 + 5.0) * 0.25 + hash(blot) * 0.2;
    float shown = step(order, reveal * 1.15 - 0.1);
    fragColor = texture(source, qt_TexCoord0) * shown * qt_Opacity;
}
