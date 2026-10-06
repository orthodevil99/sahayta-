"use client";
/** Boot hook: replay the offline outbox on load + whenever we come back online. */
import { useEffect } from "react";
import { useApi } from "../lib/api";
import { syncOutbox } from "../lib/sync";
import { useI18n } from "../lib/i18n";
import { useToast } from "./Toast";

export default function SyncBoot() {
  const { api } = useApi();
  const { toast, dismiss } = useToast();
  const { t } = useI18n();
  useEffect(() => {
    if (!api) return;
    let alive = true;
    const run = async () => {
      const n = await syncOutbox(api);
      if (n > 0 && alive) toast("success", t("toast.synced", { n } as unknown as Record<string, string | number>));
    };
    run();
    window.addEventListener("online", run);
    return () => { alive = false; window.removeEventListener("online", run); };
  }, [api, toast, t]);
  void dismiss;
  return null;
}
