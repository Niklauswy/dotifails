"""The H.264 level a video really needs.

x264 picks level 6.2 when it does not know the frame rate (Wysun Recorder encodes with
``-fps_mode passthrough``), and phones refuse any stream declared above 5.2 even when it is
small. The Recorder declares the right level; LANShare rewrites old files' level on the fly.
"""

# level → (max frame size in macroblocks, max macroblocks per second), H.264 Annex A.
LEVELS = (('3.1', 3600, 108000), ('3.2', 5120, 216000), ('4.0', 8192, 245760), ('4.1', 8192, 245760),
          ('4.2', 8704, 522240), ('5.0', 22080, 589824), ('5.1', 36864, 983040), ('5.2', 36864, 2073600))
PHONE_MAX = 52          # level_idc phones decode (iPhone, most Android)


def level_for(width, height, fps=60):
    """The smallest level ('4.2') for that size and rate, or None beyond what phones play (leave it)."""
    frame = ((int(width) + 15) // 16) * ((int(height) + 15) // 16)
    rate = frame * max(1.0, float(fps or 60))
    for name, max_frame, max_rate in LEVELS:
        if frame <= max_frame and rate <= max_rate:
            return name
    return None


def too_high(meta):
    """True for ffprobe metadata of an H.264 stream declared above what phones accept."""
    return meta.get('vcodec') == 'h264' and int(meta.get('level') or 0) > PHONE_MAX
