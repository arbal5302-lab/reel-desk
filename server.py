"""
======================================================================
 EXPLAINER VIDEO FACTORY -- Web App Backend
======================================================================
FastAPI server jo team ke liye web page serve karta hai.
Keyword submit karo -> background mein poori pipeline chalti hai
(script -> voiceover -> stock footage -> final video) -> jab ready ho,
webpage pe preview + download link mil jata hai.

RUN LOCALLY:
    pip install -r requirements.txt
    export PEXELS_API_KEY="your_key"
    export ANTHROPIC_API_KEY="your_key"
    uvicorn server:app --host 0.0.0.0 --port 8000

Phir browser mein: http://localhost:8000

DEPLOY (taake team kahin se bhi use kar sake):
    README.md mein Railway/Render deploy steps hain.
======================================================================
"""

import os
import re
import json
import uuid
import asyncio
import subprocess
import threading
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ======================================================================
# CONFIG
# ======================================================================

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VOICE = "en-US-ChristopherNeural"
NUM_CLIPS = 5

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)

# In-memory job tracking (fine for a small team; swap for Redis/DB if you scale up)
JOBS: dict[str, dict] = {}

app = FastAPI(title="Explainer Video Factory")


# ======================================================================
# PIPELINE STEPS (same logic as the standalone script, wrapped for jobs)
# ======================================================================

def log(job_id: str, message: str):
    JOBS[job_id]["log"].append(message)
    print(f"[{job_id}] {message}")


def generate_script(job_id: str, topic: str, manual_script: str | None) -> str:
    if manual_script:
        log(job_id, "Using your provided script")
        return manual_script.strip()

    log(job_id, "Writing script...")
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Write a punchy, fact-dense short-form explainer video script about: {topic}

Rules:
- 60-90 seconds when read aloud (roughly 150-220 words)
- Start with a strong hook (a surprising fact or bold claim)
- Short, punchy sentences. No filler.
- Written to be read aloud by a narrator (documentary style)
- No headers, no stage directions, no emojis -- just the spoken narration text
- End with a strong closing line
"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    script = message.content[0].text.strip()
    log(job_id, "Script ready")
    return script


def generate_voiceover(job_id: str, script: str, out_dir: Path):
    log(job_id, "Generating voiceover...")
    import edge_tts

    audio_path = out_dir / "voiceover.mp3"
    srt_path = out_dir / "captions.srt"

    async def _run():
        communicate = edge_tts.Communicate(text=script, voice=VOICE, rate="+0%", pitch="+0Hz")
        submaker = edge_tts.SubMaker()
        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(submaker.get_srt())

    asyncio.run(_run())

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise RuntimeError(
            "Voiceover file came back empty. This usually means the server's "
            "network couldn't reach Microsoft's TTS service (Edge TTS can be "
            "blocked on some cloud hosts). Try again, or switch to a paid TTS "
            "API (e.g. ElevenLabs) if this keeps happening."
        )

    log(job_id, f"Voiceover ready ({audio_path.stat().st_size} bytes)")
    return audio_path, srt_path


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrapper=1:nokey=1", str(audio_path)],
        capture_output=True, text=True,
    )
    output = result.stdout.strip()
    if not output:
        raise RuntimeError(
            f"ffprobe couldn't read the audio duration. "
            f"stderr: {result.stderr.strip()[:300]}"
        )
    return float(output)


def fetch_stock_clips(job_id: str, topic: str, out_dir: Path, count: int = 5):
    log(job_id, "Sourcing stock footage...")
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(topic)}&orientation=portrait&per_page={count}"
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_API_KEY})

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())

    clip_paths = []
    for i, video in enumerate(data.get("videos", [])[:count]):
        files = sorted(video["video_files"], key=lambda f: f.get("width", 0), reverse=True)
        best = next((f for f in files if f.get("width", 0) <= 1080), files[0])
        clip_path = clips_dir / f"clip_{i}.mp4"
        urllib.request.urlretrieve(best["link"], clip_path)
        clip_paths.append(clip_path)

    log(job_id, f"{len(clip_paths)} clips downloaded")
    return clip_paths


def assemble_video(job_id: str, clip_paths, audio_path: Path, srt_path: Path, out_dir: Path, target_duration: float):
    log(job_id, "Assembling final video...")

    if not clip_paths:
        raise RuntimeError("No stock clips found -- check your Pexels API key or try a more visual topic.")

    per_clip_duration = target_duration / len(clip_paths)
    trimmed_dir = out_dir / "trimmed"
    trimmed_dir.mkdir(exist_ok=True)
    trimmed_paths = []

    for i, clip in enumerate(clip_paths):
        trimmed = trimmed_dir / f"trimmed_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(clip), "-t", str(per_clip_duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            str(trimmed),
        ], check=True, capture_output=True)
        trimmed_paths.append(trimmed)

    concat_list = out_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in trimmed_paths:
            f.write(f"file '{p.resolve()}'\n")

    concatenated = out_dir / "concatenated.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(concatenated),
    ], check=True, capture_output=True)

    final_output = out_dir / "final_video.mp4"
    style = (
        "FontName=Arial Black,FontSize=16,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=180"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(concatenated), "-i", str(audio_path),
        "-vf", f"subtitles={srt_path}:force_style='{style}'",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-shortest",
        str(final_output),
    ], check=True, capture_output=True)

    log(job_id, "Video ready")
    return final_output


def run_pipeline(job_id: str, topic: str, manual_script: str | None):
    out_dir = JOBS_DIR / job_id
    out_dir.mkdir(exist_ok=True)
    try:
        JOBS[job_id]["status"] = "running"
        script = generate_script(job_id, topic, manual_script)
        JOBS[job_id]["script"] = script

        audio_path, srt_path = generate_voiceover(job_id, script, out_dir)
        duration = get_audio_duration(audio_path)

        clip_paths = fetch_stock_clips(job_id, topic, out_dir, NUM_CLIPS)
        final_video = assemble_video(job_id, clip_paths, audio_path, srt_path, out_dir, duration)

        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["video_path"] = str(final_video)
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)
        log(job_id, f"Error: {e}")


# ======================================================================
# API
# ======================================================================

class GenerateRequest(BaseModel):
    topic: str
    manual_script: str | None = None


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required")
    if not PEXELS_API_KEY:
        raise HTTPException(500, "Server is missing PEXELS_API_KEY")
    if not req.manual_script and not ANTHROPIC_API_KEY:
        raise HTTPException(500, "Server is missing ANTHROPIC_API_KEY (or provide manual_script)")

    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "status": "queued",
        "topic": req.topic,
        "log": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    thread = threading.Thread(target=run_pipeline, args=(job_id, req.topic, req.manual_script), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")
    job = JOBS[job_id]
    return {
        "status": job["status"],
        "log": job["log"],
        "error": job.get("error"),
    }


@app.get("/api/video/{job_id}")
def video(job_id: str):
    if job_id not in JOBS or JOBS[job_id]["status"] != "done":
        raise HTTPException(404, "Video not ready")
    return FileResponse(JOBS[job_id]["video_path"], media_type="video/mp4", filename=f"{job_id}.mp4")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
