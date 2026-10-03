"""rights.py - where an investor can complain, and in what order.

This module is deterministic. It calls no model and stores no user data. It
is a directory of official Indian complaint channels, each with the order of
escalation and the published time limits.

Last checked against the official sites on 2025-10-03. Deadlines and
eligibility change, so every step tells the reader to confirm on the official
portal before relying on it.

Guardrails:
* Guidance only. This is not legal advice.
* Sangyan never files a complaint and never contacts an organisation.
* No personal data is requested, stored or sent anywhere.

Run it directly:  python -m app.engine.rights [en|hi|ta]
"""

from __future__ import annotations

LAST_CHECKED = "2025-10-03"

LANGUAGES = ("en", "hi", "ta")

URGENT = {
    "en": "If money has been taken from your account without your approval, or "
          "someone asked for an OTP or PIN, call 1930 now and also tell your bank "
          "immediately. Do this before anything else on this page.",
    "hi": "यदि आपके खाते से आपकी अनुमति के बिना पैसा निकाला गया हो, या किसी ने "
          "ओटीपी या पिन माँगा हो, तो तुरंत 1930 पर कॉल करें और अपने बैंक को भी "
          "तुरंत बताएँ। इस पेज के बाकी चरणों से पहले यही करें।",
    "ta": "உங்கள் கணக்கிலிருந்து உங்கள் அனுமதியின்றி பணம் எடுக்கப்பட்டிருந்தால், "
          "அல்லது யாரோ OTP அல்லது PIN கேட்டிருந்தால், உடனே 1930-ஐ அழுத்தவும் "
          "மற்றும் உங்கள் வங்கிக்கும் உடனே தெரிவிக்கவும். இந்தப் பக்கத்தின் மற்ற "
          "படிகளுக்கு முன்பே இதைச் செய்யுங்கள்.",
}

# --------------------------------------------------------------- situations

SITUATIONS: dict = {
    "bank_service": {
        "en": "A bank or lender problem: wrong charge, delay, rude service, loan recovery",
        "hi": "बैंक या ऋणदाता की समस्या: गलत शुल्क, देरी, बुरा व्यवहार, ऋण वसूली",
        "ta": "வங்கி அல்லது கடனளிப்புப் பிரச்சினை: தவறான கட்டணம், தாமதம், மோசமான செயல்பாடு, கடன் வசூல்",
    },
    "securities": {
        "en": "Shares, mutual funds, demat or a broker: wrong statement, service failure, delay in SIP",
        "hi": "शेयर, म्यूचुअल फंड, डीमैट या ब्रोकर: गलत विवरण, सेवा में देरी",
        "ta": "பங்குகள், மியூच்சுவல் நிதி, டிமேட் அல்லது தரைக்கையாளர்: தவறான அறிக்கை, சேவையில் தாமதம்",
    },
    "insurance_claim": {
        "en": "An insurance claim was delayed, reduced or rejected",
        "hi": "बीमा दावा में देरी हुई, कम राशि मिली या दावा अस्वीकृत हुआ",
        "ta": "ஒரு காப்பீட்டு இழப்பீடு தாமதமாக, குறைவாக அல்லது மறுக்கப்பட்டது",
    },
    "fraud": {
        "en": "I lost money to a fake app, a fake call, or someone asked for my OTP",
        "hi": "नकली ऐप, नकली कॉल या ओटीपी माँगने वाले से पैसा डूब गया",
        "ta": "போலி செயலி, போலி அழைப்பு அல்லது OTP கேட்டவரிடம் பணம் இழந்துவிட்டேன்",
    },
    "money_stuck": {
        "en": "Money is stuck: I cannot close my account, withdraw, or get a refund",
        "hi": "पैसा अटका है: खाता बंद नहीं हो रहा, निकाल नहीं पा रहा, रिफंड नहीं मिल रहा",
        "ta": "பணம் சிக்குந்துள்ளது: கணக்கை மூட முடியவில்லை, பணம் பெற முடியவில்லை",
    },
    "unsure": {
        "en": "I am not sure who to contact",
        "hi": "मुझे नहीं पता किससे संपर्क करूँ",
        "ta": "எவருடன் தொடர்பு கொள்வது என்று எனக்குத் தெரியவில்லை",
    },
}

# ------------------------------------------------------------------ ladder

LADDERS: dict = {
    "bank_service": {
        "en": [
            {"step": 1, "who": "Write to the bank's grievance officer",
             "detail": "Use the bank's own grievance channel first, in writing. Keep the complaint number.",
             "days": "The bank normally answers within 15 days.",
             "url": ""},
            {"step": 2, "who": "RBI Complaint Management System (CMS)",
             "detail": "If there is no reply, or the reply is not satisfactory, file on the RBI portal.",
             "days": "You can approach the RBI when the bank has not replied within 30 days.",
             "url": "https://cms.rbi.org.in/"},
            {"step": 3, "who": "National Consumer Helpline",
             "detail": "A free pre-litigation helpline that forwards your complaint to the company or regulator.",
             "days": "Phone 1915.",
             "url": "https://consumerhelpline.gov.in/"},
        ],
        "hi": [
            {"step": 1, "who": "बैंक के शिकायत अधिकारी को लिखें",
             "detail": "पहले बैंक की अपनी शिकायत व्यवस्था में लिखित शिकायत करें। शिकायत संख्या संभाल कर रखें।",
             "days": "बैंक आमतौर पर 15 दिन में उत्तर देता है।",
             "url": ""},
            {"step": 2, "who": "आरबीआई शिकायत प्रबंधन प्रणाली (CMS)",
             "detail": "उत्तर न मिले या असंतोषजनक हो तो आरबीआई पोर्टल पर शिकायत दर्ज करें।",
             "days": "बैंक के 30 दिन में उत्तर न देने पर आप आरबीआई जा सकते हैं।",
             "url": "https://cms.rbi.org.in/"},
            {"step": 3, "who": "राष्ट्रीय उपभोक्ता हेल्पलाइन",
             "detail": "मुफ़्त हेल्पलाइन, आपकी शिकायत संस्था या नियामक तक पहुँचाती है।",
             "days": "फ़ोन 1915।",
             "url": "https://consumerhelpline.gov.in/"},
        ],
        "ta": [
            {"step": 1, "who": "வங்கியின் குறைதாரு அலுவலருக்கு எழுதுங்கள்",
             "detail": "முதலில் வங்கியின் சொந்த குறைதாரு வழியில் எழுத்துப் புகார் அளியுங்கள். புகார் எண்ணைக் காப்பிடுங்கள்.",
             "days": "வங்கி பொதுவாக 15 நாட்களில் பதிலளிக்கும்.",
             "url": ""},
            {"step": 2, "who": "ஆர்பிஐ குறைதாரு மேலாண்டல் (CMS)",
             "detail": "பதில் இல்லை அல்லது திருப்தியில்லை என்றால் ஆர்பிஐ இணையதளத்தில் புகார் அளியுங்கள்.",
             "days": "வங்கி 30 நாட்களில் பதிலளிக்கவில்லை என்றால் ஆர்பிஐ-அை அணுகலாம்.",
             "url": "https://cms.rbi.org.in/"},
            {"step": 3, "who": "தேசிய நிரபயாக உதவி எண்",
             "detail": "இலவச உதவி எண், உங்கள் புகாரை நிறுவனம் அல்லது ஒழுங்குபடுத்தியிடத்திற்கு அனுப்பும்.",
             "days": "தொலைபேசி 1915.",
             "url": "https://consumerhelpline.gov.in/"},
        ],
    },
    "securities": {
        "en": [
            {"step": 1, "who": "Write to the company, broker or fund",
             "detail": "Always complain to the entity first. Regulators expect this step to have been taken.",
             "days": "The entity's response period is 21 calendar days.",
             "url": ""},
            {"step": 2, "who": "SEBI SCORES",
             "detail": "Register the complaint on SEBI's portal. Complaints emailed to SEBI are not accepted.",
             "days": "Lodge within one year of the cause of action. Reviews must be requested in the stated 15-day windows.",
             "url": "https://scores.sebi.gov.in/"},
            {"step": 3, "who": "SMART ODR",
             "detail": "Online pre-conciliation with a participating regulated entity, then conciliation, then arbitration if needed.",
             "days": "Pre-conciliation is free. Later stages may carry costs.",
             "url": "https://smartodr.in/"},
        ],
        "hi": [
            {"step": 1, "who": "कंपनी, ब्रोकर या फंड को लिखें",
             "detail": "पहले उस संस्था को ही शिकायत करें। नियामक यही चाहता है।",
             "days": "संस्था का उत्तर देने का समय 21 कैलेंडर दिन है।",
             "url": ""},
            {"step": 2, "who": "सेबी स्कोर्स (SCORES)",
             "detail": "शिकायत सेबी के पोर्टल पर दर्ज करें। ईमेल से शिकायत स्वीकार नहीं की जाती।",
             "days": "कारण होने के एक साल के भीतर दर्ज करें। समीक्षा के लिए 15 दिन के निर्धारित समय में माँग करें।",
             "url": "https://scores.sebi.gov.in/"},
            {"step": 3, "who": "स्मार्ट ओडीआर",
             "detail": "ऑनलाइन पूर्व-सुलह, फिर सुलह, और ज़रूरत पड़ने पर आर्बिट्रेशन।",
             "days": "पूर्व-सुलह निःशुल्क है। आगे के चरणों में शुल्क लग सकता है।",
             "url": "https://smartodr.in/"},
        ],
        "ta": [
            {"step": 1, "who": "நிறுவனத்திற்கு, தரைக்கையாளரிடம் அல்லது நிதியிடம் எழுதுங்கள்",
             "detail": "முதலில் அந்த அமைப்பிற்கே புகார் அளியுங்கள். ஒழுங்குபடுத்தியிடம் இதை எதிர்பார்க்கிறது.",
             "days": "அமைப்பின் பதில் வழங்கும் காலம் 21 நாட்கள்.",
             "url": ""},
            {"step": 2, "who": "எஸ்பிஐ மதிப்பீடு (SCORES)",
             "detail": "எஸ்பிஐ இணையதளத்தில் பதிவு செய்யுங்கள். மின்னஞ்சல் புகார்கள் ஏற்கப்படுவதில்லை.",
             "days": "காரணம் ஏற்பட்டதிலிருந்து ஓராண்டுக்குள் பதிவு செய்யுங்கள்.",
             "url": "https://scores.sebi.gov.in/"},
            {"step": 3, "who": "ஸ்மார்ட் ஒடிஆர்",
             "detail": "இணைய முன்னரத்தல், பின்னர் ஒப்புதல், தேவைப்பட்டால் வாரியம்.",
             "days": "முன்னரத்தல் இலவசம். பின்னைய நிலைகளுக்கான கட்டணம் இருக்கலாம்.",
             "url": "https://smartodr.in/"},
        ],
    },
    "insurance_claim": {
        "en": [
            {"step": 1, "who": "Tell the insurer first",
             "detail": "Give the insurer written notice of the claim and keep the claim number and every receipt.",
             "days": "Give notice as soon as possible after the incident.",
             "url": ""},
            {"step": 2, "who": "IRDAI Bima Bharosa",
             "detail": "IRDAI's portal for registering an insurance complaint.",
             "days": "Use it after the insurer has not resolved the matter.",
             "url": "https://bimabharosa.irdai.gov.in/"},
            {"step": 3, "who": "Council for Insurance Ombudsmen",
             "detail": "An independent body for eligible insurance disputes, including delayed or rejected claims.",
             "days": "First complain to the insurer and allow 30 days. Then approach the Ombudsman, generally within one year. Claim limit is Rs 50 lakh.",
             "url": "https://www.cioins.co.in/"},
        ],
        "hi": [
            {"step": 1, "who": "पहले बीमा कंपनी को बताएँ",
             "detail": "दावा की लिखित सूचना दें और दावा संख्या तथा सभी रसीदें संभाल कर रखें।",
             "days": "घटना के तुरंत बाद सूचना दें।",
             "url": ""},
            {"step": 2, "who": "आईआरडीएआई बीमा भरोसा (Bima Bharosa)",
             "detail": "बीमा शिकायत दर्ज करने के लिए आईआरडीएआई का पोर्टल।",
             "days": "कंपनी के समाधान न होने पर इस्तेमाल करें।",
             "url": "https://bimabharosa.irdai.gov.in/"},
            {"step": 3, "who": "काउंसिल फॉर इंश्योरेंस ओम्बुड्समैन",
             "detail": "योग्य बीमा विवादों के लिए स्वतंत्र संस्था, जिसमें देरी या अस्वीकृत दावा शामिल हैं।",
             "days": "पहले कंपनी को 30 दिन अवसर दें। फिर ओम्बुड्समैन के पास, सामान्यतः एक वर्ष के भीतर। दावा सीमा 50 लाख रुपये।",
             "url": "https://www.cioins.co.in/"},
        ],
        "ta": [
            {"step": 1, "who": "முதலில் காப்பீட்டு நிறுவனத்திடம் தெரிவியுங்கள்",
             "detail": "கோரிக்கையை எழுத்தில் அறிவியுங்கள்; கோரிக்கை எண்ணையும் அனைத்து ரசீதுகளையும் காப்பிடுங்கள்.",
             "days": "சம்பவத்திற்கு உடனே அறிவியுங்கள்.",
             "url": ""},
            {"step": 2, "who": "ஐஆர்டிஐ பீமா பாரோசா",
             "detail": "காப்பீட்டு புகாரைப் பதிவு செய்யும் இதர்டிஐ இணையதளம்.",
             "days": "நிறுவனம் தீர்க்காதபோது பயன்படுத்துங்கள்.",
             "url": "https://bimabharosa.irdai.gov.in/"},
            {"step": 3, "who": "காப்பீட்டு நடுவர்கள் க council",
             "detail": "தாமதமான அல்லது மறுக்கப்பட்ட கோரிக்கை உள்ளிட்ட பொருத்தமான விவாக்களுக்கான சுதந்திர அமைப்பு.",
             "days": "முதலில் நிறுவனத்துக்கு 30 நாட்கள். பின்னர் நடுவரிடம், பொதுவாக ஓராண்டுக்குள். கோரிக்கை மேல்பரம் 50 லட்சம் ரூபாய்.",
             "url": "https://www.cioins.co.in/"},
        ],
    },
    "fraud": {
        "en": [
            {"step": 1, "who": "Call 1930 now",
             "detail": "This is the national helpline for financial cyber fraud. Call before anything else.",
             "days": "Do it immediately, even if you are not sure.",
             "url": "https://cybercrime.gov.in/"},
            {"step": 2, "who": "Tell your bank or payment provider",
             "detail": "Ask them to freeze or stop the transaction and to mark it as fraud. Do this in the same hour.",
             "days": "Ask for a written reference number.",
             "url": ""},
            {"step": 3, "who": "Report on the cybercrime portal",
             "detail": "File the report on the national portal and keep the acknowledgement number.",
             "days": "Complete the online step within 24 hours of the 1930 acknowledgement.",
             "url": "https://cybercrime.gov.in/"},
        ],
        "hi": [
            {"step": 1, "who": "तुरंत 1930 पर कॉल करें",
             "detail": "यह वित्तीय साइबर धोखाधड़ी की राष्ट्रीय हेल्पलाइन है। सबसे पहले यही करें।",
             "days": "तुरंत करें, भले ही आपको पूरा यक्कीन न हो।",
             "url": "https://cybercrime.gov.in/"},
            {"step": 2, "who": "अपने बैंक या भुगतान सेवा को बताएँ",
             "detail": "लेनदेन रोकने और धोखाधड़ी के रूप में चिह्नित करने को कहें। यही घंटे के भीतर करें।",
             "days": "लिखित संदर्भ संख्या ज़रूर लें।",
             "url": ""},
            {"step": 3, "who": "साइबर अपराध पोर्टल पर रिपोर्ट करें",
             "detail": "राष्ट्रीय पोर्टल पर रिपोर्ट दर्ज करें और पावती संख्या संभाल कर रखें।",
             "days": "1930 की पावती के 24 घंटे के भीतर ऑनलाइन चरण पूरा करें।",
             "url": "https://cybercrime.gov.in/"},
        ],
        "ta": [
            {"step": 1, "who": "உடனே 1930-ஐ அழுத்துங்கள்",
             "detail": "இது நிதி சைபர் மோசடிக்கான தேசிய உதவி எண். முதலில் இதையே செய்யுங்கள்.",
             "days": "உறுதியாக இல்லாவிட்டாலும் உடனே செய்யுங்கள்.",
             "url": "https://cybercrime.gov.in/"},
            {"step": 2, "who": "உங்கள் வங்கிக்கு அல்லது கட்டண சேவைக்குத் தெரிவியுங்கள்",
             "detail": "பரிமாற்றத்தை நிறுத்தவும், மோசடி எனக் குறிக்கவும் அறிவியுங்கள்.",
             "days": "எழுத்துப் பதிவு எண்ணைக் கேளுங்கள்.",
             "url": ""},
            {"step": 3, "who": "சைபர் குற்ற இணையதளத்தில் புகார் அளியுங்கள்",
             "detail": "தேசிய இணையதளத்தில் புகார் பதிவு செய்து உறுதிப்பு எண்ணைக் காப்பிடுங்கள்.",
             "days": "1930 உறுதிப்பிற்குப் பின் 24 மணி நேரத்திற்குள் இணையப் படிநிலை முடிக்கவும்.",
             "url": "https://cybercrime.gov.in/"},
        ],
    },
    "money_stuck": {
        "en": [
            {"step": 1, "who": "Ask the firm in writing for a reason and a date",
             "detail": "Ask for the exact clause or rule that is blocking the closure or withdrawal, and a date by which it will be done.",
             "days": "Keep their written reply.",
             "url": ""},
            {"step": 2, "who": "RBI CMS or the relevant regulator",
             "detail": "File on the RBI portal for banks, SCORES for market entities, Bima Bharosa for insurers.",
             "days": "If there is no reply within 30 days, escalate.",
             "url": "https://cms.rbi.org.in/"},
            {"step": 3, "who": "National Consumer Helpline 1915",
             "detail": "Free helpline for service disputes, before any formal case.",
             "days": "Phone 1915.",
             "url": "https://consumerhelpline.gov.in/"},
        ],
        "hi": [
            {"step": 1, "who": "संस्था से लिखित में कारण और तारीख माँगें",
             "detail": "पूछें कि कौन-सी शर्त या नियम खाता बंद करने या पैसा निकालने में रोक रहा है, और कब तक होगा।",
             "days": "उनका लिखित उत्तर संभाल कर रखें।",
             "url": ""},
            {"step": 2, "who": "आरबीआई सीएमएस या संबंधित नियामक",
             "detail": "बैंकों के लिए आरबीआई पोर्टल, बाजार संस्थाओं के लिए स्कोर्स, बीमा के लिए बीमा भरोसा।",
             "days": "30 दिन में उत्तर न मिले तो आगे बढ़ें।",
             "url": "https://cms.rbi.org.in/"},
            {"step": 3, "who": "राष्ट्रीय उपभोक्ता हेल्पलाइन 1915",
             "detail": "सेवा विवादों के लिए मुफ़्त हेल्पलाइन, औपचारिक केस से पहले।",
             "days": "फ़ोन 1915।",
             "url": "https://consumerhelpline.gov.in/"},
        ],
        "ta": [
            {"step": 1, "who": "அமைப்பிடம் எழுத்தில் காரணமும் தேதியும் கேளுங்கள்",
             "detail": "கணக்கை மூடுவதையோ பணம் பெறுவதையோ எந்தக் கூற்று அல்லது விதி தடுக்கிறது என்றும், எப்போது முடியும் என்றும் கேளுங்கள்.",
             "days": "அவர்களின் எழுத்துப் பதிலைக் காப்பிடுங்கள்.",
             "url": ""},
            {"step": 2, "who": "ஆர்பிஐ CMS அல்லது பொருத்த ஒழுங்குபடுத்தியிடம்",
             "detail": "வங்கிகளுக்கு ஆர்பிஐ இணையதளம், சந்தை அமைப்புகளுக்கு SCORES, காப்பீட்டிற்கு பீமா பாரோசா.",
             "days": "30 நாட்களில் பதில் இல்லை என்றால் மேல்நிலைக்கு செல்லுங்கள்.",
             "url": "https://cms.rbi.org.in/"},
            {"step": 3, "who": "தேசிய நிரபயாக உதவி எண் 1915",
             "detail": "முற்பட்ட நிலை சேவை விவாகங்களுக்கான இலவச உதவி எண்.",
             "days": "தொலைபேசி 1915.",
             "url": "https://consumerhelpline.gov.in/"},
        ],
    },
    "unsure": {
        "en": [
            {"step": 1, "who": "Start with the company that gave you the service",
             "detail": "Every route in India starts with the firm. Write to them and keep the reference number.",
             "days": "Ask for their grievance officer's name and email.",
             "url": ""},
            {"step": 2, "who": "Use the consumer helpline to find the right regulator",
             "detail": "Call 1915 and describe the service. They will forward it to the right body.",
             "days": "Free, and available in Hindi and other languages.",
             "url": "https://consumerhelpline.gov.in/"},
            {"step": 3, "who": "If money was taken by fraud, call 1930",
             "detail": "Financial cyber fraud is the one situation where you call first instead of writing first.",
             "days": "Immediately.",
             "url": "https://cybercrime.gov.in/"},
        ],
        "hi": [
            {"step": 1, "who": "पहले उस कंपनी को जिसने सेवा दी",
             "detail": "भारत में हर रास्ता कंपनी से शुरू होता है। उन्हें लिखें और संदर्भ संख्या रखें।",
             "days": "उनके शिकायत अधिकारी का नाम और ईमेल पूछें।",
             "url": ""},
            {"step": 2, "who": "सही नियामक तक पहुँचने के लिए उपभोक्ता हेल्पलाइन",
             "detail": "1915 पर कॉल करें और सेवा बताएँ। वे सही संस्था तक भेज देंगे।",
             "days": "मुफ़्त, हिंदी सहित अन्य भाषाओं में उपलब्ध।",
             "url": "https://consumerhelpline.gov.in/"},
            {"step": 3, "who": "धोखाधड़ी में पैसा गया हो तो 1930",
             "detail": "वित्तीय साइबर धोखाधड़ी ही वह स्थिति है जहाँ पहले फ़ोन करना होता है।",
             "days": "तुरंत।",
             "url": "https://cybercrime.gov.in/"},
        ],
        "ta": [
            {"step": 1, "who": "சேவை அளித்த நிறுவனத்திடம் முதலில்",
             "detail": "இந்தியாவில் ஒவ்வொரு பாதையும் நிறுவனத்திடமே தொடங்குகிறது. எழுதுங்கள், பதிவு எண்ணைக் காப்பிடுங்கள்.",
             "days": "அவர்களின் குறைதாரு அலுவலரின் பெயர் மற்றும் மின்னஞ்சலைக் கேளுங்கள்.",
             "url": ""},
            {"step": 2, "who": "சரியான ஒழுங்குபடுத்தியிடத்தைக் கண்டறிய நிரபயாக உதவி எண்",
             "detail": "1915-ஐ அழுத்தி சேவையை விவரியுங்கள். அவர்கள் சரியான அமைப்புக்கு அனுப்புவார்கள்.",
             "days": "இலவசம், தமிழ் உள்ளிட்ட பல மொழிகளில் கிடைக்கும்.",
             "url": "https://consumerhelpline.gov.in/"},
            {"step": 3, "who": "மோசடியாகப் பணம் போனால் 1930",
             "detail": "நிதி சைபர் மோசடி என்பதே எழுதுவதற்கு முன்பே அழுத்த வேண்டிய சூழல்.",
             "days": "உடனே.",
             "url": "https://cybercrime.gov.in/"},
        ],
    },
}

# ---------------------------------------------------------------- checklist

KEEP_READY = {
    "en": [
        "A copy or photograph of the agreement, policy or terms you accepted.",
        "Screenshots of every message, call log entry and app screen.",
        "Your bank statement showing the transaction, if money moved.",
        "Every reference number: the firm's ticket, the bank's complaint number, the 1930 acknowledgement.",
        "Dates. Write down when you complained and when they replied.",
    ],
    "hi": [
        "आपने स्वीकार किए समझौते, पॉलिसी या शर्तों की प्रति या फ़ोटो।",
        "हर संदेश, कॉल रिकॉर्ड और ऐप स्क्रीन के स्क्रीनशॉट।",
        "पैसा हिला हो तो बैंक स्टेटमेंट, जिसमें लेनदेन दिखे।",
        "हर संदर्भ संख्या: कंपनी की टिकट संख्या, बैंक की शिकायत संख्या, 1930 की पावती संख्या।",
        "तारीख़ें। लिख लें कि कब शिकायत की और कब उत्तर मिला।",
    ],
    "ta": [
        "நீங்கள் ஏற்றுக்கொண்ட ஒப்பந்தம், காப்பீட்டு அல்லது விதிமுறைகளின் பிரதி அல்லது படம்.",
        "ஒவ்வொரு செய்தி, அழைப்புப் பதிவு மற்றும் செயலி திரையின் திரைப்படங்கள்.",
        "பணம் நகர்ந்திருந்தால், அந்தப் பரிமாற்றம் தெரியும் வங்கிக் கூற்று.",
        "ஒவ்வொரு பதிவு எண்ணும்: நிறுவன டிக்கெட் எண், வங்கி குறைதாரு எண், 1930 உறுதிப்பு எண்.",
        "தேதிகள். எப்போது புகார் அளித்தீர்கள், எப்போது பதில் வந்தது என்று எழுதுங்கள்.",
    ],
}

PRIVACY = {
    "en": "Your answers stay in this browser and are never sent anywhere. "
          "Do not type account numbers, OTPs, passwords or identity documents anywhere on this page. "
          "No genuine bank, broker or regulator will ever ask for your OTP.",
    "hi": "आपके उत्तर इसी ब्राउज़र में रहते हैं और कहीं नहीं भेजे जाते। "
          "इस पेज पर खाता संख्या, ओटीपी, पासवर्ड या पहचान दस्तावेज़ न लिखें। "
          "कोई सच्चा बैंक, ब्रोकर या नियामक आपसे ओटीपी नहीं माँगेगा।",
    "ta": "உங்கள் பதில்கள் இந்த உலாவியிலேயே இருக்கும், எங்கும் அனுப்பப்படாது. "
          "இந்தப் பக்கத்தில் கணக்கு எண், OTP, கடவுச்சொல் அல்லது அடையாள "
          "ஆவணங்களைத் தட்டச்சு செய்யாதீர்கள். உண்மையான வங்கி, தரைக்கையாளர் "
          "அல்லது ஒழுங்குபடுத்தியிடம் உங்கள் OTP-ஐக் கேட்டுப்போதும் இல்லை.",
}

DISCLAIMER = {
    "en": "Guidance only, not legal advice. Sangyan does not submit complaints and does not "
          "contact any organisation for you. Deadlines and eligibility change, so confirm on the "
          "official portal before you rely on any step.",
    "hi": "यह केवल मार्गदर्शन है, कानूनी सलाह नहीं। संग्यान न आपकी ओर से शिकायत दर्ज करता है "
          "और न ही किसी संस्था से संपर्क करता है। समय-सीमा और पात्रता बदलती रहती है, इसलिए किसी भी "
          "चरण पर निर्भर रहने से पहले आधिकारिक पोर्टल पर पुष्टि करें।",
    "ta": "இது வழிகாட்டல் மட்டுமே, சட்ட ஆலோசனை அல்ல. சாங்யன் உங்கள் பதிலாகப் புகார் "
          "அளிப்பதில்லை, எந்த அமைப்பையும் தொடர்புகொள்வதில்லை. காலவரையும் தகுதியும் "
          "மாறுபடுவதால், எந்த படியையும் நம்புவதற்கு முன் அதிகாரப்பூர்வ இணையதளத்தில் "
          "சரிபார்க்கவும்.",
}

DIRECTORY = [
    {"label": "SEBI SCORES", "url": "https://scores.sebi.gov.in/"},
    {"label": "SMART ODR", "url": "https://smartodr.in/"},
    {"label": "RBI CMS", "url": "https://cms.rbi.org.in/"},
    {"label": "Cyber crime portal", "url": "https://cybercrime.gov.in/"},
    {"label": "IRDAI Bima Bharosa", "url": "https://bimabharosa.irdai.gov.in/"},
    {"label": "Insurance Ombudsmen", "url": "https://www.cioins.co.in/"},
    {"label": "National Consumer Helpline", "url": "https://consumerhelpline.gov.in/"},
    {"label": "e-Jagriti (Consumer Commission)", "url": "https://e-jagriti.gov.in/"},
]


def _pick(block: dict, language: str) -> object:
    return block.get(language) or block.get("en")


def all_situations(language: str = "en") -> dict:
    language = language if language in LANGUAGES else "en"
    return {
        "language": language,
        "last_checked": LAST_CHECKED,
        "urgent": _pick(URGENT, language),
        "privacy": _pick(PRIVACY, language),
        "disclaimer": _pick(DISCLAIMER, language),
        "keep_ready": _pick(KEEP_READY, language),
        "directory": DIRECTORY,
        "situations": [
            {"id": key, "label": _pick(value, language)}
            for key, value in SITUATIONS.items()
        ],
    }


def ladder(situation_id: str, language: str = "en") -> dict:
    language = language if language in LANGUAGES else "en"
    steps = LADDERS.get(situation_id)
    return {
        "id": situation_id,
        "language": language,
        "label": _pick(SITUATIONS.get(situation_id, {}), language) if steps else "",
        "steps": steps.get(language) or steps.get("en") or [] if steps else [],
        "disclaimer": _pick(DISCLAIMER, language),
    }


def main() -> None:
    import sys

    language = sys.argv[1] if len(sys.argv) > 1 else "en"
    data = all_situations(language)
    print("URGENT")
    print(data["urgent"])
    print()
    print("PICK YOUR SITUATION")
    for item in data["situations"]:
        print(f"  {item['id']:<18} {item['label']}")
    print()
    for key in ("fraud", "bank_service", "securities"):
        entry = ladder(key, language)
        print("=" * 70)
        print(entry["label"])
        print("=" * 70)
        for step in entry["steps"]:
            print(f"\n  Step {step['step']}: {step['who']}")
            print(f"    {step['detail']}")
            print(f"    Time limit: {step['days']}")
            if step["url"]:
                print(f"    {step['url']}")
    print()
    print("KEEP READY")
    for item in data["keep_ready"]:
        print(f"  - {item}")
    print()
    print(data["disclaimer"])
    print(f"Last checked: {LAST_CHECKED}")


if __name__ == "__main__":
    main()
