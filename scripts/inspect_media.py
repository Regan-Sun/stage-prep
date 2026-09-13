"""Portable media capability probe. No inferred visual or audio observations."""
import argparse
import _runtime
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path


def inspect(path):
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError('Media file does not exist')
    result = {'file': str(source), 'bytes': source.stat().st_size,
              'opencv_available': importlib.util.find_spec('cv2') is not None,
              'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe'),
              'visual_observation': 'not_performed', 'audio_listened': False}
    if result['ffprobe']:
        proc = subprocess.run([result['ffprobe'], '-v', 'error', '-show_format',
                               '-show_streams', '-of', 'json', str(source)],
                              capture_output=True, text=True, encoding='utf-8', timeout=60)
        if proc.returncode == 0:
            result['probe'] = json.loads(proc.stdout)
        else:
            result['probe_error'] = proc.stderr[-2000:]
    if result['opencv_available']:
        import cv2
        cap = cv2.VideoCapture(str(source))
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            ok, _ = cap.read()
            result.update(frame_readable=bool(ok), fps=fps, frames=count,
                          estimated_duration=count / fps if fps > 0 else None,
                          width=cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                          height=cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            cap.release()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video')
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.video), ensure_ascii=True, indent=2))
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, str(exc) + '\n')
