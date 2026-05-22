function Toast({ toasts, onDismiss }) {
  return React.createElement("div", {
    className: "fixed top-4 right-4 z-50 flex flex-col gap-2",
    style: { minWidth: "320px" }
  },
    Object.entries(toasts).map(([id, t]) =>
      React.createElement("div", {
        key: id,
        className: `toast-enter flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border ${
          t.type === "error" ? "bg-red-50 border-red-200 text-red-800" :
          t.type === "success" ? "bg-green-50 border-green-200 text-green-800" :
          t.type === "loading" ? "bg-white border-stone-200 text-stone-800" :
          "bg-white border-stone-200 text-stone-800"
        }`
      },
        t.type === "loading" && React.createElement("span", { className: "loading loading-spinner loading-sm" }),
        t.type === "success" && React.createElement("i", { "data-lucide": "check-circle", className: "w-4 h-4 text-green-600" }),
        t.type === "error" && React.createElement("i", { "data-lucide": "alert-circle", className: "w-4 h-4 text-red-600" }),
        React.createElement("span", { className: "text-sm flex-1" }, t.message),
        React.createElement("button", {
          onClick: () => onDismiss(id),
          className: "text-stone-400 hover:text-stone-600"
        }, React.createElement("i", { "data-lucide": "x", className: "w-4 h-4" }))
      )
    )
  );
}

function useToast() {
  const [toasts, setToasts] = React.useState({});

  const add = React.useCallback((message, type = "info", duration = 4000) => {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
    setToasts(prev => ({ ...prev, [id]: { message, type } }));
    if (type !== "loading") {
      setTimeout(() => setToasts(prev => { const n = { ...prev }; delete n[id]; return n; }), duration);
    }
    return id;
  }, []);

  const dismiss = React.useCallback((id) => {
    setToasts(prev => { const n = { ...prev }; delete n[id]; return n; });
  }, []);

  const removeLoading = React.useCallback((id, message, type = "success") => {
    setToasts(prev => {
      if (!prev[id]) return prev;
      return { ...prev, [id]: { message, type } };
    });
    if (type !== "loading") {
      setTimeout(() => setToasts(p => { const n = { ...p }; delete n[id]; return n; }), 4000);
    }
  }, []);

  return { toasts, add, dismiss, removeLoading };
}
