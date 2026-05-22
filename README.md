# dubb-cli

Local video dubbing with a web UI. Uses faster-whisper (CTranslate2) for transcription and supertonic for TTS — all on-device, no cloud.

## CLI

```bash
dubb-cli dub <video> --to <lang> -o output.mp4
dubb-cli serve --port 8080
dubb-cli version
```

## Web UI

```bash
dubb-cli serve --port 8080
# Open http://localhost:8080/ui
```

Upload a video, pick a language, download the result.

## Pipeline

1. Extract audio (ffmpeg)
2. Transcribe (faster-whisper, CPU int8 with CTranslate2)
3. Translate (Google Translate via deep-translator)
4. Generate speech (supertonic TTS — 31 languages, 10 voices)
5. Speed up video per-segment to match TTS pace
6. Concatenate clips

## Requirements

- Python 3.10+
- ffmpeg
- 8 GB+ RAM recommended
