#!/usr/bin/env python3
"""
Step 3 (refactored): Split chapters at ALLCAPS opener words and normalize CHAPTER headers.

Usage:
    python step3_formating2_argparse.py INPUT.txt OUTPUT.txt --log step3_log.json
"""

import re, json, argparse
from pathlib import Path

ROMAN = r"(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX|XXI|XXII|XXIII|XXIV|XXV|XXVI|XXVII|XXVIII|XXIX|XXX|XXXI|XXXII|XXXIII|XXXIV|XXXV|XXXVI|XXXVII|XXXVIII|XXXIX|XL|XLI|XLII|XLIII|XLIV|XLV|XLVI|XLVII|XLVIII|XLIX|L)"
chap_pat = re.compile(rf"CHAPTER\s+({ROMAN})\b")
word_re = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")

def upper_kind(w: str):
    if w == "I":
        return "I"
    if len(w) >= 2 and w.isupper():
        return "STRONG"
    return ""

def process(text: str):
    out_parts = []
    chap_logs = []
    pos = 0

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
        words = word_re.findall(chunk)
        segs = []
        for w in words:
            kind = upper_kind(w)
            if kind:
                segs.append((w, kind))
        chap_logs.append({"chapter": roman, "words": segs})
        out_parts.append(chunk)
        pos = b

    if not matches:
        out_parts.append(text)

    return "".join(out_parts), chap_logs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile", help="Input UTF-8 text (output from Step2)")
    ap.add_argument("outfile", help="Output UTF-8 text (Step3 result)")
    ap.add_argument("--log", default=None, help="Optional JSON log of uppercase words")
    args = ap.parse_args()

    text = Path(args.infile).read_text(encoding="utf-8").replace("\r\n","\n").replace("\r","\n")
    out_text, chap_logs = process(text)

    Path(args.outfile).write_text(out_text, encoding="utf-8")
    if args.log:
        Path(args.log).write_text(json.dumps(chap_logs, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
