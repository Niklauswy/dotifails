#version 440
// Wysun boot · the training tape. Turns a clean title card into a frame of a worn VHS played on a tube:
// a soft, low-resolution picture, whites that bloom, chroma smeared sideways with a coloured fringe,
// a tracking band that drags the picture near the bottom, ordered dithering, scanlines and the tube's
// curved, darker corners. Every effect is periodic or per row (no per-pixel grain): GRUB decodes the
// result with a slow PNG decoder, it has to compress well.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 res;
};
layout(binding = 1) uniform sampler2D source;

const float CELL = 2.0;     // the tape's resolution: one picture element is 2x2 screen pixels

float hash(float n) {
    return fract(sin(n * 127.1) * 43758.5453);
}

vec3 tap(vec2 uv, float dx) {
    return texture(source, uv + vec2(dx / res.x, 0.0)).rgb;
}

float bayer(vec2 c) {
    int index = int(mod(c.x, 4.0)) + int(mod(c.y, 4.0)) * 4;
    const float matrix[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0,
                                       3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
    return (matrix[index] + 0.5) / 16.0;
}

void main() {
    // The tube bulges: sample through a slight barrel distortion.
    vec2 centred = qt_TexCoord0 - 0.5;
    vec2 uv = 0.5 + centred * (1.0 + dot(centred, centred) * 0.06);
    vec2 cell = floor(uv * res / CELL);
    uv = (cell + 0.5) * CELL / res;
    float row = cell.y;

    // Tracking: the picture drags sideways in a band near the bottom.
    float band = smoothstep(0.925, 0.945, uv.y) * (1.0 - smoothstep(0.965, 0.985, uv.y));
    float drag = band * (18.0 + 10.0 * hash(floor(row / 2.0)));

    // A soft picture: luma blurred a little, chroma a lot, red late and blue early.
    vec3 soft = (tap(uv, drag) * 2.0 + tap(uv, drag - 2.0) + tap(uv, drag + 2.0)) / 4.0;
    vec3 colour = soft;
    colour.r = mix(soft.r, (tap(uv, drag - 4.0).r + tap(uv, drag - 7.0).r) * 0.5, 0.6);
    colour.b = mix(soft.b, (tap(uv, drag + 4.0).b + tap(uv, drag + 7.0).b) * 0.5, 0.5);

    // Whites bloom into the blue.
    vec3 bloom = vec3(0.0);
    for (int i = -3; i <= 3; i++)
        for (int j = -2; j <= 2; j++)
            bloom += texture(source, uv + vec2(float(i) * 5.0, float(j) * 4.0) / res).rgb;
    bloom /= 35.0;
    colour += max(bloom - 0.35, 0.0) * 0.45;

    // The tracking band is also brighter and washed out.
    colour = mix(colour, vec3(dot(colour, vec3(0.33))) * 1.25, band * 0.35);

    // Brightness bands rolling through the tape and the tube's falloff to the corners.
    colour *= 1.0 + 0.04 * sin(uv.y * 6.0 + 1.1) + 0.025 * sin(uv.y * 23.0 + 0.4);
    vec2 v = qt_TexCoord0 - 0.5;
    colour *= 1.0 - dot(v * vec2(0.95, 1.2), v * vec2(0.95, 1.2)) * 1.25;

    // Few colour steps, dithered; then the dark gap under every line.
    float levels = 16.0;
    colour = floor(colour * levels + bayer(cell)) / levels;
    float scan = mod(qt_TexCoord0.y * res.y, CELL) >= CELL - 1.0 ? 0.7 : 1.0;

    // Outside the bulged picture the tube is dark.
    vec2 edge = abs(uv - 0.5) * 2.0;
    float inside = 1.0 - smoothstep(0.985, 1.0, max(edge.x, edge.y));
    fragColor = vec4(clamp(colour, 0.0, 1.0) * scan * inside, 1.0) * qt_Opacity;
}
