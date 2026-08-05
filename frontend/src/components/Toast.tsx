import { createContext, useCallback, useContext, useState, ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from "lucide-react";

type Tone = "info" | "success" | "warning" | "error";
type Toast = { id: number; tone: Tone; title: string; message?: string };
type Ctx = { push: (t: Omit<Toast, "id">) => void };

const ToastCtx = createContext<Ctx | null>(null);

let id_counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = ++id_counter;
    setToasts((prev) => [...prev, { ...t, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 4200);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((x) => x.id !== id));

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
        role="status"
        aria-live="polite"
      >
        <AnimatePresence>
          {toasts.map((t) => (
            <ToastCard key={t.id} toast={t} onClose={() => dismiss(t.id)} />
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be inside <ToastProvider>");
  return ctx.push;
}

const icons: Record<Tone, ReactNode> = {
  info: <Info className="h-5 w-5 text-accent" />,
  success: <CheckCircle2 className="h-5 w-5 text-success" />,
  warning: <AlertTriangle className="h-5 w-5 text-warning" />,
  error: <AlertCircle className="h-5 w-5 text-danger" />,
};

function ToastCard({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      layout
      initial={reduceMotion ? { opacity: 0 } : { opacity: 0, x: 40, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={reduceMotion ? { opacity: 0 } : { opacity: 0, x: 40, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 400, damping: 32 }}
      className="pointer-events-auto flex items-start gap-3 rounded-xl border border-border bg-surface p-4 shadow-soft"
    >
      {icons[toast.tone]}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-text">{toast.title}</p>
        {toast.message && <p className="mt-0.5 text-xs text-muted">{toast.message}</p>}
      </div>
      <button
        onClick={onClose}
        aria-label="Dismiss notification"
        className="rounded-md p-0.5 text-muted transition-colors hover:bg-surface-2 hover:text-text"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}
