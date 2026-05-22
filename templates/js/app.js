const { useState, useEffect, useCallback, createElement: h } = React;

function App() {
  const { toasts, add, dismiss } = useToast();

  useEffect(() => {
    if (typeof lucide !== "undefined") lucide.createIcons();
  }, [toasts]);

  return h("div", { className: "min-h-screen flex flex-col" },
    h(Toast, { toasts, onDismiss: dismiss }),
    h(DubView, { addToast: add }),
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(h(App));
