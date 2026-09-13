"""Extract unmodified frames; never equate extraction with visual verification."""
import argparse
import _runtime
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path


def extract(video, out, start, end, step, audio=False):
    if not all(math.isfinite(x) for x in (start, end, step)) or start < 0 or end < start or step <= 0:
        raise ValueError('Require finite 0 <= start <= end and step > 0')
    if (end - start) / step > 500:
        raise ValueError('At most 501 frames per extraction; split the interval')
    import cv2
    video, out = Path(video).resolve(), Path(out).resolve()
    if not video.is_file():
        raise ValueError('Video not found')
    if out.exists():
        raise ValueError('Output directory already exists; choose a new evidence directory')
    if audio and not shutil.which('ffmpeg'):
        raise ValueError('Audio extraction requires ffmpeg on PATH; omit --audio for visual-only mode')
    cap = cv2.VideoCapture(str(video))
    try:
        fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or fps <= 0 or count <= 0:
            raise ValueError('Cannot obtain frame rate/count')
        if end >= count / fps:
            raise ValueError('Requested end is outside the video')
        out.mkdir(parents=True)
        records, previous = [], None
        for i in range(int(math.floor((end - start) / step + 1e-8)) + 1):
            requested = start + i * step
            index = int(round(requested * fps))
            index = min(index, int(count) - 1)
            if index == previous:
                continue
            previous = index
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                raise ValueError('Cannot decode frame ' + str(index))
            decoded_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
            pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            actual = pts if pts > 0 or decoded_index == 0 else decoded_index / fps
            name = f'frame_{i:04d}_{actual:010.3f}.jpg'
            ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 96])
            if not ok:
                raise ValueError('Cannot encode frame')
            (out / name).write_bytes(encoded.tobytes())
            records.append({'requested_seconds': requested, 'seconds': actual,
                            'frame_index': decoded_index, 'file': name,
                            'sha256': hashlib.sha256(encoded.tobytes()).hexdigest()})
        manifest = {'source': str(video), 'fps': fps, 'start': start, 'end': end,
                    'step': step, 'timestamp_note': 'Decoder PTS where available; otherwise frame/fps estimate. Verify VFR alignment.',
                    'frames': records, 'observed': False, 'audio_listened': False}
        if audio:
            subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-n', '-i', str(video),
                            '-ss', str(start), '-t', str(end - start), '-vn',
                            '-ac', '1', '-ar', '16000', str(out / 'audio.wav')],
                           check=True, capture_output=True, timeout=120)
            manifest['audio_offset_seconds'] = start
        (out / 'frames.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            from PIL import Image, ImageDraw
            for page_start in range(0, len(records), 20):
                page = records[page_start:page_start + 20]
                sheet = Image.new('RGB', (1280, math.ceil(len(page) / 4) * 208), '#141414')
                draw = ImageDraw.Draw(sheet)
                for j, rec in enumerate(page):
                    x, y = (j % 4) * 320, (j // 4) * 208
                    with Image.open(out / rec['file']) as im:
                        im.thumbnail((320, 180))
                        sheet.paste(im, (x, y))
                    draw.text((x + 8, y + 183), f"{rec['seconds']:.3f}s / frame {rec['frame_index']}", fill='white')
                sheet.save(out / f'contact_{page_start // 20 + 1:02d}.jpg', quality=92)
        except ImportError:
            manifest['contact_sheet_note'] = 'Pillow unavailable; individual frames exist'
            (out / 'frames.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return manifest
    finally:
        cap.release()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video'); p.add_argument('--out', required=True)
    p.add_argument('--start', type=float, required=True); p.add_argument('--end', type=float, required=True)
    p.add_argument('--step', type=float, default=0.5); p.add_argument('--audio', action='store_true')
    args = p.parse_args()
    try:
        result = extract(args.video, args.out, args.start, args.end, args.step, args.audio)
        print(json.dumps({'frames': len(result['frames']), 'out': args.out}, ensure_ascii=True))
    except (ValueError, ImportError, OSError, subprocess.SubprocessError) as exc:
        p.exit(2, str(exc) + '\n')
