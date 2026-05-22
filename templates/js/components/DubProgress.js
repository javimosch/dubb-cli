function DubProgress({ job, onDownload, onDub }) {
  if (!job) return null;

  const pct = job.total > 0 ? Math.round((job.step / job.total) * 100) : 0;

  const states = [
    "Extracting audio", "Transcribing", "Translating",
    "Generating speech", "Processing video", "Concatenating", "Done"
  ];

  return React.createElement("div", { className: "fade-in space-y-4 mt-6" },

    React.createElement("div", { className: "flex items-center justify-between text-sm" },
      React.createElement("span", { className: "font-medium text-stone-700" },
        job.status === "done" ? "Complete" :
        job.status === "error" ? "Failed" :
        `${job.label || "Processing..."}`
      ),
      React.createElement("span", { className: "text-stone-400" },
        job.status === "done" ? `${job.duration_s}s` :
        job.status === "error" ? "" :
        `${job.step}/${job.total}`
      )
    ),

    job.status === "error"
      ? React.createElement("div", { className: "alert alert-error text-sm" },
          React.createElement("i", { "data-lucide": "alert-triangle", className: "w-4 h-4" }),
          React.createElement("span", null, job.error || "An error occurred")
        )
      : React.createElement("div", { className: "w-full bg-stone-100 rounded-full h-2 overflow-hidden" },
          React.createElement("div", {
            className: `h-full rounded-full transition-all duration-500 ease-out ${
              job.status === "done" ? "bg-green-500" : "bg-stone-700"
            }`,
            style: { width: `${pct}%` }
          })
        ),

    job.status !== "done" && job.status !== "error" &&
      React.createElement("div", { className: "flex gap-1.5" },
        states.slice(0, job.step + 1).map((s, i) =>
          React.createElement("div", {
            key: i,
            className: `h-1.5 flex-1 rounded-full transition-all ${
              i < job.step ? "bg-stone-700" :
              i === job.step ? "bg-stone-400 animate-pulse" :
              "bg-stone-200"
            }`
          })
        )
      ),

    job.status === "done" &&
      React.createElement("button", {
        onClick: onDownload,
        className: "btn btn-neutral w-full gap-2"
      },
        React.createElement("i", { "data-lucide": "download", className: "w-4 h-4" }),
        "Download Dubbed Video"
      )
  );
}
