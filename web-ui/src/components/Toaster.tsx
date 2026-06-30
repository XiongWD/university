import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import { useVolunteerStore } from "../store/volunteerStore";

/**
 * 极简 Toast 通知（自建，零额外依赖）。
 * 读取 volunteerStore.toasts，固定定位 top-20 right-4，3秒自动消失。
 */
export default function Toaster() {
  const toasts = useVolunteerStore((s) => s.toasts);
  const dismiss = useVolunteerStore((s) => s.dismissToast);
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 w-72 max-w-[calc(100vw-2rem)]">
      {toasts.map((t) => {
        const Icon = t.type === "success" ? CheckCircle2 : t.type === "error" ? XCircle : Info;
        const color =
          t.type === "success" ? "text-emerald-300 border-emerald-400/30"
          : t.type === "error" ? "text-red-300 border-red-400/30"
          : "text-sky-300 border-sky-400/30";
        return (
          <div
            key={t.id}
            role="status"
            data-testid={`toast-${t.type}`}
            className={`glass rounded-xl px-3 py-2.5 text-sm flex items-start gap-2 shadow-xl animate-fade-in ${color}`}
          >
            <Icon className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="flex-1 leading-snug text-white/85">{t.message}</span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="text-white/40 hover:text-white/70 shrink-0"
              aria-label="关闭"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
