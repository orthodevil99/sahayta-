"use client";
/** Toast system — bottom-center, auto-dismiss 4s (design-system §5.7). */
import { AlertTriangle, CheckCircle2, WifiOff } from "lucide-react";
import React, { createContext, useCallback, useContext, useState } from "react";

type ToastKind = "success" | "error" | "offline";
interface Toast { id: number; kind: ToastKind; message: string; sticky?: boolean }

const Ctx = createContext<{ toast: (kind: ToastKind, message: string, sticky?: boolean) => void; dismiss: (id: number) => void }>({
  toast: () => {}, dismiss: () => {},
});
export const useToast = () => useContext(Ctx);

let nextId = 1;
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)), []);
  const toast = useCallback((kind: ToastKind, message: string, sticky = false) => {
    const id = nextId++;
    setToasts((ts) => [...ts.slice(-2), { id, kind, message, sticky }]);
    if (!sticky && kind !== "offline") setTimeout(() => dismiss(id), 4000);
  }, [dismiss]);
  return (
    <Ctx.Provider value={{ toast, dismiss }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4" aria-live="polite">
        {toasts.map((t) => (
          <button
            key={t.id}
            onClick={() => dismiss(t.id)}
            className="pointer-events-auto flex min-h-[48px] max-w-md items-center gap-2 rounded-btn bg-[#0F172A] px-4 text-white shadow-sheet"
          >
            <span className={`h-6 w-1.5 rounded-full ${t.kind === "success" ? "bg-green-500" : t.kind === "error" ? "bg-red-500" : "bg-amber-400"}`} aria-hidden />
            {t.kind === "offline" ? <WifiOff size={18} aria-hidden /> : t.kind === "error" ? <AlertTriangle size={18} aria-hidden /> : <CheckCircle2 size={18} aria-hidden />}
            <span className="text-[15px] font-medium">{t.message}</span>
          </button>
        ))}
      </div>
    </Ctx.Provider>
  );
}
