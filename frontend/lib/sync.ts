"use client";
/**
 * lib/sync.ts — outbox replay. Called on 'online' + app boot.
 * Replays queued SOS reports (idempotent via client_report_id) and queued
 * volunteer task actions. Works for both demo and REST api clients.
 */
import type { SahaytaApi } from "./api";
import { outboxList, outboxRemove, type OutboxEntry } from "./outbox";
import type { SOSCreateInput } from "./types";

export async function syncOutbox(api: SahaytaApi, onSynced?: (n: number) => void): Promise<number> {
  if (typeof navigator !== "undefined" && !navigator.onLine) return 0;
  const entries = await outboxList().catch(() => [] as OutboxEntry[]);
  let done = 0;
  for (const e of entries) {
    try {
      if (e.kind === "sos") {
        await api.createSOS(e.payload as SOSCreateInput);
      } else {
        const p = e.payload as { action: string; url: string; body: Record<string, unknown> };
        const m = p.url.match(/\/api\/tasks\/([^/]+)\/(accept|decline|enroute|complete|cancel)/);
        if (m) await api.taskAction(m[1], m[2] as "accept" | "decline" | "enroute" | "complete" | "cancel", p.body);
        else continue;
      }
      await outboxRemove(e.client_report_id);
      done++;
    } catch {
      // Leave it queued; next sync retries. Idempotency key prevents dupes.
    }
  }
  if (done > 0) onSynced?.(done);
  return done;
}
