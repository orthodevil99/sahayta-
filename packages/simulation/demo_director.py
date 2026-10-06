"""Sahayta demo director — deterministic replay of docs/demo-scenario.md.

Replays the 14-step "Monsoon flood in Patna" acceptance test against a fresh
backend seed and prints PASS/FAIL per step. Exit code 0 iff all 14 pass.
This is what the demo-video recording runs.

Usage:
    python demo_director.py --scenario patna-flood          # one-click: seed+boot+run
    python demo_director.py --scenario patna-flood --no-boot --base-url http://127.0.0.1:8000
    python demo_director.py --scenario patna-flood --port 8003

Fixture inputs come from data/demo/patna-flood/ (synthetic, labeled).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import (  # noqa: E402
    ADMIN_KEY,
    DATA_DIR,
    BackendBoot,
    api_get,
    api_post,
    api_request,
    devanagari_present,
    encode_multipart,
    latin_present,
)

FIXTURE_DIR = DATA_DIR / "demo" / "patna-flood"
SOS_LAT, SOS_LON = 25.5941, 85.1376
RAVI_ID = "vol-ravi-kumar-patna"


@dataclass
class StepResult:
    index: int
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Ctx:
    base_url: str
    device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    admin_headers: dict[str, str] = field(default_factory=lambda: {"X-Admin-Key": ADMIN_KEY})
    sos_id: str = ""
    task_id: str = ""

    @property
    def device_headers(self) -> dict[str, str]:
        return {"X-Device-Id": self.device_id}


def _expect(cond: bool, detail: str = "") -> tuple[bool, str]:
    return cond, detail


def step_01_health(ctx: Ctx) -> tuple[bool, str]:
    st, payload = api_get(ctx.base_url, "/api/health")
    ok = st == 200 and isinstance(payload, dict) and payload.get("status") == "ok"
    return _expect(ok, f"status={st} payload={str(payload)[:120]}")


def step_02_sos_filed(ctx: Ctx) -> tuple[bool, str]:
    description = (FIXTURE_DIR / "description.txt").read_text(encoding="utf-8").strip()
    photo = (FIXTURE_DIR / "flood-photo.jpg").read_bytes()
    fields = {
        "description": description,
        "lat": str(SOS_LAT),
        "lon": str(SOS_LON),
        "district_id": "patna",
        "language": "hi",
        "client_report_id": str(uuid.uuid4()),
    }
    files = {"photo": ("flood-photo.jpg", "image/jpeg", photo)}
    body, ctype = encode_multipart(fields, files)
    st, resp = api_request(
        "POST", ctx.base_url, "/api/sos", body=body,
        headers={"X-Device-Id": ctx.device_id, "Content-Type": ctype},
        timeout=60.0,
    )
    if st not in (200, 201) or not isinstance(resp, dict):
        return _expect(False, f"status={st} resp={str(resp)[:200]}")
    ctx.sos_id = resp.get("id", "")
    ok = (
        resp.get("status") == "reported"
        and resp.get("district_id") == "patna"
        and bool(ctx.sos_id)
    )
    return _expect(ok, f"status={st} id={ctx.sos_id[:8]}...")


def step_03_severity_assessed(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_get(ctx.base_url, f"/api/sos/{ctx.sos_id}",
                       headers=ctx.device_headers)
    if st != 200 or not isinstance(resp, dict):
        return _expect(False, f"GET sos -> {st}")
    a = resp.get("assessment") or {}
    rationale = a.get("rationale", "")
    checks = [
        (resp.get("severity") == 4, f"severity={resp.get('severity')}"),
        (resp.get("category") == "rescue", f"category={resp.get('category')}"),
        (resp.get("priority") == "critical", f"priority={resp.get('priority')}"),
        (resp.get("needed_skills") == ["rescue", "driving"],
         f"skills={resp.get('needed_skills')}"),
        ("\n" not in rationale and len(rationale) > 10, "rationale one line"),
        (any(w in rationale for w in ["पानी", "घुटन", "छत", "water", "rooftop", "waist", "knee"]),
         f"rationale mentions depth/people: {rationale[:80]}"),
        (bool(a.get("model")), f"model={a.get('model')}"),
    ]
    bad = [d for ok, d in checks if not ok]
    return _expect(not bad, "; ".join(bad) if bad else f"model={a.get('model')}")


def step_04_board_lists_sos(ctx: Ctx) -> tuple[bool, str]:
    st, listing = api_get(
        ctx.base_url, "/api/sos?district=patna&severity_min=4&limit=50",
        headers=ctx.device_headers,
    )
    if st != 200 or not isinstance(listing, dict):
        return _expect(False, f"list -> {st}")
    ids = [i.get("id") for i in listing.get("items", [])]
    st2, full = api_get(ctx.base_url, f"/api/sos/{ctx.sos_id}",
                        headers=ctx.device_headers)
    ok = (ctx.sos_id in ids
          and st2 == 200 and isinstance(full, dict)
          and isinstance(full.get("assessment"), dict))
    return _expect(ok, f"in_list={ctx.sos_id in ids} nested_assessment={isinstance((full or {}).get('assessment'), dict)}")


def step_05_volunteer_matched(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_post(ctx.base_url, "/api/tasks/match",
                        {"sos_id": ctx.sos_id, "max_results": 5},
                        headers=ctx.device_headers)
    if st != 200 or not isinstance(resp, dict) or not resp.get("matches"):
        return _expect(False, f"match -> {st}")
    top = resp["matches"][0]
    vol = top.get("volunteer", {}) or {}
    reasons = " ".join(top.get("reasons", [])).lower()
    dist = top.get("distance_km", 999)
    checks = [
        (vol.get("id") == RAVI_ID, f"top={vol.get('id')}"),
        (top.get("score", 0) >= 80, f"score={top.get('score')}"),
        (abs(dist - 2.1) <= 0.5, f"distance_km={dist}"),
        ("skill match: rescue" in reasons, f"reasons={top.get('reasons')}"),
    ]
    bad = [d for ok, d in checks if not ok]
    return _expect(not bad, "; ".join(bad) if bad else f"score={top.get('score')} dist={dist}")


def step_06_task_dispatched(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_post(ctx.base_url, "/api/tasks",
                        {"sos_id": ctx.sos_id, "volunteer_id": RAVI_ID,
                         "note": "Nearest rescue volunteer"},
                        headers=ctx.admin_headers)
    if st != 201 or not isinstance(resp, dict):
        return _expect(False, f"status={st} resp={str(resp)[:200]}")
    ctx.task_id = resp.get("id", "")
    ok = resp.get("status") == "assigned" and bool(ctx.task_id)
    return _expect(ok, f"task={ctx.task_id[:8]}... status={resp.get('status')}")


def step_07_task_accepted(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_post(ctx.base_url, f"/api/tasks/{ctx.task_id}/accept",
                        {}, headers=ctx.admin_headers)
    ok = st == 200 and isinstance(resp, dict) and resp.get("status") == "accepted"
    return _expect(ok, f"status={st} -> {(resp or {}).get('status')}")


def step_08_sos_help_on_way(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_post(ctx.base_url, f"/api/tasks/{ctx.task_id}/enroute",
                        {}, headers=ctx.admin_headers)
    if st != 200:
        return _expect(False, f"enroute -> {st}")
    st2, sos = api_get(ctx.base_url, f"/api/sos/{ctx.sos_id}",
                       headers=ctx.device_headers)
    ok = st2 == 200 and isinstance(sos, dict) and sos.get("status") == "help_on_way"
    return _expect(ok, f"sos status={(sos or {}).get('status')}")


def step_09_task_completed(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_post(ctx.base_url, f"/api/tasks/{ctx.task_id}/complete",
                        {"note": "Residents moved to relief camp; lane dewatered."},
                        headers=ctx.admin_headers)
    if st != 200:
        return _expect(False, f"complete -> {st}")
    st2, sos = api_get(ctx.base_url, f"/api/sos/{ctx.sos_id}",
                       headers=ctx.device_headers)
    st3, vol = api_get(ctx.base_url, f"/api/volunteers/{RAVI_ID}",
                       headers=ctx.admin_headers)
    checks = [
        (isinstance(sos, dict) and sos.get("status") == "resolved",
         f"sos={(sos or {}).get('status')}"),
        (isinstance(vol, dict) and vol.get("reputation") == 52,
         f"reputation={(vol or {}).get('reputation')}"),
        (isinstance(vol, dict) and vol.get("tasks_completed") == 1,
         f"tasks_completed={(vol or {}).get('tasks_completed')}"),
    ]
    bad = [d for ok, d in checks if not ok]
    return _expect(not bad, "; ".join(bad) if bad else "resolved, rep 52, 1 task")


def step_10_broadcast_sent(ctx: Ctx) -> tuple[bool, str]:
    body = ("पटना के कंकड़बाग इलाके में पानी तेजी से बढ़ रहा है। निचले इलाकों के "
            "निवासी तुरंत ऊंचे स्थानों पर जाएं। राहत शिविर खुले हैं: पटना हाई स्कूल, "
            "कंकड़बाग। हेल्पलाइन: 1078।")
    st, resp = api_post(ctx.base_url, "/api/alerts/broadcast",
                        {"district_ids": ["patna"], "type": "flood",
                         "title": "बाढ़ चेतावनी", "body": body,
                         "severity": 4, "languages": ["hi", "hing"]},
                        headers=ctx.admin_headers, timeout=60.0)
    if st != 202 or not isinstance(resp, dict):
        return _expect(False, f"status={st} resp={str(resp)[:200]}")
    rendered = resp.get("rendered", {}) or {}
    hi, hing = rendered.get("hi", ""), rendered.get("hing", "")
    checks = [
        (len(hi) <= 480 and len(hi) > 20, f"hi len={len(hi)}"),
        (devanagari_present(hi), "hi Devanagari"),
        (any(w in hi for w in ["पटना", "Patna", "कंकड़बाग", "Kankarbagh"]),
         f"hi mentions place: {hi[:90]}"),
        (any(w in hi for w in ["पानी", "जाएं", "शिविर", "हेल्पलाइन"]),
         "hi safety action"),
        (len(hing) <= 480 and latin_present(hing), f"hing len={len(hing)} latin"),
    ]
    bad = [d for ok, d in checks if not ok]
    return _expect(not bad, "; ".join(bad) if bad else "hi+hing rendered")


def step_11_admin_overview(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_get(ctx.base_url, "/api/admin/overview?district=patna",
                       headers=ctx.admin_headers)
    if st != 200 or not isinstance(resp, dict):
        return _expect(False, f"overview -> {st}")
    need = ["sos_by_status", "sos_by_severity", "district_risk",
            "volunteers_active", "pending_verifications"]
    missing = [k for k in need if k not in resp]
    return _expect(not missing, f"missing={missing}" if missing
                   else f"risk={resp.get('district_risk')}")


def step_12_district_risk(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_get(ctx.base_url, "/api/districts/patna/risk",
                       headers=ctx.device_headers)
    if st != 200 or not isinstance(resp, dict):
        return _expect(False, f"risk -> {st}")
    factors = resp.get("factors", []) or []
    checks = [
        (resp.get("risk", 0) >= 70, f"risk={resp.get('risk')}"),
        (len(factors) > 0, "factors non-empty"),
        (bool(resp.get("weather_source")), f"source={resp.get('weather_source')}"),
    ]
    bad = [d for ok, d in checks if not ok]
    return _expect(not bad, "; ".join(bad) if bad else
                   f"risk={resp.get('risk')}/{resp.get('risk_level')}")


def step_13_warnings_status(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_get(ctx.base_url, "/api/warnings/status",
                       headers=ctx.device_headers)
    if st != 200 or not isinstance(resp, dict):
        return _expect(False, f"warnings/status -> {st}")
    checks = [
        (resp.get("enabled") is True, f"enabled={resp.get('enabled')}"),
        (resp.get("districts_tracked") == 20,
         f"tracked={resp.get('districts_tracked')}"),
        (resp.get("last_ingest_ok") is True,
         f"last_ingest_ok={resp.get('last_ingest_ok')}"),
    ]
    bad = [d for ok, d in checks if not ok]
    return _expect(not bad, "; ".join(bad) if bad else "enabled, 20 districts")


def step_14_forecast(ctx: Ctx) -> tuple[bool, str]:
    st, resp = api_get(ctx.base_url, "/api/districts/patna/forecast",
                       headers=ctx.device_headers)
    if st != 200 or not isinstance(resp, dict):
        return _expect(False, f"forecast -> {st}")
    hours = resp.get("hours", []) or []
    bad_hours = [h for h in hours if "risk" not in h or "risk_level" not in h]
    ok = len(hours) == 72 and not bad_hours
    return _expect(ok, f"hours={len(hours)} bad={len(bad_hours)}")


STEPS: list[tuple[str, Callable[[Ctx], tuple[bool, str]]]] = [
    ("api_health", step_01_health),
    ("sos_filed", step_02_sos_filed),
    ("severity_assessed", step_03_severity_assessed),
    ("board_lists_sos", step_04_board_lists_sos),
    ("volunteer_matched", step_05_volunteer_matched),
    ("task_dispatched", step_06_task_dispatched),
    ("task_accepted", step_07_task_accepted),
    ("sos_help_on_way", step_08_sos_help_on_way),
    ("task_completed", step_09_task_completed),
    ("broadcast_sent", step_10_broadcast_sent),
    ("admin_overview", step_11_admin_overview),
    ("district_risk", step_12_district_risk),
    ("warnings_status", step_13_warnings_status),
    ("forecast_72h", step_14_forecast),
]


def run_director(base_url: str) -> list[StepResult]:
    ctx = Ctx(base_url=base_url)
    results: list[StepResult] = []
    for i, (name, fn) in enumerate(STEPS, start=1):
        try:
            passed, detail = fn(ctx)
        except Exception as exc:  # noqa: BLE001 — a step must never crash the run
            passed, detail = False, f"exception: {type(exc).__name__}: {exc}"
        results.append(StepResult(i, name, passed, detail))
        status = "PASS" if passed else "FAIL"
        print(f"STEP {i:02d}/14 {name:20s} : {status}"
              + (f" — {detail}" if detail else ""), flush=True)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Sahayta demo director")
    ap.add_argument("--scenario", default="patna-flood",
                    help="only 'patna-flood' is supported in v1")
    ap.add_argument("--port", type=int, default=8003)
    ap.add_argument("--no-boot", action="store_true",
                    help="drive an already-running backend instead of booting one")
    ap.add_argument("--base-url", default="")
    args = ap.parse_args()

    if args.scenario != "patna-flood":
        print(f"unknown scenario: {args.scenario} (v1 supports only patna-flood)",
              file=sys.stderr)
        return 2
    if not FIXTURE_DIR.exists():
        print(f"fixture dir missing: {FIXTURE_DIR}", file=sys.stderr)
        return 2

    print("=== Sahayta demo director : patna-flood (14 steps, all synthetic) ===",
          flush=True)
    if args.no_boot:
        base_url = args.base_url or "http://127.0.0.1:8000"
        results = run_director(base_url)
    else:
        with BackendBoot(port=args.port) as base_url:
            results = run_director(base_url)

    failed = [r for r in results if not r.passed]
    print(f"=== {len(results) - len(failed)}/14 steps PASS ===", flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
