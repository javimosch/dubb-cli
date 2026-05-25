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
BASE_DIR = Path(__file__).parent.parent
os.makedirs(UPLOAD_DIR, exist_ok=True)

JOBS = {}
QUEUE = []
PROCESSING = None
RATE_LIMIT = {}
LOCK = threading.Lock()

MAX_SIZE = 10 * 1024 * 1024
MAX_QUEUED = 5
RATE_WINDOW = 30 * 60
ARTIFACT_TTL = 2 * 3600
CLEANUP_INTERVAL = 5 * 60

SAMPLE_FILE = os.getenv("DUBB_SAMPLE_FILE", str(BASE_DIR / "sample" / "cat-driving.mp4"))
SAMPLE_DUBBED = os.getenv("DUBB_SAMPLE_DUBBED", str(BASE_DIR / "sample" / "cat-driving_dubbed.mp4"))


def rate_cleanup():
    now = time.time()
    for ip in list(RATE_LIMIT.keys()):
        if now - RATE_LIMIT[ip] > RATE_WINDOW:
            del RATE_LIMIT[ip]


def artifact_cleanup():
    now = time.time()
    with LOCK:
        for jid in list(JOBS.keys()):
            j = JOBS[jid]
            if j["status"] in ("done", "error") and jid not in QUEUE:
                started = j.get("started_at", 0)
                if started and now - started > ARTIFACT_TTL:
                    out_dir = os.path.join(UPLOAD_DIR, f"{jid}_out")
                    shutil.rmtree(out_dir, ignore_errors=True)
                    out = j.get("output", "")
                    if out and os.path.exists(out):
                        os.remove(out)
                    del JOBS[jid]
                    logging.info(f"Cleaned up artifact {jid}")


def cleanup_loop():
    while True:
        time.sleep(CLEANUP_INTERVAL)
        try:
            with LOCK:
                rate_cleanup()
            artifact_cleanup()
        except Exception:
            pass


def dispatch_next():
    global PROCESSING
    if PROCESSING is not None:
        return
    if not QUEUE:
        return
    job_id = QUEUE.pop(0)
    PROCESSING = job_id
    j = JOBS.get(job_id)
    if j:
        j["status"] = "processing"
        j["started_at"] = time.time()
        runner = JobRunner(
            job_id, j["file_path"], j["target_lang"],
            j["source_lang"], j["voice"], j.get("model", "base")
        )
        runner.start()


def on_job_done(job_id):
    global PROCESSING
    with LOCK:
        if PROCESSING == job_id:
            PROCESSING = None
        dispatch_next()


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
        finally:
            on_job_done(self.job_id)


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
        self.send_header("Content-Disposition", f'attachment; filename="dubbed_{os.path.basename(path)}"')
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
        elif self.path == "/api/sample":
            self._handle_sample()
        elif self.path == "/api/sample/download":
            self._handle_sample_download()
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
        if "multipart/form-data" not in ct:
            self._json({"error": "Expected multipart/form-data"}, 400)
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_SIZE:
            self._json({"error": f"File too large (max {MAX_SIZE // (1024*1024)} MB)"}, 413)
            return
        boundary = ct.split("boundary=")[-1]
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
        self._json({"ok": True, "file_id": file_id, "filename": filename, "path": dest, "size": length})

    def _handle_dub(self):
        client_ip = self.client_address[0]

        with LOCK:
            rate_cleanup()
            last = RATE_LIMIT.get(client_ip, 0)
            if time.time() - last < RATE_WINDOW:
                remaining = int(RATE_WINDOW - (time.time() - last))
                self._json({"error": f"Rate limited. Try again in {remaining}s"}, 429)
                return

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

        with LOCK:
            queued_count = sum(1 for j in JOBS.values() if j["status"] in ("queued", "processing"))
            if queued_count >= MAX_QUEUED:
                self._json({"error": "Queue full (max 5 queued). Try again later."}, 503)
                return

        job_id = str(uuid.uuid4())[:8]
        with LOCK:
            RATE_LIMIT[client_ip] = time.time()
            JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "file_path": file_path,
                "target_lang": target_lang,
                "source_lang": source_lang,
                "voice": voice,
                "model": model,
                "step": 0,
                "total": 6,
                "label": "Queued",
                "started_at": time.time(),
                "duration_s": 0,
            }
            QUEUE.append(job_id)
            dispatch_next()

        self._json({"ok": True, "job_id": job_id})

    def _handle_get_jobs(self):
        with LOCK:
            jobs = dict(JOBS)
            queue = list(QUEUE)
            processing = PROCESSING
        out = {}
        for jid, j in jobs.items():
            pos = queue.index(jid) + 1 if jid in queue else None
            out[jid] = {
                "id": j["id"],
                "status": j["status"],
                "step": j["step"],
                "total": j["total"],
                "label": j["label"],
                "duration_s": round(j.get("duration_s", 0), 1),
                "target_lang": j["target_lang"],
                "position": pos,
                "queued_before": pos - 1 if pos and pos > 1 else None,
                "error": j.get("error"),
            }
        self._json({"ok": True, "jobs": out, "processing": processing})

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


    def _handle_sample(self):
        available = SAMPLE_FILE and os.path.exists(SAMPLE_FILE)
        dubbed = SAMPLE_DUBBED and os.path.exists(SAMPLE_DUBBED)
        info = {"available": available, "dubbed": dubbed}
        if available:
            sz = os.path.getsize(SAMPLE_FILE)
            info["size"] = sz
            info["filename"] = os.path.basename(SAMPLE_FILE)
            info["size_mb"] = round(sz / (1024 * 1024), 1)
        self._json(info)

    def _handle_sample_download(self):
        if SAMPLE_FILE and os.path.exists(SAMPLE_FILE):
            self._file_response(SAMPLE_FILE, "video/mp4")
        else:
            self._json({"error": "Sample not found"}, 404)


def start_server(port=8080):
    global SERVE_HTML
    project = Path(__file__).parent.parent
    html_path = project / "templates" / "index.html"
    if html_path.exists():
        SERVE_HTML = html_path.read_text()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    logging.info(f"Dubb server on http://0.0.0.0:{port}")
    logging.info(f"UI at http://localhost:{port}/ui")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


SERVE_HTML = ""
