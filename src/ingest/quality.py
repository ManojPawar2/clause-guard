"""Graded Marathi extraction-quality score for GR PDFs.

Maharashtra GR PDFs use many legacy Devanagari fonts with broken ToUnicode
CMaps: text extracts, but with font-specific glyph corruption (e.g.
`निर्णय`→`दनणचय`). Corruption severity varies per document from ~0% to ~60%.

Metric: fraction of the document's Devanagari tokens that appear in a list of
very common correct Marathi words/stems. Clean documents score ~0.25-0.45;
heavily garbled ones score <0.08 (their corrupted tokens match nothing).
"""
import re

# ~150 ultra-common correct Marathi words/stems seen in virtually every GR.
COMMON = set("""
शासन निर्णय दिनांक क्रमांक विभाग महाराष्ट्र मंत्रालय मुंबई प्रस्तावना संदर्भ
वाचा आदेश मान्यता मंजूर मंजुरी योजना योजनेच्या योजनेअंतर्गत अंतर्गत अनुदान
निधी रक्कम रुपये कोटी लाख हजार वर्ष वर्षात वर्षासाठी आर्थिक वित्तीय
प्रशासकीय अधिकारी कार्यालय संचालक आयुक्त सचिव प्रधान अवर उप सह कक्ष
शाळा विद्यार्थी विद्यार्थ्यांना शिष्यवृत्ती शिक्षण महाविद्यालय विद्यापीठ
तंत्र उच्च शालेय क्रीडा सामाजिक न्याय विशेष सहाय्य आदिवासी विकास
ग्राम नगर जिल्हा तालुका राज्य केंद्र स्थानिक ठिकाणी येथे येथील
अटी शर्ती नियम अधिनियम कलम तरतूद तरतुदी अंमलबजावणी कार्यवाही
प्रकरणी बाबत बाबतीत संदर्भात अनुषंगाने नुसार प्रमाणे खालील पुढील
सर्व एकूण प्रत्येक तसेच आणि किंवा परंतु मात्र यथास्थिती
आहे आहेत होते होती करण्यात येत असून असलेल्या केली केला केले
देण्यात घेण्यात ठेवण्यात राहील राहतील पाहिजे आवश्यक अर्ज
समिती अध्यक्ष सदस्य बैठक अहवाल शिफारस प्रस्ताव सादर
पात्र लाभार्थी उत्पन्न मर्यादा प्रमाणपत्र कागदपत्रे तपासणी
सुधारित अधिक्रमित रद्द लागू अंमलात संमती सहमती अभिप्राय
राज्यपाल आदेशानुसार नावाने स्वाक्षरीत सोबत जोडली परिशिष्ट
अर्थसंकल्प लेखाशीर्ष खर्च खर्चासाठी वितरण वितरित प्रतिपूर्ती
""".split())

DEV_WORD = re.compile(r"[ऀ-ॿ]{2,}")


def readability(text: str) -> dict:
    words = DEV_WORD.findall(text)
    if len(words) < 30:
        return {"score": 0.0, "n_words": len(words), "verdict": "too-short"}
    hits = sum(1 for w in words if w in COMMON)
    score = hits / len(words)
    verdict = "clean" if score >= 0.16 else ("usable" if score >= 0.10 else "garbled")
    return {"score": round(score, 4), "n_words": len(words), "verdict": verdict}
