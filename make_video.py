#!/usr/bin/env python3
"""
Cinematic birthday video generator.
Ken Burns + crossfade transitions + letterbox + title card.
"""
import os, subprocess, shutil
from PIL import Image

IMGDIR = "/home/user/Luisa-s-birthday/images"
TMPDIR = "/home/user/Luisa-s-birthday/tmp_segments"
OUTDIR = "/home/user/Luisa-s-birthday"
OUTPUT = os.path.join(OUTDIR, "happy_birthday_luisa.mp4")

W, H = 1920, 1080
FPS = 24
PHOTO_DUR = 6       # seconds each photo is shown
FADE_DUR = 1.0      # crossfade duration in seconds
TITLE_DUR = 3       # title card duration
OUTRO_DUR = 3       # outro card duration

# Cinematic letterbox: simulate 2.39:1 by adding black bars
BAR_H = 116         # (1080 - 1080/2.39) / 2 ≈ 116px per bar

# Gentle Ken Burns — max zoom 1.12 so faces stay in frame
# (name, z_expr, x_expr, y_expr)
KB = [
    ("zoom_in",   "min(zoom+0.0007,1.12)", "iw/2-(iw/zoom/2)",                          "ih/2-(ih/zoom/2)"),
    ("pan_right", "1.10",                  "0+(on/(total_frames-1))*(iw-iw/zoom)",       "ih/2-(ih/zoom/2)"),
    ("zoom_out",  "if(lte(zoom,1.0),1.10,max(1.0,zoom-0.0007))", "iw/2-(iw/zoom/2)",    "ih/2-(ih/zoom/2)"),
    ("pan_left",  "1.10",                  "(iw-iw/zoom)-(on/(total_frames-1))*(iw-iw/zoom)", "ih/2-(ih/zoom/2)"),
    ("zoom_in2",  "min(zoom+0.0007,1.12)", "iw/2-(iw/zoom/2)",                          "ih/2-(ih/zoom/2)"),
    ("pan_right", "1.10",                  "0+(on/(total_frames-1))*(iw-iw/zoom)",       "ih/2-(ih/zoom/2)"),
    ("zoom_out",  "if(lte(zoom,1.0),1.10,max(1.0,zoom-0.0007))", "iw/2-(iw/zoom/2)",    "ih/2-(ih/zoom/2)"),
    ("pan_left",  "1.10",                  "(iw-iw/zoom)-(on/(total_frames-1))*(iw-iw/zoom)", "ih/2-(ih/zoom/2)"),
    ("zoom_in",   "min(zoom+0.0007,1.12)", "iw/2-(iw/zoom/2)",                          "ih/2-(ih/zoom/2)"),
    ("zoom_out",  "if(lte(zoom,1.0),1.10,max(1.0,zoom-0.0007))", "iw/2-(iw/zoom/2)",    "ih/2-(ih/zoom/2)"),
]

os.makedirs(TMPDIR, exist_ok=True)

def run(cmd, desc=""):
    print(f"  >> {desc or cmd[:80]}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  STDERR: {result.stderr[-500:]}")
        raise RuntimeError(f"Command failed: {cmd[:80]}")
    return result

def make_segment(photo_num, kb_config):
    """Create a single Ken Burns clip — full image always visible, no cropping."""
    name, z_expr, x_expr, y_expr = kb_config
    infile = os.path.join(IMGDIR, f"photo_{photo_num:02d}.jpg")
    outfile = os.path.join(TMPDIR, f"seg_{photo_num:02d}.mp4")

    total_frames = PHOTO_DUR * FPS

    x_expr = x_expr.replace("total_frames", str(total_frames))
    y_expr = y_expr.replace("total_frames", str(total_frames))
    z_expr_safe = z_expr.replace("total_frames", str(total_frames))

    # Calculate the size each image fits into within W×H (no cropping)
    with Image.open(infile) as img:
        iw, ih = img.size
    scale = min(W / iw, H / ih)
    fw = (int(iw * scale) // 2) * 2   # fitted width  (even)
    fh = (int(ih * scale) // 2) * 2   # fitted height (even)

    # Scale up 1.25× to give Ken Burns headroom inside the image
    sw = (int(fw * 1.25) // 2) * 2
    sh = (int(fh * 1.25) // 2) * 2

    # zoompan crops into the 1.25× image and outputs at fitted size,
    # then we pad to full 1920×1080 — faces always fully visible
    vf = (
        f"scale={sw}:{sh},"
        f"zoompan=z='{z_expr_safe}':x='{x_expr}':y='{y_expr}'"
        f":d={total_frames}:s={fw}x{fh}:fps={FPS},"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1,"
        f"drawbox=x=0:y=0:w={W}:h={BAR_H}:color=black@1:t=fill,"
        f"drawbox=x=0:y={H-BAR_H}:w={W}:h={BAR_H}:color=black@1:t=fill,"
        f"vignette=PI/5"
    )

    cmd = (
        f'ffmpeg -y -loop 1 -framerate {FPS} -i "{infile}" '
        f'-vf "{vf}" '
        f'-t {PHOTO_DUR} -an '
        f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p '
        f'"{outfile}"'
    )
    run(cmd, f"Ken Burns segment {photo_num:02d} ({name})")
    return outfile

def make_title_card(text_line1, text_line2, duration, filename, fade_in=True, fade_out=True):
    """Create a title card with text on black."""
    outfile = os.path.join(TMPDIR, filename)
    total_frames = int(duration * FPS)
    fade_frames = int(FPS * 0.8)

    fade_filters = ""
    if fade_in:
        fade_filters += f",fade=t=in:st=0:d=0.8"
    if fade_out:
        fade_filters += f",fade=t=out:st={duration-0.8}:d=0.8"

    # Two-line title with elegant fonts
    drawtext = (
        f"drawtext=text='{text_line1}':"
        f"fontcolor=white:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2-60:"
        f"alpha='if(lt(t,0.5),t/0.5,if(gt(t,{duration-0.5}),(({duration})-t)/0.5,1))',"
        f"drawtext=text='{text_line2}':"
        f"fontcolor=0xF5C842:fontsize=44:x=(w-text_w)/2:y=(h-text_h)/2+60:"
        f"alpha='if(lt(t,0.8),t/0.8,if(gt(t,{duration-0.5}),(({duration})-t)/0.5,1))'"
    )

    vf = (
        f"color=c=black:size={W}x{H}:rate={FPS}:duration={duration},"
        f"{drawtext}"
        f",drawbox=x=0:y=0:w={W}:h={BAR_H}:color=black@1:t=fill"
        f",drawbox=x=0:y={H-BAR_H}:w={W}:h={BAR_H}:color=black@1:t=fill"
        f"{fade_filters}"
    )

    cmd = (
        f'ffmpeg -y -f lavfi -i "{vf}" '
        f'-t {duration} -an '
        f'-c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p '
        f'"{outfile}"'
    )
    run(cmd, f"Title card: {filename}")
    return outfile

def concat_with_xfade(segments, fade_dur=FADE_DUR, photo_dur=PHOTO_DUR):
    """Concatenate segments with xfade transitions."""
    outfile = os.path.join(TMPDIR, "slideshow.mp4")

    # Build xfade chain
    # Each segment is photo_dur long
    # Transition starts at cumulative_time - fade_dur
    # For title (3s) + photos (6s each) with 1s overlaps:
    #   seg0: 0..3  (title)
    #   seg1: 2..8  (photo 1, starts at 3-1=2 in xfade chain)
    #   etc.

    n = len(segments)
    if n == 1:
        shutil.copy(segments[0], outfile)
        return outfile

    # Build filter_complex for xfade
    # Duration info per segment (first is title, rest are photos)
    durations = []
    for i, s in enumerate(segments):
        if "title" in os.path.basename(s) or "outro" in os.path.basename(s):
            if "outro" in os.path.basename(s):
                durations.append(OUTRO_DUR)
            else:
                durations.append(TITLE_DUR)
        else:
            durations.append(PHOTO_DUR)

    # Build input list
    inputs = " ".join(f'-i "{s}"' for s in segments)

    # Build xfade filter chain
    # xfade offset = sum of previous durations - fade_dur * num_previous_transitions
    chains = []
    offset = durations[0] - fade_dur
    # First transition: [0][1] -> [v0]
    transition = "fade"
    chains.append(f"[0:v][1:v]xfade=transition={transition}:duration={fade_dur}:offset={offset:.3f}[v0]")

    for i in range(2, n):
        offset += durations[i-1] - fade_dur
        prev = f"v{i-2}"
        cur = f"v{i-1}"
        chains.append(f"[{prev}][{i}:v]xfade=transition={transition}:duration={fade_dur}:offset={offset:.3f}[{cur}]")

    last_label = f"v{n-2}"
    filter_complex = ";".join(chains)

    cmd = (
        f'ffmpeg -y {inputs} '
        f'-filter_complex "{filter_complex}" '
        f'-map "[{last_label}]" '
        f'-an -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p '
        f'"{outfile}"'
    )
    run(cmd, "Concat with xfade transitions")
    return outfile

def add_fade_in_out(infile, outfile, duration):
    """Add overall fade in/out to the final video."""
    cmd = (
        f'ffmpeg -y -i "{infile}" '
        f'-vf "fade=t=in:st=0:d=1,fade=t=out:st={duration-1.5}:d=1.5" '
        f'-c:v libx264 -preset fast -crf 17 -pix_fmt yuv420p '
        f'"{outfile}"'
    )
    run(cmd, "Final fade in/out")

print("=" * 60)
print("Building premium cinematic birthday video for Luisa")
print("=" * 60)

# 1. Create title card
print("\n[1/4] Creating title & outro cards...")
title_seg = make_title_card(
    "Feliz Cumpleanos",
    "Luisa ♥",
    TITLE_DUR,
    "title_card.mp4",
    fade_in=True,
    fade_out=False
)
outro_seg = make_title_card(
    "Con todo el amor",
    "del mundo ♥",
    OUTRO_DUR,
    "outro_card.mp4",
    fade_in=False,
    fade_out=True
)

# 2. Create Ken Burns segments for each photo
print("\n[2/4] Creating Ken Burns photo segments...")
photo_segs = []
for i in range(1, 11):
    kb = KB[(i-1) % len(KB)]
    seg = make_segment(i, kb)
    photo_segs.append(seg)

# 3. Concatenate all with xfade
print("\n[3/4] Concatenating with cinematic crossfades...")
all_segs = [title_seg] + photo_segs + [outro_seg]
slideshow = concat_with_xfade(all_segs)

# 4. Final output with overall fade
print("\n[4/4] Finalizing...")
# Calculate approximate total duration
n_segs = len(all_segs)
total_dur = TITLE_DUR + (PHOTO_DUR * 10) + OUTRO_DUR - (FADE_DUR * (n_segs - 1))
add_fade_in_out(slideshow, OUTPUT, total_dur)

# Cleanup tmp
shutil.rmtree(TMPDIR)

size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
print(f"\n{'='*60}")
print(f"Video ready: {OUTPUT}")
print(f"Estimated duration: ~{total_dur:.0f} seconds")
print(f"File size: {size_mb:.1f} MB")
print("=" * 60)
