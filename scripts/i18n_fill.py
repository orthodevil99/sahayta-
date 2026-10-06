"""Merge i18n fill data into frontend/lib/i18n/*.json.

- Adds new demo.* + a11y.toggle_view keys to hi.json and hing.json.
- Fills missing keys in bn/ta/te/mr/gu/kn/ml/pa from scripts/i18n_fill/*_*.py.
- Rebuilds each file in hi.json key order. Updates _meta.
Usage: python3 scripts/i18n_fill.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "frontend" / "lib" / "i18n"
sys.path.insert(0, str(ROOT / "scripts" / "i18n_fill"))

from bn_ta import DATA as D1  # noqa: E402
from te_mr import DATA as D2  # noqa: E402
from gu_kn import DATA as D3  # noqa: E402
from ml_pa import DATA as D4  # noqa: E402

FILL = {**D1, **D2, **D3, **D4}

HI_HING_NEW = {
    "hi": {
        "a11y": {"toggle_view": "दृश्य बदलें"},
        "demo": {
            "go_live": "लाइव देखें",
            "reset_confirm": "डेमो डेटा रीसेट करें?",
            "reset_label": "डेमो रीसेट करें",
            "step_report": "SOS दर्ज",
            "step_assess": "AI गंभीरता 4",
            "step_match": "रवि कुमार मिले",
            "step_accept": "कार्य स्वीकृत",
            "step_enroute": "मदद रास्ते में",
            "step_complete": "सुलझ गई · +2",
            "step_broadcast": "हिंदी अलर्ट भेजा",
            "step_dashboard": "डैशबोर्ड लाइव",
            "complete_note": "डेमो पूरा — लाइव देखने के लिए बोर्ड, स्वयंसेवक, अलर्ट और प्रशासन टैब खोलें।",
        },
    },
    "hing": {
        "a11y": {"toggle_view": "Drishya badlein"},
        "demo": {
            "go_live": "Go live",
            "reset_confirm": "Reset demo data?",
            "reset_label": "Reset demo",
            "step_report": "SOS filed",
            "step_assess": "AI severity 4",
            "step_match": "Ravi Kumar matched",
            "step_accept": "Task accepted",
            "step_enroute": "Help on the way",
            "step_complete": "Resolved · +2",
            "step_broadcast": "Hindi alert sent",
            "step_dashboard": "Dashboard live",
            "complete_note": "Demo complete — open the Board, Volunteer, Alerts and Admin tabs to see it live.",
        },
    },
}


def flat_keys(o, prefix=""):
    ks = []
    for k, v in o.items():
        if k == "_meta":
            continue
        if isinstance(v, dict):
            ks += flat_keys(v, prefix + k + ".")
        else:
            ks.append(prefix + k)
    return ks


def get_nested(o, dotted):
    cur = o
    for p in dotted.split("."):
        cur = cur[p]
    return cur


def set_nested(o, dotted, val):
    parts = dotted.split(".")
    cur = o
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val


def ordered_like_hi(hi, other):
    """Rebuild `other` following hi's key order (namespaces + keys)."""
    out = {}
    for ns, val in hi.items():
        if ns == "_meta":
            continue
        if isinstance(val, dict):
            out[ns] = {}
            for k in val:
                if ns in other and isinstance(other[ns], dict) and k in other[ns]:
                    out[ns][k] = other[ns][k]
                else:
                    out[ns][k] = val[k]  # shouldn't happen after fill
        else:
            out[ns] = other.get(ns, val)
    # keep any extra keys not in hi (shouldn't exist, but don't drop data)
    for ns, val in other.items():
        if ns == "_meta" or ns in out:
            continue
        out[ns] = val
    return out


SUPPLEMENT = {
    "hi": {"admin": {"panel_kpis": "मुख्य आंकड़े"}, "common": {"outbox_n": "{n} रिपोर्ट कतार में"}},
    "hing": {"admin": {"panel_kpis": "KPIs"}, "common": {"outbox_n": "{n} reports queued"}},
    "bn": {"admin": {"panel_kpis": "প্রধান সংখ্যা"}, "common": {"outbox_n": "{n}টি রিপোর্ট কিউতে"}},
    "ta": {"admin": {"panel_kpis": "முக்கிய எண்கள்"}, "common": {"outbox_n": "{n} அறிக்கைகள் வரிசையில்"}},
    "te": {"admin": {"panel_kpis": "ముఖ్య సంఖ్యలు"}, "common": {"outbox_n": "{n} నివేదికలు క్యూలో"}},
    "mr": {"admin": {"panel_kpis": "महत्त्वाची आकडेवारी"}, "common": {"outbox_n": "{n} अहवाल रांगेत"}},
    "gu": {"admin": {"panel_kpis": "મુખ્ય આંકડા"}, "common": {"outbox_n": "{n} રિપોર્ટ કતારમાં"}},
    "kn": {"admin": {"panel_kpis": "ಪ್ರಮುಖ ಅಂಕಿಗಳು"}, "common": {"outbox_n": "{n} ವರದಿಗಳು ಸರದಿಯಲ್ಲಿ"}},
    "ml": {"admin": {"panel_kpis": "പ്രധാന കണക്കുകൾ"}, "common": {"outbox_n": "{n} റിപ്പോർട്ടുകൾ ക്യൂവിൽ"}},
    "pa": {"admin": {"panel_kpis": "ਮੁੱਖ ਅੰਕੜੇ"}, "common": {"outbox_n": "{n} ਰਿਪੋਰਟਾਂ ਕਤਾਰ ਵਿੱਚ"}},
}


def main():
    hi = json.loads((I18N / "hi.json").read_text(encoding="utf-8"))
    hi_keys = flat_keys(hi)

    # 1. hi + hing get the brand-new keys
    for lang, newkeys in HI_HING_NEW.items():
        p = I18N / f"{lang}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        for ns, kv in newkeys.items():
            d.setdefault(ns, {})
            for k, v in kv.items():
                d[ns][k] = v
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{lang}: added {sum(len(v) for v in newkeys.values())} new keys")

    # reload hi (now includes demo.* + toggle_view)
    hi = json.loads((I18N / "hi.json").read_text(encoding="utf-8"))
    hi = {"_meta": hi["_meta"], **ordered_like_hi(hi, hi)}
    (I18N / "hi.json").write_text(json.dumps(hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hi_keys = flat_keys(hi)
    print(f"hi total keys: {len(hi_keys)}")

    # 2. fill the 8 languages
    for lang, fill in FILL.items():
        p = I18N / f"{lang}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        added = 0
        for ns, kv in fill.items():
            for k, v in kv.items():
                dotted = f"{ns}.{k}"
                exists = dotted in set(flat_keys(d))
                if not exists:
                    set_nested(d, dotted, v)
                    added += 1
        missing = [k for k in hi_keys if k not in set(flat_keys(d))]
        d = {"_meta": d["_meta"], **ordered_like_hi(hi, d)}
        d["_meta"]["complete"] = len(missing) == 0
        d["_meta"]["coverage"] = (
            "full parity with hi (Agent 12, Wave 4)" if not missing
            else f"missing {len(missing)} keys (see i18n-coverage)"
        )
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{lang}: +{added} keys, missing={len(missing)}")

    # 3. supplement keys (added after the first fill): hi first, then the rest
    # ordered against the final key set.
    p_hi = I18N / "hi.json"
    d_hi = json.loads(p_hi.read_text(encoding="utf-8"))
    for ns, kv in SUPPLEMENT["hi"].items():
        d_hi.setdefault(ns, {})
        for k, v in kv.items():
            d_hi[ns][k] = v
    d_hi = {"_meta": d_hi["_meta"], **ordered_like_hi(d_hi, d_hi)}
    p_hi.write_text(json.dumps(d_hi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hi = d_hi
    for lang, namespaces in SUPPLEMENT.items():
        if lang == "hi":
            continue
        p = I18N / f"{lang}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        for ns, kv in namespaces.items():
            d.setdefault(ns, {})
            for k, v in kv.items():
                d[ns][k] = v
        d = {"_meta": d["_meta"], **ordered_like_hi(hi, d)}
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("supplement keys applied to all 10 languages")


if __name__ == "__main__":
    main()
