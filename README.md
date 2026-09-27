# 🎬 → 📄 YouTube-to-PDF

Turn any YouTube video into a flip-through PDF of its slides — paste a link, get a document.

Point it at a lecture, a conference talk, a tutorial, whatever — it downloads the video, watches for real visual changes, and keeps only the frames that matter as pages in a PDF. No more scrubbing through an hour of video to screenshot ten slides.

## How it works

1. **Downloads** the video with `yt-dlp` (capped at 720p — plenty for reading slides, and fast).
2. **Samples** a frame every few seconds and throws away ones that look the same as the last one it kept, so a static talking-head segment collapses to a single page instead of dozens of near-duplicates.
3. **Builds** a PDF from whatever's left, one frame per page.

## Requirements

- Python 3.8+
- **ffmpeg** — required by `yt-dlp` to merge the separate video/audio streams YouTube serves at anything above the lowest quality. Install it via your package manager:
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Termux (Android): `pkg install ffmpeg`
- Python packages:
  ```bash
  pip install yt-dlp opencv-python-headless pillow numpy
  ```

## Usage

```bash
python youtube_to_pdf.py "https://www.youtube.com/watch?v=XXXXXXXX"
```

That's it — defaults produce `output.pdf` in the current directory.

### Options

| Flag | Default | What it does |
|---|---|---|
| `-o, --output` | `output.pdf` | Output PDF path |
| `--interval` | `2.0` | Seconds between sampled frames. Lower = won't miss quick slide changes, but slower to run. |
| `--threshold` | `8.0` | % of pixels that must change for a frame to count as "new." Lower = more sensitive (keeps more frames); higher = only keeps big changes. |
| `--keep-frames` | off | Keep the extracted JPGs instead of deleting them |
| `--frames-dir` | temp dir | Directory to save frames into (implies `--keep-frames`) |

### Examples

```bash
# A talk with slow slide changes -- sample less often
python youtube_to_pdf.py URL --interval 3

# A fast-moving whiteboard demo -- catch more, keep more
python youtube_to_pdf.py URL --interval 1 --threshold 4

# Custom output name + keep the raw frames
python youtube_to_pdf.py URL -o lecture.pdf --frames-dir ./frames
```

## Running on Android (Termux)

Native Termux can't easily build OpenCV/NumPy from source (no matching wheels, and building them by hand is painful). Run it inside a Termux `proot-distro` Ubuntu environment instead, where `pip` gets normal prebuilt wheels:

```bash
pkg install proot-distro
proot-distro install ubuntu
proot-distro login ubuntu

# inside the Ubuntu environment (your phone's shared storage is
# already reachable at /sdcard):
apt update && apt install -y python3 python3-pip ffmpeg
pip install yt-dlp opencv-python-headless pillow numpy

python3 /sdcard/Download/youtube_to_pdf.py "URL" -o /sdcard/Download/output.pdf
```

## Notes

- Frame comparison is a simple grayscale pixel-difference — great for slides and screen-share content, less useful for anything with constant motion (it'll just keep every frame).
- Downloaded video and intermediate frames are cleaned up automatically unless `--keep-frames` is set.
