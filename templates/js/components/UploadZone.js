function UploadZone({ onFile, disabled }) {
  const [drag, setDrag] = React.useState(false);
  const [file, setFile] = React.useState(null);
  const inputRef = React.useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) { setFile(f); onFile(f); }
  };

  const handleChange = (e) => {
    const f = e.target.files[0];
    if (f) { setFile(f); onFile(f); }
  };

  const fmt = (n) => {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  };

  const icon = file
    ? React.createElement("i", { "data-lucide": "file-video", className: "w-8 h-8 text-stone-500" })
    : React.createElement("i", { "data-lucide": "upload", className: "w-8 h-8 text-stone-400" });

  return React.createElement("div", { className: "fade-in" },
    React.createElement("div", {
      className: `upload-zone rounded-2xl p-8 text-center cursor-pointer transition-all ${
        disabled ? "opacity-50 pointer-events-none" :
        drag ? "drag-over scale-[1.01]" : "hover:border-stone-400"
      }`,
      onDragOver: (e) => { e.preventDefault(); setDrag(true); },
      onDragLeave: () => setDrag(false),
      onDrop: handleDrop,
      onClick: () => inputRef.current?.click(),
    },
      React.createElement("input", {
        ref: inputRef, type: "file", accept: ".mp4,.mp3,.wav,.mov,.webm,.avi",
        onChange: handleChange, className: "hidden"
      }),

      file
        ? React.createElement("div", { className: "flex flex-col items-center gap-2" },
            icon,
            React.createElement("p", { className: "font-medium text-stone-700" }, file.name),
            React.createElement("p", { className: "text-sm text-stone-400" }, fmt(file.size)),
            React.createElement("button", {
              onClick: (e) => { e.stopPropagation(); setFile(null); onFile(null); },
              className: "text-xs text-red-500 hover:text-red-600 mt-1"
            }, "Remove")
          )
        : React.createElement("div", { className: "flex flex-col items-center gap-2" },
            icon,
            React.createElement("p", { className: "font-medium text-stone-600" },
              "Drop a video or audio file here"
            ),
            React.createElement("p", { className: "text-xs text-stone-400" },
              "MP4, MOV, WebM, MP3, WAV"
            )
          )
    )
  );
}
