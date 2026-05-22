const API = {
  async upload(file) {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch("/api/upload", { method: "POST", body: form });
    return r.json();
  },
  async dub(params) {
    const r = await fetch("/api/dub", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    return r.json();
  },
  async getJobs() {
    const r = await fetch("/api/jobs");
    return r.json();
  },
  downloadUrl(jobId) {
    return `/api/download/${jobId}`;
  },
  pollJobs(cb, interval = 1500) {
    const poll = async () => {
      try {
        const data = await API.getJobs();
        cb(data.jobs);
      } catch {}
    };
    poll();
    const id = setInterval(poll, interval);
    return () => clearInterval(id);
  },
};
