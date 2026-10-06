"""Shared pools, RNG helpers and constants for Sahayta synthetic data generation.

ALL DATA PRODUCED WITH THESE POOLS IS SYNTHETIC — demo fixtures only.
Deterministic: every generator seeds its own random.Random instance.
"""
import json
import random
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent
SEED = 20261006

# ---------------------------------------------------------------- districts
def load_districts():
    with open(DATA_DIR / "districts.json", encoding="utf-8") as f:
        return json.load(f)["districts"]

# ------------------------------------------------------------------ helpers
def make_rng(salt: str) -> random.Random:
    return random.Random(f"{SEED}-{salt}")

def new_uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))

def indian_phone(rng: random.Random) -> str:
    # NOTE: all phone numbers are fake (synthetic demo data)
    return f"+91-{rng.choice(['6','7','8','9'])}{rng.randint(100000000, 999999999)}"

def jitter(rng, lat, lon, spread=0.25):
    return (round(lat + rng.uniform(-spread, spread), 6),
            round(lon + rng.uniform(-spread, spread), 6))

# --------------------------------------------------------------- name pools
FIRST_NAMES = [
    "Aarav","Aisha","Amit","Anjali","Ankit","Arjun","Asha","Avinash","Deepak","Divya",
    "Farhan","Gita","Harish","Imran","Jyoti","Kabir","Kajal","Karan","Kavita","Kunal",
    "Lakshmi","Manoj","Meena","Mohammed","Neha","Nikhil","Pooja","Priya","Rahul","Rajesh",
    "Rakesh","Rani","Ravi","Rekha","Rohit","Sana","Sandeep","Sanjay","Seema","Shabnam",
    "Shankar","Shilpa","Shivam","Simran","Sita","Sohan","Suman","Sunil","Sunita","Suresh",
    "Vikash","Vikram","Vinod","Zoya","Aditya","Anita","Chandan","Dinesh","Guddi","Hemant",
]
LAST_NAMES = [
    "Kumar","Devi","Singh","Yadav","Sharma","Verma","Gupta","Mishra","Tiwari","Pandey",
    "Chaudhary","Paswan","Das","Mandal","Sahni","Khan","Ansari","Khatun","Begum","Ali",
    "Rai","Thakur","Jha","Ojha","Dubey","Pathak","Srivastava","Saxena","Agarwal","Jain",
    "Patel","Shah","Reddy","Nair","Iyer","Dasgupta","Banerjee","Chatterjee","Dutta","Ghosh",
    "Mukherjee","Sen","Bose","Pillai","Menon","Rao","Naidu","Kulkarni","Deshmukh","Patil",
]

# Localities per district slug (used to ground descriptions)
LOCALITIES = {
    "patna": ["Kankarbagh","Rajendra Nagar","Patrakar Nagar","Boring Road","Danapur","Phulwari Sharif","Mithapur","Ashok Rajpath","Gandhi Maidan","Digha"],
    "vaishali": ["Hajipur","Mahnar","Lalganj","Bidupur","Raghopur"],
    "gaya": ["Bodh Gaya","Manpur","Belaganj","Tekari","Sherghati"],
    "muzaffarpur": ["Motihari Road","Kanti","Sahebganj","Baruraj","Mushahari"],
    "darbhanga": ["Laheriasarai","Benipur","Bahadurpur","Keoti","Jale"],
    "bhagalpur": ["Tilkamanjhi","Sultanganj","Naugachia","Sabour","Kahalgaon"],
    "purnia": ["Gulabbagh","Banmankhi","Dhamdaha","Kasba","Rupauli"],
    "katihar": ["Manihari","Barsoi","Kadwa","Kursela","Pranpur"],
    "samastipur": ["Dalsinghsarai","Rosera","Tajpur","Khanpur","Pusa"],
    "sitamarhi": ["Dumra","Bairgania","Sursand","Pupri","Belsand"],
    "lucknow": ["Gomti Nagar","Aliganj","Indira Nagar","Chowk","Aminabad"],
    "gorakhpur": ["Golghar","Mohaddipur","Kushmi","Pipraich","Sahjanwa"],
    "varanasi": ["Godowlia","Sigra","Lanka","Pandeypur","Ramnagar"],
    "guwahati": ["Ganeshguri","Beltola","Maligaon","Chandmari","Paltan Bazaar"],
    "dibrugarh": ["Mancotta","Boiragimoth","Naliapool","Chowkidingee","Mohanbari"],
    "kolkata": ["Behala","Dum Dum","Salt Lake","Howrah Bridge","Sealdah"],
    "howrah": ["Shibpur","Liluah","Bally","Uluberia","Santragachi"],
    "puri": ["Sea Beach Road","Chakratirtha","Talabania","Satyabadi","Delang"],
    "nagpur": ["Dharampeth","Sitabuldi","Manewada","Hingna","Kamptee"],
    "chennai": ["T Nagar","Velachery","Anna Nagar","Adyar","Porur"],
}

CATEGORIES = ["medical","rescue","food","shelter","infrastructure","other"]
CATEGORY_SKILLS = {
    "medical": ["medical","driving"],
    "rescue": ["rescue","driving"],
    "food": ["cooking","logistics"],
    "shelter": ["shelter_mgmt","logistics"],
    "infrastructure": ["engineering","logistics"],
    "other": ["logistics"],
}
VOLUNTEER_SKILLS = ["medical","rescue","driving","cooking","shelter_mgmt",
                    "translation","logistics","counseling","engineering"]
LANG_CODES = ["hi","hing","bn","ta","te","mr","gu","kn","ml","pa","en"]

SEVERITY_PRIORITY = {1: "low", 2: "medium", 3: "high", 4: "critical", 5: "critical"}

# ------------------------------------------------- SOS description templates
# Slots: {name} {locality} {district} {detail}
SOS_TEMPLATES = {
"medical": {
"hi": [
"{name} को तेज़ बुखार और उल्टी हो रही है, दवा चाहिए। {locality}, {district}।",
"बुजुर्ग महिला को साँस लेने में दिक्कत है, ऑक्सीजन की ज़रूरत। {locality}।",
"बच्चे को चोट लगी है, पट्टी और दवा चाहिए। {locality}, {district}।",
"गर्भवती महिला को अस्पताल ले जाना है, रास्ते में पानी भरा है। {locality}।",
"डायबिटीज़ की दवा खत्म हो गई, इंसुलिन चाहिए। {locality}, {district}।",
"{name} को साँप ने काटा है, तुरंत एंटी-वेनम चाहिए। {locality}।",
"दिल के मरीज़ की दवा बह गई, मदद चाहिए। {locality}, {district}।",
"बच्चे को दस्त लग गए हैं, ORS चाहिए। {locality}।",
],
"hing": [
"{name} ko tez bukhar hai, dawai chahiye. {locality}, {district}.",
"Buzurg aadmi ko saans lene me dikkat, oxygen chahiye. {locality}.",
"Bacche ko chot lagi hai, first-aid chahiye. {locality}, {district}.",
"Pregnant lady ko hospital le jana hai, raaste me paani bhara hai. {locality}.",
"BP ki dawai khatam ho gayi, medical help chahiye. {locality}, {district}.",
"{name} ko chakkar aa rahe hain, doctor chahiye. {locality}.",
],
"en": [
"{name} has high fever and vomiting, needs medicine urgently. {locality}, {district}.",
"Elderly woman having breathing difficulty, needs oxygen support. {locality}.",
"Child injured, needs first aid and bandages. {locality}, {district}.",
"Pregnant woman needs to reach hospital but roads are flooded. {locality}.",
"Diabetic patient ran out of insulin, needs medical help. {locality}, {district}.",
"Snakebite victim needs anti-venom immediately. {locality}.",
],
"bn": [
"{name}-এর জ্বর ও বমি হচ্ছে, ওষুধ দরকার। {locality}, {district}।",
"বৃদ্ধ মহিলার শ্বাসকষ্ট হচ্ছে, অক্সিজেন দরকার। {locality}।",
"শিশু আহত হয়েছে, ফার্স্ট-এড দরকার। {locality}, {district}।",
],
},
"rescue": {
"hi": [
"{locality} में घुटनों तक पानी भर गया है, घरों में पानी घुस गया है। तुरंत मदद चाहिए।",
"बुजुर्ग छत पर फँसे हैं, नाव चाहिए। {locality}, {district}।",
"दो गलियों में पानी कमर तक पहुँच गया, बच्चे फँसे हैं। {locality}।",
"{name} का परिवार पहली मंज़िल पर फँसा है, निकालने में मदद चाहिए। {locality}, {district}।",
"पानी तेज़ी से बढ़ रहा है, {locality} के 10 घरों को खाली कराना है।",
"मकान की दीवार गिरने वाली है, अंदर लोग हैं। {locality}, {district}।",
"नाला उफन गया है, {locality} में लोग फँसे हैं।",
"पेड़ गिरने से रास्ता बंद, एम्बुलेंस नहीं पहुँच रही। {locality}।",
],
"hing": [
"{locality} me ghutno tak paani bhar gaya hai, gharon me paani ghus gaya. Turant madad chahiye.",
"Buzurg chhat par fanse hain, naav chahiye. {locality}, {district}.",
"Do galiyon me paani kamar tak pahunch gaya, bacche fanse hain. {locality}.",
"{name} ka parivaar first floor par fansa hai, nikalne me help chahiye. {locality}, {district}.",
"Paani tezi se badh raha hai, {locality} ke 10 gharon ko khaali karana hai.",
"Ped girne se raasta band, ambulance nahi pahunch rahi. {locality}.",
],
"en": [
"Knee-deep water has flooded {locality}, water entered homes. Need immediate help.",
"Elderly people stranded on rooftop, need a boat. {locality}, {district}.",
"Waist-deep water in two lanes, children trapped. {locality}.",
"{name}'s family is stuck on the first floor, need evacuation help. {locality}, {district}.",
"Water rising fast, 10 houses in {locality} need evacuation.",
"Tree fallen blocking road, ambulance cannot reach. {locality}.",
],
"bn": [
"{locality}-তে হাঁটু পর্যন্ত জল উঠেছে, বাড়িতে জল ঢুকেছে। দ্রুত সাহায্য দরকার।",
"বৃদ্ধরা ছাদে আটকে আছেন, নৌকা দরকার। {locality}, {district}।",
"দুটি গলিতে কোমর পর্যন্ত জল, শিশুরা আটকে আছে। {locality}।",
],
},
"food": {
"hi": [
"{locality} में 20 परिवारों के पास खाने को कुछ नहीं, राशन चाहिए।",
"बच्चों के लिए दूध नहीं है, {locality}, {district}।",
"राहत शिविर में खाना खत्म हो गया, {locality}।",
"{name} के घर चूल्हा डूब गया, पका खाना चाहिए। {locality}, {district}।",
"3 दिन से चूल्हा नहीं जला, सूखा राशन चाहिए। {locality}।",
],
"hing": [
"{locality} me 20 parivaaron ke paas khaane ko kuch nahi, ration chahiye.",
"Bacchon ke liye doodh nahi hai, {locality}, {district}.",
"Relief camp me khaana khatam ho gaya, {locality}.",
"{name} ke ghar chulha doob gaya, paka khaana chahiye. {locality}, {district}.",
],
"en": [
"20 families in {locality} have no food left, need ration kits.",
"No milk for infants in {locality}, {district}.",
"Relief camp at {locality} ran out of cooked food.",
"{name}'s stove is submerged, needs cooked meals. {locality}, {district}.",
],
"bn": [
"{locality}-তে ২০টি পরিবারের খাবার নেই, রেশন দরকার।",
"শিশুদের জন্য দুধ নেই, {locality}, {district}।",
],
},
"shelter": {
"hi": [
"घर में पानी भर गया, {name} के परिवार को रहने की जगह चाहिए। {locality}।",
"{locality} में 15 लोग खुले में हैं, टेंट चाहिए।",
"मकान गिर गया है, परिवार को शिविर में जगह चाहिए। {locality}, {district}।",
"बाढ़ में घर बह गया, 6 लोगों को आश्रय चाहिए। {locality}।",
],
"hing": [
"Ghar me paani bhar gaya, {name} ke parivaar ko rehne ki jagah chahiye. {locality}.",
"{locality} me 15 log khule me hain, tent chahiye.",
"Makaan gir gaya hai, parivaar ko camp me jagah chahiye. {locality}, {district}.",
],
"en": [
"House flooded, {name}'s family needs a place to stay. {locality}.",
"15 people in the open at {locality}, need tents.",
"House collapsed, family needs space in a relief camp. {locality}, {district}.",
],
"bn": [
"বাড়িতে জল ঢুকেছে, {name}-এর পরিবারের থাকার জায়গা দরকার। {locality}।",
"{locality}-তে ১৫ জন খোলা আকাশের নিচে, তাঁবু দরকার।",
],
},
"infrastructure": {
"hi": [
"{locality} में बिजली का खंभा गिर गया, तार सड़क पर हैं।",
"पानी की टंकी दूषित हो गई, साफ पानी नहीं। {locality}, {district}।",
"{locality} का पुल टूट गया, गाँव का संपर्क कटा।",
"मोबाइल टावर बंद, {locality} में नेटवर्क नहीं।",
"सड़क धँस गई है, {locality} में वाहन नहीं जा रहे।",
],
"hing": [
"{locality} me bijli ka khamba gir gaya, taar sadak par hain.",
"Paani ki tanki dooshit ho gayi, saaf paani nahi. {locality}, {district}.",
"{locality} ka pul toot gaya, gaon ka sampark kata.",
"Mobile tower band, {locality} me network nahi.",
],
"en": [
"Electric pole fallen in {locality}, live wires on the road.",
"Water tank contaminated, no clean drinking water. {locality}, {district}.",
"Bridge at {locality} collapsed, village cut off.",
"Mobile tower down, no network in {locality}.",
],
"bn": [
"{locality}-তে বিদ্যুতের খুঁটি পড়ে গেছে, তার রাস্তায়।",
"জলের ট্যাঙ্কি দূষিত, পরিষ্কার জল নেই। {locality}, {district}।",
],
},
"other": {
"hi": [
"{locality} में मदद चाहिए, स्थिति बिगड़ रही है।",
"{name} को सहायता चाहिए। {locality}, {district}।",
],
"hing": [
"{locality} me madad chahiye, sthiti bigad rahi hai.",
"{name} ko sahayata chahiye. {locality}, {district}.",
],
"en": [
"Need help at {locality}, situation worsening.",
"{name} needs assistance. {locality}, {district}.",
],
"bn": [
"{locality}-তে সাহায্য দরকার, পরিস্থিতি খারাপ হচ্ছে।",
],
},
}

# Short generic templates for the remaining 7 languages (ta/te/mr/gu/kn/ml/pa)
OTHER_LANG_TEMPLATES = {
"ta": "{locality}-இல் உதவி தேவை, {district}. உடனடி நிவாரணம் வேண்டும்.",
"te": "{locality}లో సహాయం కావాలి, {district}. తక్షణ సహాయం అవసరం.",
"mr": "{locality} मध्ये मदत हवी आहे, {district}. तातडीने मदत पाठवा.",
"gu": "{locality} માં મદદ જોઈએ છે, {district}. તાત્કાલિક મદદ મોકલો.",
"kn": "{locality}ನಲ್ಲಿ ಸಹಾಯ ಬೇಕು, {district}. ತಕ್ಷಣ ಸಹಾಯ ಕಳುಹಿಸಿ.",
"ml": "{locality}-ൽ സഹായം വേണം, {district}. അടിയന്തര സഹായം അയയ്ക്കുക.",
"pa": "{locality} ਵਿੱਚ ਮਦਦ ਚਾਹੀਦੀ ਹੈ, {district}. ਤੁਰੰਤ ਮਦਦ ਭੇਜੋ.",
}

# ------------------------------------------------------- photo descriptions
# Slots: {place} {locality} {detail}
PLACES = ["residential lane","market road","main road","village street","school compound",
          "railway underpass","bus stand","riverside ghat","low-lying colony","highway stretch"]
PHOTO_DETAILS = [
    "a stranded auto-rickshaw half submerged",
    "children sitting on a raised platform",
    "floating debris and household items",
    "power lines hanging low over the water",
    "a rescue boat visible in the distance",
    "an elderly couple watching from a balcony",
    "volunteers distributing water bottles",
    "a dog swimming across the lane",
    "submerged hand-pumps and shops",
    "people carrying belongings on their heads",
]
PHOTO_TEMPLATES = {
"flood": {
1: ["Light rainwater puddles on a {place} in {locality}; people walking normally with umbrellas; no disruption visible.",
    "Damp {place} in {locality} after a shower; normal traffic; shops open."],
2: ["Ankle-deep waterlogging on a {place} in {locality}; two-wheelers moving slowly; {detail}.",
    "Shin-deep rainwater on a {place} in {locality}; pedestrians wading carefully; shops placing sandbags."],
3: ["Knee-deep floodwater covering a {place} in {locality}; residents wading with belongings; {detail}.",
    "Knee-to-thigh deep water in a {place} in {locality}; ground floors flooded; people moving to upper floors."],
4: ["Waist-deep brown floodwater submerging a {place} in {locality}; water entering ground-floor homes; {detail}.",
    "Chest-high water rising in a {place} in {locality}; residents stranded on rooftops; {detail}."],
5: ["Chest-deep fast-flowing floodwater across {locality}; houses partially submerged with only roofs visible; people stranded on rooftops waving for help; {detail}.",
    "Severe flooding in {locality}; entire {place} underwater; families on rooftops; {detail}."],
},
"heatwave": {
1: ["Hot sunny afternoon in {locality}; people using umbrellas; streets active.",
    "Bright harsh sunlight over a {place} in {locality}; normal crowd with sun protection."],
2: ["Scorching heat in {locality} market; vendors covering stalls with wet cloth; people drinking water frequently.",
    "Very hot midday on a {place} in {locality}; shutters half-down; {detail}."],
3: ["Intense heatwave in {locality}; nearly empty streets at noon; a man resting in shade showing heat exhaustion; {detail}.",
    "Blazing heat over {locality}; cracked dry ground; labourers resting under a tree."],
4: ["Severe heatwave in {locality}; elderly person collapsed near a bus stop; bystanders giving water; {detail}.",
    "Extreme heat in {locality}; thermometer reading dangerously high; streets deserted."],
5: ["Extreme heat emergency in {locality}; multiple people fainted on the street; ambulance present; {detail}.",
    "Deadly heatwave in {locality}; hospital entrance crowded; shops shuttered in peak afternoon."],
},
"cyclone": {
1: ["Overcast sky with strong winds in {locality}; trees swaying; fishermen securing boats.",
    "Dark clouds gathering over {locality}; rough sea; people moving indoors."],
2: ["Heavy rain and gusty winds in {locality}; tin roofs rattling; {detail}.",
    "Strong winds bending trees on a {place} in {locality}; rain lashing sideways."],
3: ["Cyclonic storm hitting {locality}; fallen trees blocking the road; damaged shop signboards; {detail}.",
    "Severe winds in {locality}; uprooted small trees; waterlogging beginning."],
4: ["Severe cyclone landfall near {locality}; uprooted trees and electric poles; houses with roofs torn off; {detail}.",
    "Destructive winds battering {locality}; collapsed boundary walls; streets flooded."],
5: ["Catastrophic cyclone devastation in {locality}; collapsed buildings; submerged streets; rescue teams evacuating residents; {detail}.",
    "Massive storm surge flooding {locality}; boats washed onto roads; {detail}."],
},
}

SEVERITY_RATIONALES = {
1: ["Minor waterlogging with no disruption to people or property.",
    "Mild conditions; situation under control, no urgent action needed.",
    "Light impact visible; monitoring is sufficient for now."],
2: ["Ankle-deep water slowing movement; manageable with precautions.",
    "Moderate disruption; vulnerable people should take care.",
    "Noticeable impact but daily life continues with adjustments."],
3: ["Knee-deep water affecting homes and movement; vulnerable people at risk.",
    "Significant flooding; evacuation of low-lying homes advised.",
    "Water entering ground floors; relief assistance likely needed soon."],
4: ["Waist-deep water entering homes; residents stranded; urgent rescue needed.",
    "Severe flooding with people trapped; immediate evacuation required.",
    "Deep water across residential areas; critical rescue situation."],
5: ["Life-threatening flooding with people stranded; immediate mass rescue required.",
    "Catastrophic conditions; large-scale emergency response needed.",
    "Extreme danger to life; highest-priority rescue operation."],
}
