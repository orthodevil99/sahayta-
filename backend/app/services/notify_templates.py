"""SMS-style notification templates for volunteer task events.

DEMO HONESTY: these are templates only. v1 sends no real SMS — the backend
exposes them via GET /api/tasks/{id}/notifications (an SMS preview for the
demo/video), and a real deployment would hand the rendered text to an SMS
gateway. Every rendered message is SMS-length (≤ 160 chars, single segment).

Placeholders: {name} (volunteer first name), {district} (district display
name), {km} (distance), {sos} (short SOS id).

Languages: hi, hing, bn, ta, te, mr, gu, kn, ml, pa.
Fallback chain on render: requested → hi → hing.
"""
from __future__ import annotations

NOTIFY_EVENTS: tuple[str, ...] = ("assigned", "accepted", "en_route", "completed", "declined")

LANGS: tuple[str, ...] = ("hi", "hing", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa")

# event -> lang -> template
TEMPLATES: dict[str, dict[str, str]] = {
    "assigned": {
        "hi": "सहायता: {district} में नया कार्य, {km} किमी दूर (SOS {sos})। ऐप में स्वीकार करें।",
        "hing": "Sahayta: {district} me naya task, {km} km door (SOS {sos}). App me accept karein.",
        "bn": "সহায়তা: {district}-এ নতুন কাজ, {km} কিমি দূরে (SOS {sos})। অ্যাপে গ্রহণ করুন।",
        "ta": "சகாய்தா: {district}-இல் புதிய பணி, {km} கிமீ தொலைவில் (SOS {sos}). செயலியில் ஏற்கவும்.",
        "te": "సహాయత: {district}లో కొత్త పని, {km} కిమీ దూరంలో (SOS {sos}). యాప్‌లో అంగీకరించండి.",
        "mr": "सहायता: {district} मध्ये नवीन कार्य, {km} किमी अंतरावर (SOS {sos}). अॅपमध्ये स्वीकारा.",
        "gu": "સહાયતા: {district}માં નવું કાર્ય, {km} કિમી દૂર (SOS {sos}). એપમાં સ્વીકારો.",
        "kn": "ಸಹಾಯತಾ: {district}ನಲ್ಲಿ ಹೊಸ ಕಾರ್ಯ, {km} ಕಿಮೀ ದೂರದಲ್ಲಿ (SOS {sos}). ಆಪ್‌ನಲ್ಲಿ ಸ್ವೀಕರಿಸಿ.",
        "ml": "സഹായത: {district}-ൽ പുതിയ ചുമതല, {km} കിമീ അകലെ (SOS {sos}). ആപ്പിൽ സ്വീകരിക്കുക.",
        "pa": "ਸਹਾਇਤਾ: {district} ਵਿੱਚ ਨਵਾਂ ਕੰਮ, {km} ਕਿਮੀ ਦੂਰ (SOS {sos})। ਐਪ ਵਿੱਚ ਸਵੀਕਾਰ ਕਰੋ।",
    },
    "accepted": {
        "hi": "सहायता: {name} ने कार्य स्वीकार किया (SOS {sos})। मदद जल्द पहुंचेगी।",
        "hing": "Sahayta: {name} ne task accept kiya (SOS {sos}). Madad jald pahunchegi.",
        "bn": "সহায়তা: {name} কাজটি গ্রহণ করেছেন (SOS {sos})। সাহায্য শীঘ্রই পৌঁছাবে।",
        "ta": "சகாய்தா: {name} பணியை ஏற்றுக்கொண்டார் (SOS {sos}). உதவி விரைவில் வரும்.",
        "te": "సహాయత: {name} పనిని అంగీకరించారు (SOS {sos}). సహాయం త్వరలో చేరుతుంది.",
        "mr": "सहायता: {name} यांनी कार्य स्वीकारले (SOS {sos}). मदत लवकरच पोहोचेल.",
        "gu": "સહાયતા: {name}એ કાર્ય સ્વીકાર્યું (SOS {sos}). મદદ જલ્દી પહોંચશે.",
        "kn": "ಸಹಾಯತಾ: {name} ಕಾರ್ಯವನ್ನು ಸ್ವೀಕರಿಸಿದ್ದಾರೆ (SOS {sos}). ಸಹಾಯ ಶೀಘ್ರದಲ್ಲೇ ಬರುತ್ತದೆ.",
        "ml": "സഹായത: {name} ചുമതല ഏറ്റെടുത്തു (SOS {sos}). സഹായം ഉടൻ എത്തും.",
        "pa": "ਸਹਾਇਤਾ: {name} ਨੇ ਕੰਮ ਸਵੀਕਾਰ ਕੀਤਾ (SOS {sos})। ਮਦਦ ਜਲਦੀ ਪਹੁੰਚੇਗੀ।",
    },
    "en_route": {
        "hi": "सहायता: {name} रवाना हो गए (SOS {sos}, {district})। सुरक्षित स्थान पर रहें।",
        "hing": "Sahayta: {name} ravaana ho gaye (SOS {sos}, {district}). Surakshit jagah rahein.",
        "bn": "সহায়তা: {name} রওনা হয়েছেন (SOS {sos}, {district})। নিরাপদ স্থানে থাকুন।",
        "ta": "சகாய்தா: {name} புறப்பட்டுவிட்டார் (SOS {sos}, {district}). பாதுகாப்பான இடத்தில் இருங்கள்.",
        "te": "సహాయత: {name} బయలుదేరారు (SOS {sos}, {district}). సురక్షిత ప్రదేశంలో ఉండండి.",
        "mr": "सहायता: {name} रवाना झाले (SOS {sos}, {district}). सुरक्षित ठिकाणी रहा.",
        "gu": "સહાયતા: {name} રવાના થયા (SOS {sos}, {district}). સલામત જગ્યાએ રહો.",
        "kn": "ಸಹಾಯತಾ: {name} ಹೊರಟಿದ್ದಾರೆ (SOS {sos}, {district}). ಸುರಕ್ಷಿತ ಸ್ಥಳದಲ್ಲಿರಿ.",
        "ml": "സഹായത: {name} പുറപ്പെട്ടു (SOS {sos}, {district}). സുരക്ഷിത സ്ഥലത്ത് തുടരുക.",
        "pa": "ਸਹਾਇਤਾ: {name} ਰਵਾਨਾ ਹੋ ਗਏ (SOS {sos}, {district})। ਸੁਰੱਖਿਅਤ ਥਾਂ 'ਤੇ ਰਹੋ।",
    },
    "completed": {
        "hi": "सहायता: SOS {sos} पूर्ण। {name} ने मदद पहुंचाई। धन्यवाद!",
        "hing": "Sahayta: SOS {sos} poorn. {name} ne madad pahunchayi. Dhanyavaad!",
        "bn": "সহায়তা: SOS {sos} সম্পূর্ণ। {name} সাহায্য পৌঁছে দিয়েছেন। ধন্যবাদ!",
        "ta": "சகாய்தா: SOS {sos} நிறைவு. {name} உதவி செய்தார். நன்றி!",
        "te": "సహాయత: SOS {sos} పూర్తయింది. {name} సహాయం అందించారు. ధన్యవాదాలు!",
        "mr": "सहायता: SOS {sos} पूर्ण. {name} यांनी मदत पोहोचवली. धन्यवाद!",
        "gu": "સહાયતા: SOS {sos} પૂર્ણ. {name}એ મદદ પહોંચાડી. આભાર!",
        "kn": "ಸಹಾಯತಾ: SOS {sos} ಪೂರ್ಣಗೊಂಡಿದೆ. {name} ಸಹಾಯ ಮಾಡಿದ್ದಾರೆ. ಧನ್ಯವಾದ!",
        "ml": "സഹായത: SOS {sos} പൂർത്തിയായി. {name} സഹായം എത്തിച്ചു. നന്ദി!",
        "pa": "ਸਹਾਇਤਾ: SOS {sos} ਪੂਰਾ। {name} ਨੇ ਮਦਦ ਪਹੁੰਚਾਈ। ਧੰਨਵਾਦ!",
    },
    "declined": {
        "hi": "सहायता: {name} यह कार्य नहीं कर सके (SOS {sos})। अगला स्वयंसेवक नियुक्त हो रहा है।",
        "hing": "Sahayta: {name} ye task nahi kar sake (SOS {sos}). Agla volunteer assign ho raha hai.",
        "bn": "সহায়তা: {name} এই কাজটি করতে পারলেন না (SOS {sos})। পরের স্বেচ্ছাসেবক নিয়োগ হচ্ছে।",
        "ta": "சகாய்தா: {name}-ஆல் இப்பணியை செய்ய முடியவில்லை (SOS {sos}). அடுத்த தன்னார்வலர் நியமிக்கப்படுகிறார்.",
        "te": "సహాయత: {name} ఈ పని చేయలేకపోయారు (SOS {sos}). తదుపరి వాలంటీర్‌ను నియమిస్తున్నాము.",
        "mr": "सहायता: {name} हे कार्य करू शकले नाहीत (SOS {sos}). पुढील स्वयंसेवक नेमला जात आहे.",
        "gu": "સહાયતા: {name} આ કાર્ય કરી શક્યા નહીં (SOS {sos}). આગલા સ્વયંસેવકની નિમણૂક થઈ રહી છે.",
        "kn": "ಸಹಾಯತಾ: {name} ಈ ಕಾರ್ಯವನ್ನು ಮಾಡಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ (SOS {sos}). ಮುಂದಿನ ಸ್ವಯಂಸೇವಕರನ್ನು ನೇಮಿಸಲಾಗುತ್ತಿದೆ.",
        "ml": "സഹായത: {name}-ന് ഈ ചുമതല ഏറ്റെടുക്കാനായില്ല (SOS {sos}). അടുത്ത വളണ്ടിയറെ നിയമിക്കുന്നു.",
        "pa": "ਸਹਾਇਤਾ: {name} ਇਹ ਕੰਮ ਨਹੀਂ ਕਰ ਸਕੇ (SOS {sos})। ਅਗਲੇ ਵਲੰਟੀਅਰ ਦੀ ਨਿਯੁਕਤੀ ਹੋ ਰਹੀ ਹੈ।",
    },
}


def render_notification(
    event: str,
    lang: str,
    *,
    name: str = "—",
    district: str = "—",
    km: str = "—",
    sos: str = "—",
) -> str:
    """Render one SMS-length notification. Fallback: lang → hi → hing."""
    if event not in TEMPLATES:
        raise ValueError(f"unknown notification event: {event}")
    by_lang = TEMPLATES[event]
    template = by_lang.get(lang) or by_lang.get("hi") or by_lang["hing"]
    return (
        template.replace("{name}", name)
        .replace("{district}", district)
        .replace("{km}", km)
        .replace("{sos}", sos)
    )


def notification_preview(
    lang: str,
    *,
    name: str = "—",
    district: str = "—",
    km: str = "—",
    sos: str = "—",
) -> dict[str, str]:
    """Render all five lifecycle events for a task context (SMS preview)."""
    return {
        event: render_notification(event, lang, name=name, district=district, km=km, sos=sos)
        for event in NOTIFY_EVENTS
    }
