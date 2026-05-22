import argparse
import json
import sys

from .errors import DubbError, EXIT_SUCCESS
from .cli import cmd_dub, cmd_serve, cmd_version


def main():
    ap = argparse.ArgumentParser(description="dubb-cli-v2 — Dub videos with local AI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dub", help="Dub a video")
    d.add_argument("video", nargs="?", help="Input video file")
    d.add_argument("--from", dest="src", help="Source lang (auto if omitted)")
    d.add_argument("--to", required=True, help="Target lang (ISO 639-1)")
    d.add_argument("--voice", help="TTS voice (M1-F5, F1-F5)")
    d.add_argument("--model", default="base", help="Whisper model size")
    d.add_argument("-o", "--output", help="Output video path")
    d.add_argument("--json", action="store_true", help="JSON output")

    s = sub.add_parser("serve", help="Start web UI server")
    s.add_argument("--port", "-p", type=int, default=8080, help="Port")

    v = sub.add_parser("version", help="Show version")

    args = ap.parse_args()

    try:
        if args.cmd == "dub":
            result = cmd_dub(args)
            if args.json or True:
                print(json.dumps(result, indent=2))
        elif args.cmd == "serve":
            cmd_serve(args)
        elif args.cmd == "version":
            result = cmd_version(args)
            print(json.dumps(result, indent=2))
    except DubbError as e:
        print(json.dumps({"ok": False, "error": e.message}), file=sys.stderr)
        sys.exit(e.code)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
