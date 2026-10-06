"use client";
/** TaskCard — volunteer task lifecycle (design-system §5.15, wireframe volunteer-tasks).
 *  Wave 3 (Agent 8): complete flow gains an optional note + photo proof
 *  (POST /api/media → proof_photo_id), per the wireframe's "(+photo opt)". */
import { Camera, Check, Compass, MapPin, Star, X } from "lucide-react";
import { useRef, useState } from "react";
import { useI18n } from "../lib/i18n";
import { timeAgo } from "../lib/format";
import type { Task } from "../lib/types";
import SeverityBadge from "./SeverityBadge";
import { TaskStatusPill } from "./StatusPill";

export type TaskActionBody = { note?: string; proofFile?: File | null; reason?: string };

export default function TaskCard({ task, onAction, busy }: {
  task: Task;
  onAction: (action: "accept" | "decline" | "enroute" | "complete", body?: TaskActionBody) => void;
  busy?: boolean;
}) {
  const { t } = useI18n();
  const [completing, setCompleting] = useState(false);
  const [note, setNote] = useState("");
  const [proofFile, setProofFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const sos = task.sos;
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        {sos?.severity != null ? <SeverityBadge severity={sos.severity} size="sm" /> : <span />}
        <TaskStatusPill status={task.status} />
      </div>
      {sos && (
        <>
          <p className="mb-1 line-clamp-2 text-[15px] font-medium text-ink">{sos.description}</p>
          <p className="mb-3 flex items-center gap-1 text-[13px] text-muted">
            <MapPin size={13} aria-hidden />
            <span className="num-ltr">{t("volunteer.assigned_ago", { t: timeAgo(task.assigned_at) })}</span>
          </p>
        </>
      )}
      {task.note?.startsWith("Re-offered") && (
        <p className="mb-3 rounded-card bg-amber-50 px-2.5 py-1.5 text-[13px] text-amber-800">🔁 {task.note}</p>
      )}
      {task.proof_photo_url && (
        <img src={task.proof_photo_url} alt="" className="mb-3 max-h-40 w-full rounded-card object-cover" />
      )}
      <div className="flex gap-2">
        {task.status === "assigned" && (
          <>
            <button onClick={() => onAction("accept")} disabled={busy} className="btn-primary flex-1">
              ✓ {t("volunteer.accept")}
            </button>
            <button onClick={() => onAction("decline")} disabled={busy} className="btn-danger-ghost" aria-label={t("volunteer.decline")}>
              <X size={20} aria-hidden /> {t("volunteer.decline")}
            </button>
          </>
        )}
        {task.status === "accepted" && (
          <button onClick={() => onAction("enroute")} disabled={busy} className="btn-primary flex-1">
            <Compass size={18} aria-hidden /> {t("volunteer.enroute")}
          </button>
        )}
        {task.status === "en_route" && !completing && (
          <button onClick={() => setCompleting(true)} disabled={busy} className="btn-primary flex-1">
            <Camera size={18} aria-hidden /> {t("volunteer.complete")}
          </button>
        )}
        {task.status === "en_route" && completing && (
          <div className="w-full space-y-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("volunteer.complete_note_ph")}
              maxLength={500}
              className="input"
            />
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => setProofFile(e.target.files?.[0] ?? null)}
            />
            <button onClick={() => fileRef.current?.click()} className="btn-secondary flex w-full items-center justify-center gap-2">
              <Camera size={16} aria-hidden />
              {proofFile ? proofFile.name.slice(0, 28) : t("volunteer.photo_proof")}
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => { onAction("complete", { note: note.trim() || undefined, proofFile }); setCompleting(false); }}
                disabled={busy}
                className="btn-primary flex-1"
              >
                <Check size={18} aria-hidden /> {t("volunteer.complete")}
              </button>
              <button onClick={() => { setCompleting(false); setNote(""); setProofFile(null); }} disabled={busy} className="btn-secondary">
                {t("common.cancel")}
              </button>
            </div>
          </div>
        )}
        {(task.status === "completed" || task.status === "declined" || task.status === "cancelled") && (
          <span className="inline-flex items-center gap-1 text-[14px] font-semibold text-muted">
            {task.status === "completed" && <><Star size={15} className="text-amber-500" aria-hidden /> +2 ★</>}
          </span>
        )}
      </div>
    </div>
  );
}
