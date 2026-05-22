import json
import logging
import mimetypes
import os
import shutil
import sys
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from .dubb import run_pipeline

UPLOAD_DIR = "/tmp/dubb_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

JOBS = {}
LOCK = threading.Lock()


def parse_multipart(body, boundary):
    parts = {}
    boundary = boundary.strip().encode()
    for chunk in body.split(b"--" + boundary):
        if not chunk or chunk in (b"--\r\n", b"--\r\n", b"--\n", b"--"):
            continue
        hdr_end = chunk.find(b"\r\n\r\n")
        if hdr_end == -1:
            continue
        raw_headers = chunk[:hdr_end].decode("utf-8", errors="replace")
        data = chunk[hdr_end + 4:]
        if data.endswith(b"\r\n"):
            data = data[:-2]
        filename = None
        for line in raw_headers.split("\r\n"):
            if "filename=" in line:
                filename = line.split("filename=")[1].strip('"')
        if filename:
            parts["filename"] = sanitize_filename(filename)
            parts["body"] = data
    return parts


def sanitize_filename(name):
    name = name.replace("\\", "/").split("/")[-1]
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip() or "upload"


class JobRunner(threading.Thread):
    def __init__(self, job_id, video_path, target_lang, source_lang, voice, model):
        super().__init__(daemon=True)
        self.job_id = job_id
        self.video_path = video_path
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.voice = voice
        self.model = model

    def run(self):
        try:
            def progress(step, total, label=""):
                with LOCK:
                    if self.job_id in JOBS:
                        JOBS[self.job_id]["step"] = step
                        JOBS[self.job_id]["total"] = total
                        JOBS[self.job_id]["label"] = label

            out_dir = os.path.join(UPLOAD_DIR, f"{self.job_id}_out")
            os.makedirs(out_dir, exist_ok=True)
            output_path = os.path.join(out_dir, "dubbed.mp4")

            with LOCK:
                if self.job_id in JOBS:
                    JOBS[self.job_id]["status"] = "processing"

            progress(0, 6, "Starting")
            actual_out = run_pipeline(
                self.video_path, self.target_lang,
                source_lang=self.source_lang, voice=self.voice,
                model_size=self.model, output_path=output_path,
                on_progress=progress
            )

            with LOCK:
                if self.job_id in JOBS:
                    JOBS[self.job_id].update({
                        "status": "done",
                        "output": actual_out,
                        "step": 6,
                        "total": 6,
                        "label": "Done",
                        "duration_s": time.time() - JOBS[self.job_id]["started_at"]
                    })
        except Exception as e:
            with LOCK:
                if self.job_id in JOBS:
                    JOBS[self.job_id].update({
                        "status": "error",
                        "error": str(e)
                    })


class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logging.info(f"{self.client_address[0]} - {fmt % args}")

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self, content, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _js(self, content, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _file_response(self, path, content_type=None):
        if not os.path.exists(path):
            self._json({"error": "File not found"}, 404)
            return
        if not content_type:
            content_type, _ = mimetypes.guess_type(path)
        content_type = content_type or "application/octet-stream"
        sz = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(sz))
        self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/ui":
            self._html(SERVE_HTML)
        elif self.path.startswith("/ui/js/"):
            rel = self.path[4:]
            project = Path(__file__).parent.parent
            fp = project / "templates" / rel.lstrip("/")
            if fp.exists():
                self._js(fp.read_text())
            else:
                self._json({"error": "Not found"}, 404)
        elif self.path == "/api/health":
            self._json({"status": "healthy"})
        elif self.path.startswith("/api/jobs"):
            self._handle_get_jobs()
        elif self.path.startswith("/api/download/"):
            job_id = self.path.split("/")[-1]
            self._handle_download(job_id)
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/upload":
            self._handle_upload()
        elif self.path == "/api/dub":
            self._handle_dub()
        else:
            self._json({"error": "Not found"}, 404)

    def _handle_upload(self):
        ct = self.headers.get("Content-Type", "")
        if "multipart/form-data" in ct:
            boundary = ct.split("boundary=")[-1]
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            parts = parse_multipart(body, boundary)
            filename = parts.get("filename", "upload")
            data = parts.get("body")
            if not data:
                self._json({"error": "No file data"}, 400)
                return
            file_id = str(uuid.uuid4())[:8]
            ext = os.path.splitext(filename)[1] or ".mp4"
            dest = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
            with open(dest, "wb") as f:
                f.write(data)
            self._json({"ok": True, "file_id": file_id, "filename": filename, "path": dest})
        else:
            self._json({"error": "Expected multipart/form-data"}, 400)

    def _handle_dub(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        file_path = body.get("file_path")
        target_lang = body.get("target_lang", "es")
        source_lang = body.get("source_lang")
        voice = body.get("voice")
        model = body.get("model", "base")

        if not file_path or not os.path.exists(file_path):
            self._json({"error": "Invalid file_path"}, 400)
            return

        job_id = str(uuid.uuid4())[:8]
        with LOCK:
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "file_path": file_path,
                "target_lang": target_lang,
                "source_lang": source_lang,
                "voice": voice,
                "step": 0,
                "total": 6,
                "label": "Queued",
                "started_at": time.time(),
                "duration_s": 0,
            }

        runner = JobRunner(job_id, file_path, target_lang, source_lang, voice, model)
        runner.start()
        self._json({"ok": True, "job_id": job_id})

    def _handle_get_jobs(self):
        with LOCK:
            jobs = dict(JOBS)
        out = {}
        for jid, j in jobs.items():
            out[jid] = {
                "id": j["id"],
                "status": j["status"],
                "step": j["step"],
                "total": j["total"],
                "label": j["label"],
                "duration_s": round(j.get("duration_s", 0), 1),
                "target_lang": j["target_lang"],
                "error": j.get("error"),
            }
        self._json({"ok": True, "jobs": out})

    def _handle_download(self, job_id):
        with LOCK:
            job = JOBS.get(job_id)
        if not job:
            self._json({"error": "Job not found"}, 404)
            return
        if job["status"] != "done":
            self._json({"error": "Job not ready", "status": job["status"]}, 400)
            return
        out_path = job.get("output")
        if not out_path or not os.path.exists(out_path):
            self._json({"error": "Output not found"}, 404)
            return
        self._file_response(out_path, "video/mp4")


def start_server(port=8080):
    global SERVE_HTML
    project = Path(__file__).parent.parent
    html_path = project / "templates" / "index.html"
    if html_path.exists():
        SERVE_HTML = html_path.read_text()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    logging.info(f"Dubb server on http://0.0.0.0:{port}")
    logging.info(f"UI at http://localhost:{port}/ui")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


SERVE_HTML = ""
