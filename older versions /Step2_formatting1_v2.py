#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
INTERMEDIATE SCRIPT 2 — Formatting & Dialogue Pipeline (v2: mojibake pre-pass for â, â¢)

Input: UTF‑8 .txt (output of the first cleanup script)
Output: formatted UTF‑8 .txt + optional JSON log

What this does (in order):
  1) French mojibake fixes (targeted + common map)
  2) Artifact sweep (â€¢, â€ …) + double‑quote normalization / collapse
  3) Reflow paragraphs: join soft line breaks, preserve blank lines, safe dehyphenation
  4) Dialogue paragraphing (Step 1, strengthened):
       - Break between consecutive quoted sentences:   "…." "…."  -> two paragraphs
       - Break before quoted sentence after sentence end:  . "…"   -> paragraph break
       - Break after closing quote (., !, ?) when narration starts:  "…." I …
  5) Merge leftover single newlines (inside paragraphs)
  6) Collapse mid‑sentence paragraph breaks (double newline between non‑terminator and lowercase)
  7) Lone quote line fixer (quote on its own line w/ blank line above & below): 
       - If nearest non‑empty above already ends with ", remove the lone line
       - Else append " to the end of that line

Usage:
  python formatting_pipeline_intermediate2.py IN.txt OUT.txt --log LOG.json
"""

import argparse, json, os, re

# ---------- French & artifacts ----------

MOJI_MAP = {
    # lowercase
    "Ã ":"à","Ã¢":"â","Ã¤":"ä","Ã¦":"æ","Ã§":"ç","Ã©":"é","Ã¨":"è","Ãª":"ê","Ã«":"ë",
    "Ã¯":"ï","Ã®":"î","Ã´":"ô","Ã¶":"ö","Ã¹":"ù","Ãº":"ú","Ã»":"û","Ã¼":"ü","Å“":"œ",
    # uppercase
    "Ã€":"À","Ã‚":"Â","Ã„":"Ä","Ã†":"Æ","Ã‡":"Ç","Ã‰":"É","Ãˆ":"È","ÃŠ":"Ê","Ã‹":"Ë",
    "Ã�":"Í","ÃŽ":"Î","Ã�":"Ï","Ã”":"Ô","Ã–":"Ö","Ã™":"Ù","Ãš":"Ú","Ã›":"Û","Ãœ":"Ü","Å’":"Œ",
    # common stray
    "Â«":"«","Â»":"»","Â·":"·","Â°":"°","Â":""
}
SPECIAL_FR = {
    "d'UrfÃ©":"d'Urfé", "UrfÃ©":"Urfé",
    "SociÃ©tÃ©":"Société", "ASSOCIÃ‰S":"ASSOCIÉS",
    "ChambÃ©ry":"Chambéry"
}
ARTIFACTS = ["â€¢", "â€", "Â¤", "Â¸", "Â·", "Â«", "Â»", "Â"]

QUOTE_VARIANTS = {"“":'"',"”":'"',"„":'"',"‟":'"',"〝":'"',"〞":'"',"«":'"',"»":'"',"‹":'"',"›":'"',"＂":'"',"❝":'"',"❞":'"'}

def french_and_artifacts(text, log):
    counts_spec, counts_map, counts_art = {}, {}, {}
    for bad, good in SPECIAL_FR.items():
        c = text.count(bad)
        if c:
            text = text.replace(bad, good)
            counts_spec[bad] = c
    for bad, good in MOJI_MAP.items():
        c = text.count(bad)
        if c:
            text = text.replace(bad, good)
            counts_map[bad] = c
    for tok in ARTIFACTS:
        c = text.count(tok)
        if c:
            text = text.replace(tok, "")
            counts_art[tok] = c
    # quote normalization
    qvar = 0
    for qv, repl in QUOTE_VARIANTS.items():
        c = text.count(qv)
        if c:
            text = text.replace(qv, repl); qvar += c
    text, dbl_q = re.subn(r'"{2,}', '"', text)
    log["french_fixes"] = {"specific": counts_spec, "mojibake": counts_map}
    log["artifacts_removed"] = counts_art
    log["quotes_normalized"] = {"variants_to_double": qvar, "double_quotes_collapsed": dbl_q}
    return text

# ---------- Reflow (soft joins + dehyphenation) ----------

def safe_dehyphenate(m):
    before = m.group(1); after = m.group(2)
    if after and after[0].isalpha() and after[0].islower():
        return before + after
    return before + "-" + after

def reflow(text, log):
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    PARA = "<<<P>>>"
    text = text.replace("\n\n", PARA)
    # dehyphenate across line breaks
    text = re.sub(r"([A-Za-z])-(?:\n)([A-Za-z])", safe_dehyphenate, text)
    text = text.replace("\u00ad\n", "")
    # join remaining singles
    singles_before = text.count("\n")
    text = text.replace("\n", " ")
    text = text.replace(PARA, "\n\n")
    # tidy spacing
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
    log["reflow"] = {"single_newlines_joined": singles_before}
    return text

# ---------- Dialogue paragraphing (3 rules) ----------

def dialogue_paragraphing(text, log):
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    PARA = "<<<PBRK>>>"
    text = text.replace("\n\n", PARA)

    # Rule A: between consecutive quoted sentences
    pattern_between_any = re.compile(r'(")([^"]*?)(")\s+(")')
    text, n_between_any = pattern_between_any.subn(r'\1\2"\n\n"', text)

    # Rule B: before quoted sentence after sentence end
    pattern_before = re.compile(r'([.!?])\s+(")')
    text, n_before = pattern_before.subn(r'\1\n\n\2', text)

    # Rule C: after closing quote to narration (uppercase start)
    pattern_to_narr = re.compile(r'("([^"]*[.!?])")\s+([A-ZÀ-Ö])')
    text, n_to_narr = pattern_to_narr.subn(r'\1\n\n\3', text)

    text = text.replace(PARA, "\n\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    log["dialogue_paragraphing"] = {
        "between_quotes": n_between_any,
        "before_leading_quote": n_before,
        "after_quote_to_narration": n_to_narr,
    }
    return text

# ---------- Merge residual single newlines ----------

def merge_single_newlines(text, log):
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    PARA = "<<<PBRK>>>"
    text = re.sub(r"\n\s*\n", PARA, text)
    single_before = text.count("\n")
    text = text.replace("\n", " ")
    text = text.replace(PARA, "\n\n")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
    log["single_newlines_merge"] = {"singles_removed": single_before}
    return text

# ---------- Collapse mid‑sentence paragraph breaks ----------

def collapse_mid_sentence_breaks(text, log):
    pattern_mid = re.compile(r'([^\.!\?;:)"\n])\s*\n\n\s*([a-zà-öø-ÿ])')
    text, n = pattern_mid.subn(r'\1 \2', text)
    log["mid_sentence_breaks_collapsed"] = n
    return text

# ---------- Lone quote line fixer ----------

def fix_lone_quote_lines(text, log):
    lines = text.splitlines()
    removed = 0; appended = 0
    i = 1
    while i < len(lines) - 1:
        if lines[i].strip() == '"' and lines[i-1].strip() == "" and lines[i+1].strip() == "":
            # find nearest non-empty line above
            j = i - 2
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            if j >= 0:
                if lines[j].rstrip().endswith('"'):
                    del lines[i]; removed += 1; continue
                else:
                    lines[j] = lines[j] + '"'; del lines[i]; appended += 1; continue
            else:
                del lines[i]; removed += 1; continue
        i += 1
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    log["lone_quote_lines"] = {"removed": removed, "appended_to_above": appended}
    return text

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile", help="Input UTF‑8 text (output from first script)")
    ap.add_argument("outfile", help="Output UTF‑8 text (formatted)")
    ap.add_argument("--log", default=None, help="Optional JSON log")
    args = ap.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        text = f.read()
    # --- Pre-pass for mojibake that escaped earlier maps ---
    # Delete bullet mojibake and convert bare 'â' to a straight quote so dialogue logic sees it
    text = text.replace("â¢", "")
    text = text.replace("â", '"')

    log = {}

    # 1) French & artifacts
    text = french_and_artifacts(text, log)
    # 2) Reflow soft line breaks
    text = reflow(text, log)
    # 3) Dialogue paragraphing (3 rules)
    text = dialogue_paragraphing(text, log)
    # 4) Merge any residual singles
    text = merge_single_newlines(text, log)
    # 5) Collapse mid‑sentence paragraph breaks
    text = collapse_mid_sentence_breaks(text, log)
    # 6) Lone quote fixer
    text = fix_lone_quote_lines(text, log)

    with open(args.outfile, "w", encoding="utf-8") as f:
        f.write(text)

    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    print("Wrote:", args.outfile)
    if args.log:
        print("Log:", args.log)

if __name__ == "__main__":
    main()
