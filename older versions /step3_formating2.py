#!/usr/bin/env python3
"""
Step 3: Split chapters at ALLCAPS opener words and normalize CHAPTER headers.

Input:  step2_formatted_md_ready.txt
Output: step3_split_at_caps.txt, step3_split_at_caps_log.json
"""

import re, json
from pathlib import Path

src = Path("vol7_step2_formatted_md_ready.txt")
text = src.read_text(encoding="utf-8").replace("\r\n","\n").replace("\r","\n")

ROMAN = r"(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX|XXI|XXII|XXIII|XXIV|XXV|XXVI|XXVII|XXVIII|XXIX|XXX|XXXI|XXXII|XXXIII|XXXIV|XXXV|XXXVI|XXXVII|XXXVIII|XXXIX|XL|XLI|XLII|XLIII|XLIV|XLV|XLVI|XLVII|XLVIII|XLIX|L)"
chap_pat = re.compile(rf"CHAPTER\s+({ROMAN})\b")
word_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")

def upper_kind(w: str):
    if w == "I":
        return "I"
    if len(w) >= 2 and w.isupper():
        return "STRONG"
    return ""

out_parts = []
pos = 0
chap_logs = []

matches = list(chap_pat.finditer(text))
for i, m in enumerate(matches):
    roman = m.group(1)
    pre = text[pos:m.start()]
    pre = pre.rstrip() + "\n\n"
    out_parts.append(pre)

    out_parts.append(f"CHAPTER {roman}\n\n")

    a = m.end()
    b = matches[i+1].start() if i+1 < len(matches) else len(text)
    chunk = text[a:b]

    tokens = [(mt.group(0), mt.start()) for mt in word_re.finditer(chunk)]
    chosen = None
    for k in range(len(tokens)-1):
        w1, p1 = tokens[k]
        w2, p2 = tokens[k+1]
        if upper_kind(w1) == "STRONG" and upper_kind(w2) == "STRONG":
            chosen = (w1, w2, p1, p2, "strong_pair"); break
    if not chosen:
        for k in range(len(tokens)-1):
            k1 = upper_kind(tokens[k][0])
            k2 = upper_kind(tokens[k+1][0])
            if (k1 in {"STRONG","I"}) and (k2 in {"STRONG","I"}) and not (tokens[k][0]=="I" and tokens[k+1][0]=="I"):
                w1, p1 = tokens[k]
                w2, p2 = tokens[k+1]
                chosen = (w1, w2, p1, p2, "fallback_allow_I"); break

    if chosen:
        w1, w2, p1, p2, mode = chosen
        summary = chunk[:p1].strip()
        body = chunk[p1:].lstrip()
        if summary:
            out_parts.append(summary + "\n\n")
        out_parts.append(body.strip())
        chap_logs.append({
            "chapter": roman,
            "pair": [w1, w2],
            "mode": mode,
            "summary_preview": summary[:120],
            "body_preview": body[:120]
        })
    else:
        out_parts.append(chunk.strip())
        chap_logs.append({
            "chapter": roman,
            "pair": [],
            "mode": "not_found",
            "summary_preview": "",
            "body_preview": chunk[:120]
        })

    out_parts.append("\n\n")
    pos = b

out_parts.append(text[pos:])

rebuilt = "".join(out_parts)

Path("step3_split_at_caps.txt").write_text(rebuilt, encoding="utf-8")
Path("step3_split_at_caps_log.json").write_text(json.dumps(chap_logs, indent=2), encoding="utf-8")

print("Step 3 complete.")
print("Output: step3_split_at_caps.txt, step3_split_at_caps_log.json")
