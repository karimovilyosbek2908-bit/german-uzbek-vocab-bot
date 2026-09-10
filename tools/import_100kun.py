"""'100 kun qoidasi.pdf' -> data/words.json (v2).

- separator: ' – ', ' - ', bo'sh joysiz '–' ham
- kirill o'zbekcha -> lotin
- kunlik dialoglar -> o'sha kun birinchi so'ziga example sifatida
"""
import json
import re
from pypdf import PdfReader

import os
import sys

# Foydalanish:  python tools/import_100kun.py "<100 kun qoidasi.pdf yo'li>"
_HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "..", "data", "100 kun qoidasi.pdf")
OUT = os.path.join(_HERE, "..", "data", "words.json")

reader = PdfReader(SRC)
text = "\n".join(p.extract_text() for p in reader.pages)
lines = [l.rstrip() for l in text.split("\n")]

APO = {"’": "'", "‘": "'", "ʻ": "'", "ʼ": "'", "`": "'", "´": "'"}
def fix_apo(s):
    for k, v in APO.items():
        s = s.replace(k, v)
    return s

CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g'", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ў": "o'",
    "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ј": "j",
}
def translit(s):
    if not any("Ѐ" <= c <= "ӿ" for c in s):
        return s
    out = []
    for ch in s:
        low = ch.lower()
        if low in CYR2LAT:
            rep = CYR2LAT[low]
            out.append(rep.upper() if ch.isupper() and rep else rep)
        else:
            out.append(ch)
    return "".join(out)

DAY_RE = re.compile(r"^\s*(\d{1,3})\s*[-–—]\s*kun\s*$", re.I)
ENTRY_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.*\S)\s*$")
SEP_RE = re.compile(r"\s+[–—-]\s+|\s*[–—]\s*")
QUOTE_CHARS = set("„“”‟\"«»")
PAIR_RE = re.compile(r"[„“]([^“”„]+)[“”]")

entries = []
phrases = {}     # day -> [(de, uz)]
day = 0
cur = None
phrase_buf = []

def flush_phrases():
    global phrase_buf
    if not phrase_buf or not day:
        phrase_buf = []
        return
    joined = " ".join(phrase_buf)
    quoted = PAIR_RE.findall(joined)
    quoted = [fix_apo(q.strip()) for q in quoted if q.strip()]
    pairs = []
    for i in range(0, len(quoted) - 1, 2):
        de, uz = quoted[i], translit(quoted[i + 1])
        if de and uz:
            pairs.append((de, uz))
    if pairs:
        phrases.setdefault(day, []).extend(pairs)
    phrase_buf = []

for ln in lines:
    st = ln.strip()
    m = DAY_RE.match(st)
    if m:
        flush_phrases()
        day = int(m.group(1))
        cur = None
        continue
    m = ENTRY_RE.match(ln)
    if m:
        cur = [day, m.group(2)]
        entries.append(cur)
        continue
    if not st:
        cur = None
        continue
    if QUOTE_CHARS & set(st) or st.startswith("– "):
        phrase_buf.append(st)
        cur = None
        continue
    if cur is not None and not (st[:1].isupper() and len(st.split()) > 4):
        cur[1] += " " + st
flush_phrases()

PRON = {"ich", "du", "er", "sie", "es", "wir", "ihr", "er/sie/es", "man", "ja", "nein"}
def classify(de, uz):
    low = de.lower()
    if re.match(r"^(der|die|das)\s+\S", low):
        return "noun"
    if low in PRON:
        return "pron"
    u = uz.lower()
    if u.endswith(("moq", "moq.", "moq,")) or re.search(r"\bmoq\b", u):
        return "verb"
    if " " not in de and de[:1].isupper():
        return "noun"
    if " " not in de and de.islower():
        return "adj"
    return ""

seen = {}
words = []
skipped = []
day_first_word = {}
for d, raw in entries:
    raw = fix_apo(raw)
    raw = re.sub(r"\[[^\]]*\]", "", raw)
    raw = re.sub(r"\s{2,}", " ", raw).strip(" .;")
    parts = SEP_RE.split(raw, maxsplit=1)
    if len(parts) != 2:
        # zaxira: bo'sh joysiz tire bo'yicha bo'lish
        fb = re.split(r"[–—-]", raw, maxsplit=1)
        if len(fb) == 2 and fb[0].strip() and fb[1].strip():
            parts = fb
        else:
            skipped.append(raw)
            continue
    de, uz = parts[0].strip(" .;,"), parts[1].strip()
    de = re.sub(r"\s*\([^)]*\)\s*", " ", de).strip()
    mpar = re.match(r"^([^()]+?)\s*\(", uz)
    if mpar and mpar.group(1).strip():
        uz = mpar.group(1).strip()
    uz = translit(uz.strip(" .;,–—-"))
    if not de or not uz or len(de) > 70:
        skipped.append(raw)
        continue
    key = de.lower()
    if key in seen:
        continue
    seen[key] = True
    w = {
        "id": len(words) + 1,
        "de": de,
        "uz": uz,
        "pos": classify(de, uz),
        "day": d,
        "example_de": "",
        "example_uz": "",
    }
    words.append(w)
    day_first_word.setdefault(d, w)

# qo'lda tuzatishlar (manba PDF'dagi OCR xatolari)
MANUAL_FIXES = {
    "dшу besamung": {"de": "die Besamung", "pos": "noun"},
}
for w in words:
    fix = MANUAL_FIXES.get(w["de"].lower())
    if fix:
        w.update(fix)

# kunlik dialogni o'sha kun birinchi so'ziga biriktirish
for d, w in day_first_word.items():
    if phrases.get(d):
        de, uz = phrases[d][0]
        w["example_de"] = de
        w["example_uz"] = uz

data = {
    "meta": {
        "language_pair": "de-uz",
        "source": "100 kun qoidasi.pdf",
        "description": "Nemis-o'zbek lug'at, 100 kunlik kursdan ajratib olindi. Kirill yozuvlar lotinga o'girildi.",
        "count": len(words),
        "days": max(w["day"] for w in words),
        "level": "A1-B1",
    },
    "words": words,
}
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"so'zlar        : {len(words)}")
print(f"tashlangan     : {len(skipped)} -> {skipped}")
print(f"kunlar         : {data['meta']['days']}")
print(f"dialogli kun   : {sum(1 for w in words if w['example_de'])}")
pos = {}
for w in words:
    pos[w["pos"]] = pos.get(w["pos"], 0) + 1
print(f"turkum         : {pos}")
print(f"kirill qolgan  : {sum(1 for w in words if any(chr(0x400) <= c <= chr(0x4ff) for c in w['uz']+w['de']))}")
print("\n--- 1..15 ---")
for w in words[:15]:
    ex = f"  |  ex: {w['example_de'][:30]}" if w["example_de"] else ""
    print(f'{w["id"]:>4} d{w["day"]:<3} | {w["de"]:<28} | {w["uz"]:<34} | {w["pos"]:<5}{ex}')
print("\n--- 2000..2012 ---")
for w in words[2000:2012]:
    print(f'{w["id"]:>4} d{w["day"]:<3} | {w["de"]:<28} | {w["uz"]:<34} | {w["pos"]}')
