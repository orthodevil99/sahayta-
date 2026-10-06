"use client";
import { Ban, Check, CheckCheck, ClipboardList, Compass, Flag, Inbox, Ambulance, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { SOSStatus, TaskStatus } from "../lib/types";

const SOS_STYLE: Record<SOSStatus, { bg: string; text: string; Icon: typeof Check }> = {
  reported: { bg: "#E2E8F0", text: "#334155", Icon: Inbox },
  verified: { bg: "#DBEAFE", text: "#1E40AF", Icon: Check },
  help_on_way: { bg: "#FEF3C7", text: "#92400E", Icon: Ambulance },
  resolved: { bg: "#DCFCE7", text: "#14532D", Icon: CheckCheck },
  duplicate: { bg: "#F1F5F9", text: "#64748B", Icon: Ban },
  rejected: { bg: "#F1F5F9", text: "#64748B", Icon: X },
};

const TASK_STYLE: Record<TaskStatus, { bg: string; text: string; Icon: typeof Check }> = {
  assigned: { bg: "#DBEAFE", text: "#1E40AF", Icon: ClipboardList },
  accepted: { bg: "#FEF3C7", text: "#92400E", Icon: Check },
  en_route: { bg: "#FEF3C7", text: "#92400E", Icon: Compass },
  completed: { bg: "#DCFCE7", text: "#14532D", Icon: Flag },
  declined: { bg: "#F1F5F9", text: "#64748B", Icon: X },
  cancelled: { bg: "#F1F5F9", text: "#64748B", Icon: Ban },
};

export function StatusPill({ status, pulse = false }: { status: SOSStatus; pulse?: boolean }) {
  const { t } = useI18n();
  const s = SOS_STYLE[status];
  return (
    <span className={`pill ${pulse ? "animate-pulseonce" : ""}`} style={{ backgroundColor: s.bg, color: s.text }}>
      <s.Icon size={16} aria-hidden /> {t(`status.${status}`)}
    </span>
  );
}

export function TaskStatusPill({ status }: { status: TaskStatus }) {
  const { t } = useI18n();
  const s = TASK_STYLE[status];
  return (
    <span className="pill" style={{ backgroundColor: s.bg, color: s.text }}>
      <s.Icon size={16} aria-hidden /> {t(`task_status.${status}`)}
    </span>
  );
}
