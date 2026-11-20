"""Inspect an actual pipeline MP4, narration, and the rendered scene boundaries."""
from pathlib import Path
import json
import re
import subprocess
import sys


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def verify(job_dir):
    job_dir = Path(job_dir).resolve()
    video = job_dir / "explainer.mp4"
    media = probe(video)
    streams = {s["codec_type"]: s for s in media["streams"]}
    assert "video" in streams and "audio" in streams, "Expected both video and audio"
    delta = abs(float(streams["video"]["duration"]) - float(streams["audio"]["duration"]))
    assert delta < 0.05, f"Stream durations differ by {delta}s"
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
    assert decode.returncode == 0 and not decode.stderr.strip(), decode.stderr
    volume = subprocess.run(["ffmpeg", "-i", str(video), "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True, check=True)
    peak = float(re.search(r"max_volume: ([\d.-]+) dB", volume.stderr)[1])
    assert peak > -60, "Narration is effectively silent"
    manifest = next(job_dir.glob("**/partial_movie_file_list.txt"))
    clips = [line[11:-1] for line in manifest.read_text().splitlines() if line.startswith("file 'file:")]
    durations = [float(probe(clip)["format"]["duration"]) for clip in clips]
    plan = json.loads((job_dir / "plan.json").read_text())
    timings = json.loads((job_dir / "timing.json").read_text())
    index, start = 0, 0.0
    boundaries = []
    # These counts reflect the approved template's rendered animations and wait.
    for scene, timing in zip(plan["scenes"], timings):
        labels = (scene["bullets"] or [scene["heading"]])[:4]
        count = 4 if scene["type"] == "diagram_flow" and len(labels) > 1 else 3
        duration = sum(durations[index:index + count])
        index += count
        offset = start - timing["start"]
        assert abs(offset) < 0.05, f"Scene {scene['id']} offset: {offset}s"
        assert timing["speech_duration"] <= duration, "Speech would extend beyond its scene"
        boundaries.append({"scene": scene["id"], "video_start": start, "audio_start": timing["start"],
                           "offset_seconds": offset, "video_duration": duration,
                           "speech_duration": timing["speech_duration"]})
        start += duration
    assert index == len(clips), "Unexpected template animation count"
    result = {"video": str(video), "decode": "passed", "peak_db": peak,
              "stream_duration_delta": delta, "duration": media["format"]["duration"],
              "streams": [{k: s[k] for k in ("codec_type", "codec_name", "width", "height", "duration", "start_time") if k in s} for s in media["streams"]],
              "scene_boundaries": boundaries}
    (job_dir / "media-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1]), indent=2))
