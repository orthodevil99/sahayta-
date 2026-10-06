/**
 * IndexedDB outbox — the offline queue. SOS drafts (and queued volunteer
 * actions) persist here; the service worker + `syncOutbox()` replay them with
 * the original `client_report_id`, so replays are idempotent (contracts §0.5:
 * duplicate replay → 200 with the existing resource, never a duplicate row).
 */
import type { SOSCreateInput } from "./types";

export interface OutboxEntry {
  client_report_id: string;
  kind: "sos" | "volunteer_action";
  payload: SOSCreateInput | { action: string; url: string; body: unknown };
  created_at: string;
  attempts: number;
}

const DB = "sahayta-outbox";
const STORE = "entries";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "client_report_id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function outboxAdd(entry: OutboxEntry): Promise<void> {
  await tx("readwrite", (s) => s.put(entry));
}

export async function outboxList(): Promise<OutboxEntry[]> {
  return tx("readonly", (s) => s.getAll());
}

export async function outboxRemove(client_report_id: string): Promise<void> {
  await tx("readwrite", (s) => s.delete(client_report_id));
}

export async function outboxCount(): Promise<number> {
  const all = await outboxList();
  return all.length;
}

/** Client-generated device id — the guest auth identity (contracts §0.2). */
export function getDeviceId(): string {
  const KEY = "sahayta.device_id";
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}

export function newClientReportId(): string {
  return crypto.randomUUID();
}
