import sys

from .errors import DubbError, InvalidArgument
from .dubb import run_pipeline


def cmd_dub(args):
    if not args.video:
        raise InvalidArgument("Video path required")
    import os
    if not os.path.exists(args.video):
        raise InvalidArgument(f"Video not found: {args.video}")
    import tempfile
    out = args.output or os.path.join(tempfile.gettempdir(), "dubbed_output.mp4")

    def progress(step, total, label=""):
        print(f"[{step}/{total}] {label}", file=sys.stderr)

    result = run_pipeline(
        args.video, args.to, source_lang=args.src,
        voice=args.voice, model_size=args.model or "base",
        output_path=out, on_progress=progress
    )
    return {"ok": True, "output": result, "duration_s": 0}


def cmd_serve(args):
    from .server import start_server
    port = args.port or 8080
    print(f"Starting server on port {port}...", file=sys.stderr)
    start_server(port)


def cmd_version(args):
    return {"name": "dubb-cli-v2", "version": "0.1.0"}
