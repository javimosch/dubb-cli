const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "it", name: "Italian" },
  { code: "pt", name: "Portuguese" },
  { code: "ru", name: "Russian" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "zh", name: "Chinese" },
  { code: "ar", name: "Arabic" },
  { code: "hi", name: "Hindi" },
  { code: "nl", name: "Dutch" },
  { code: "pl", name: "Polish" },
  { code: "tr", name: "Turkish" },
  { code: "vi", name: "Vietnamese" },
  { code: "th", name: "Thai" },
  { code: "uk", name: "Ukrainian" },
];

const VOICES = [
  { id: "M1", label: "Male 1" },
  { id: "M2", label: "Male 2" },
  { id: "M3", label: "Male 3" },
  { id: "M4", label: "Male 4" },
  { id: "M5", label: "Male 5" },
  { id: "F1", label: "Female 1" },
  { id: "F2", label: "Female 2" },
  { id: "F3", label: "Female 3" },
  { id: "F4", label: "Female 4" },
  { id: "F5", label: "Female 5" },
];

function DubView({ addToast }) {
  const [file, setFile] = React.useState(null);
  const [filePath, setFilePath] = React.useState(null);
  const [uploading, setUploading] = React.useState(false);
  const [targetLang, setTargetLang] = React.useState("es");
  const [voice, setVoice] = React.useState("");
  const [jobs, setJobs] = React.useState({});
  const [activeJobId, setActiveJobId] = React.useState(null);
  const [sample, setSample] = React.useState(null);

  React.useEffect(() => {
    if (typeof lucide !== "undefined") lucide.createIcons();
  }, [file, uploading, jobs, activeJobId, sample]);

  React.useEffect(() => {
    fetch("/api/sample").then(r => r.json()).then(setSample).catch(() => {});
  }, []);

  React.useEffect(() => {
    const stop = API.pollJobs((all) => {
      setJobs(all);
      const active = Object.values(all).find(j => j.status === "queued" || j.status === "processing");
      if (active) {
        setActiveJobId(active.id);
      } else {
        const prev = activeJobId;
        if (prev && all[prev]?.status === "done") {
          addToast("Dubbing complete!", "success");
        } else if (prev && all[prev]?.status === "error") {
          addToast("Dubbing failed", "error");
        }
      }
    });
    return stop;
  }, []);

  const handleFile = async (f) => {
    setFile(f);
    if (!f) { setFilePath(null); return; }
    setUploading(true);
    try {
      const r = await API.upload(f);
      if (r.ok) {
        setFilePath(r.path);
        addToast("File uploaded", "success");
      } else {
        addToast(r.error || "Upload failed", "error");
      }
    } catch (e) {
      addToast("Upload error: " + e.message, "error");
    } finally {
      setUploading(false);
    }
  };

  const handleSample = () => {
    setFilePath("/root/projects/dubb-cli/sample/cat-driving.mp4");
    setFile({ name: "cat-driving.mp4" });
    addToast("Sample loaded", "success");
  };

  const handleDub = async () => {
    if (!filePath) return;
    try {
      const r = await API.dub({
        file_path: filePath,
        target_lang: targetLang,
        voice: voice || null,
      });
      if (r.ok) {
        setActiveJobId(r.job_id);
        addToast("Job queued", "success");
      } else {
        addToast(r.error || "Failed to start", "error");
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  const active = activeJobId ? jobs[activeJobId] : null;
  const hasActive = Object.values(jobs).some(j => j.status === "queued" || j.status === "processing");

  return React.createElement("div", { className: "max-w-xl mx-auto px-4 py-10 space-y-6" },

    React.createElement("div", { className: "text-center" },
      React.createElement("h1", { className: "text-2xl font-semibold text-stone-800" }, "Dubb CLI"),
      React.createElement("p", { className: "text-sm text-stone-400 mt-1" },
        "Upload a video or try the demo"
      )
    ),

    React.createElement(UploadZone, { onFile: handleFile, disabled: uploading || hasActive }),

    sample && sample.available && !file && !hasActive &&
      React.createElement("div", { className: "text-center" },
        React.createElement("div", { className: "divider text-xs text-stone-300" }, "OR"),
        React.createElement("button", {
          onClick: handleSample,
          className: "btn btn-ghost btn-sm gap-2 border border-stone-200"
        },
          React.createElement("i", { "data-lucide": "play", className: "w-4 h-4" }),
          `Try sample (${sample.size_mb} MB)`
        )
      ),

    filePath && !hasActive && React.createElement("div", { className: "fade-in space-y-4" },

      React.createElement("div", { className: "flex flex-col gap-1.5" },
        React.createElement("label", { className: "text-xs font-medium text-stone-500 uppercase tracking-wider" }, "Dub to"),
        React.createElement("select", {
          value: targetLang,
          onChange: (e) => setTargetLang(e.target.value),
          className: "select select-bordered w-full bg-white",
        },
          LANGUAGES.map(l =>
            React.createElement("option", { key: l.code, value: l.code }, l.name)
          )
        )
      ),

      React.createElement("div", { className: "flex flex-col gap-1.5" },
        React.createElement("label", { className: "text-xs font-medium text-stone-500 uppercase tracking-wider" }, "Voice"),
        React.createElement("select", {
          value: voice,
          onChange: (e) => setVoice(e.target.value),
          className: "select select-bordered w-full bg-white",
        },
          React.createElement("option", { value: "" }, "Auto"),
          VOICES.map(v =>
            React.createElement("option", { key: v.id, value: v.id }, v.label)
          )
        )
      ),

      React.createElement("button", {
        onClick: handleDub,
        className: "btn btn-neutral w-full gap-2"
      },
        React.createElement("i", { "data-lucide": "wand-2", className: "w-4 h-4" }),
        "Dub Video"
      )
    ),

    React.createElement(DubProgress, {
      job: active,
      onDownload: () => { window.open(API.downloadUrl(activeJobId), "_blank"); },
    })

  );
}
