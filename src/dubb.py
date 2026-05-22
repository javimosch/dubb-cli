import os
import shutil
import subprocess
import tempfile
import time

from .errors import DubbError


def get_audio_duration(file_path):
    r = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except (ValueError, TypeError):
        return 0


def transcribe(audio_path, source_lang, model_size="base"):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    kw = dict(beam_size=3)
    if source_lang:
        kw["language"] = source_lang
    segments, info = model.transcribe(audio_path, **kw)
    result = []
    for seg in segments:
        result.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })
    return result, info.language


def translate(segments, target_lang, source_lang=None):
    if source_lang and source_lang == target_lang:
        for seg in segments:
            seg["translated"] = seg["text"]
        return segments
    from deep_translator import GoogleTranslator
    src = source_lang or "auto"
    t = GoogleTranslator(source=src, target=target_lang)
    for seg in segments:
        text = seg["text"]
        if not text:
            seg["translated"] = text
            continue
        try:
            seg["translated"] = t.translate(text)
        except Exception as e:
            seg["translated"] = text
    return segments


def synthesize(segments, voice, lang, output_dir):
    from supertonic import TTS
    tts = TTS()
    style = tts.get_voice_style(voice)
    segs_out = []
    for i, seg in enumerate(segments):
        text = seg.get("translated", seg["text"])
        if not text.strip():
            continue
        out = os.path.join(output_dir, f"raw_{i:04d}.wav")
        try:
            wav, _dur = tts.synthesize(text, style, lang=lang)
            tts.save_audio(wav, out)
            if os.path.getsize(out) > 100:
                segs_out.append({**seg, "raw_path": out})
        except Exception:
            pass
    return segs_out


def speed_video_to_tts(segs_out, video_path, workdir, max_speed=3.0, on_progress=None):
    clips = []
    total = len(segs_out)
    for i, seg in enumerate(segs_out):
        raw_path = seg["raw_path"]
        vid_dur = seg["end"] - seg["start"]
        tts_dur = get_audio_duration(raw_path)
        ratio = vid_dur / tts_dur if tts_dur > 0 else 1.0
        r = min(ratio, max_speed)
        r = max(r, 1.0)
        out = os.path.join(workdir, f"clip_{i:04d}.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{seg['start']:.3f}", "-to", f"{seg['end']:.3f}",
            "-i", video_path,
            "-i", raw_path,
            "-map", "0:v", "-map", "1:a",
            "-filter:v", f"setpts=PTS/{r:.4f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-preset", "fast", "-crf", "23",
            "-t", f"{tts_dur:.3f}",
            out
        ], check=True, capture_output=True)
        clips.append(out)
        if on_progress:
            on_progress(i + 1, total)
    return clips


def concat_clips(clip_files, output_path, workdir):
    flist = os.path.join(workdir, "clips.txt")
    with open(flist, "w") as f:
        for cf in clip_files:
            f.write(f"file '{cf}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", flist,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-preset", "fast", "-crf", "23",
        output_path
    ], check=True, capture_output=True)
    return output_path


def run_pipeline(video_path, target_lang, source_lang=None, voice=None, model_size="base",
                  output_path=None, on_progress=None):
    workdir = tempfile.mkdtemp(prefix="dubb_")
    try:
        if on_progress:
            on_progress(0, 6, "Extracting audio")
        audio_p = os.path.join(workdir, "audio.wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_p
        ], check=True, capture_output=True)

        if on_progress:
            on_progress(1, 6, "Transcribing")

        fem = {"es", "fr", "pt", "it", "ru", "pl", "uk", "ro", "bg", "el"}
        voice = voice or ("F1" if target_lang in fem else "M1")

        segs, detected_lang = transcribe(audio_p, source_lang, model_size)
        src = source_lang or detected_lang

        if on_progress:
            on_progress(2, 6, "Translating")
        segs = translate(segs, target_lang, src)

        if on_progress:
            on_progress(3, 6, "Generating speech")
        segs_out = synthesize(segs, voice, target_lang, workdir)

        if on_progress:
            on_progress(4, 6, "Processing video")
        clips = speed_video_to_tts(segs_out, video_path, workdir, on_progress=None)

        if on_progress:
            on_progress(5, 6, "Concatenating")
        out_path = output_path or os.path.join(workdir, "final.mp4")
        concat_clips(clips, out_path, workdir)

        if on_progress:
            on_progress(6, 6, "Done")
        return out_path
    except Exception as e:
        raise DubbError(str(e))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
