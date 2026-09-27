#!/usr/bin/env python3
"""
youtube_to_pdf.py

Turn a YouTube video into a PDF "slide deck" of its visually distinct frames.
Give it just a link — it downloads the video, samples frames every few
seconds, keeps only the ones that changed meaningfully (so a talking-head
video doesn't produce hundreds of near-identical pages), and stitches the
survivors into a single PDF.

Usage:
    python youtube_to_pdf.py "https://www.youtube.com/watch?v=XXXXXXXX"
    python youtube_to_pdf.py URL -o lecture.pdf
    python youtube_to_pdf.py URL --interval 3 --threshold 5
    python youtube_to_pdf.py URL --keep-frames --frames-dir ./frames

Install dependencies first:
    pip install yt-dlp opencv-python-headless pillow numpy
"""

import argparse
import os
import shutil
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image


def download_video(url: str, dest_dir: str) -> str:
    """Download a YouTube video with yt-dlp and return the local file path."""
    import yt_dlp

    outtmpl = os.path.join(dest_dir, "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        # Cap at 720p -- plenty of resolution for reading slides/text,
        # and keeps downloads fast.
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)

    base, _ = os.path.splitext(filepath)
    mp4_path = base + ".mp4"
    if os.path.exists(mp4_path):
        return mp4_path
    if os.path.exists(filepath):
        return filepath
    raise FileNotFoundError("yt-dlp reported success but the output file wasn't found.")


def frame_difference_pct(prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
    """Return roughly what percent of pixels changed meaningfully between two frames."""
    if prev_gray.shape != curr_gray.shape:
        curr_gray = cv2.resize(curr_gray, (prev_gray.shape[1], prev_gray.shape[0]))
    diff = cv2.absdiff(prev_gray, curr_gray)
    changed_pixels = int(np.count_nonzero(diff > 25))  # per-pixel intensity threshold
    return 100.0 * changed_pixels / diff.size


def extract_distinct_frames(
    video_path: str,
    out_dir: str,
    interval: float = 2.0,
    threshold: float = 8.0,
    max_width: int = 1280,
) -> list:
    """
    Sample the video every `interval` seconds. Keep a sampled frame only if
    it differs from the last *kept* frame by at least `threshold` percent of
    pixels -- this is what collapses a static talking-head/slide segment
    down to one page instead of one page per sample.

    Returns the sorted list of saved JPG paths.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step_frames = max(1, int(round(interval * fps)))

    os.makedirs(out_dir, exist_ok=True)
    saved_paths = []
    prev_gray = None
    frame_idx = 0
    saved_idx = 0

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            break  # end of video (or an unreadable frame past the end)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        keep = prev_gray is None or frame_difference_pct(prev_gray, gray) >= threshold

        if keep:
            h, w = frame.shape[:2]
            if w > max_width:
                scale = max_width / w
                frame = cv2.resize(frame, (max_width, int(h * scale)))
            path = os.path.join(out_dir, f"frame_{saved_idx:04d}.jpg")
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved_paths.append(path)
            prev_gray = gray
            saved_idx += 1

        frame_idx += step_frames

    cap.release()
    return saved_paths


def images_to_pdf(image_paths: list, output_pdf: str) -> None:
    if not image_paths:
        raise ValueError("No frames were extracted, so there's nothing to put in the PDF.")
    images = [Image.open(p).convert("RGB") for p in image_paths]
    images[0].save(output_pdf, save_all=True, append_images=images[1:])


def youtube_to_pdf(
    url: str,
    output_pdf: str = "output.pdf",
    interval: float = 2.0,
    threshold: float = 8.0,
    keep_frames: bool = False,
    frames_dir: str = None,
) -> str:
    work_dir = tempfile.mkdtemp(prefix="yt2pdf_")
    video_dir = os.path.join(work_dir, "video")
    frames_out = frames_dir or os.path.join(work_dir, "frames")
    os.makedirs(video_dir, exist_ok=True)

    try:
        print("Downloading video...")
        video_path = download_video(url, video_dir)

        print("Sampling and de-duplicating frames...")
        frame_paths = extract_distinct_frames(
            video_path, frames_out, interval=interval, threshold=threshold
        )
        print(f"Kept {len(frame_paths)} distinct frame(s).")

        print("Building PDF...")
        images_to_pdf(frame_paths, output_pdf)
        print(f"Done: {os.path.abspath(output_pdf)}")
        return output_pdf
    finally:
        if not keep_frames:
            shutil.rmtree(work_dir, ignore_errors=True)
        elif frames_dir is None:
            print(f"(Temp files, including frames, left at: {work_dir})")


def main():
    parser = argparse.ArgumentParser(
        description="Turn a YouTube video into a PDF of its visually distinct frames."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-o", "--output", default="output.pdf", help="Output PDF path (default: output.pdf)")
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Seconds between sampled frames (default: 2.0). Smaller = won't miss quick slide changes, but slower.",
    )
    parser.add_argument(
        "--threshold", type=float, default=8.0,
        help="Percent of pixels that must change for a frame to be kept (default: 8.0). "
             "Lower = more sensitive (keeps more frames), higher = only keeps big changes.",
    )
    parser.add_argument(
        "--keep-frames", action="store_true",
        help="Don't delete the extracted JPG frames after building the PDF.",
    )
    parser.add_argument(
        "--frames-dir", default=None,
        help="Directory to save extracted frames into (implies --keep-frames).",
    )
    args = parser.parse_args()

    keep = args.keep_frames or args.frames_dir is not None
    try:
        youtube_to_pdf(
            args.url,
            output_pdf=args.output,
            interval=args.interval,
            threshold=args.threshold,
            keep_frames=keep,
            frames_dir=args.frames_dir,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
