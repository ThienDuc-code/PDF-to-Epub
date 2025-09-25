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

# === v13 Reconstruction: comprehensive formatting/cleanup passes ===
import os
import re

def _parse_money_terms(args_env: str | None) -> set[str]:
    if args_env:
        return {t.strip().lower() for t in args_env.split(",") if t.strip()}
    return {
        "ducat","ducats","louis","louis-dor","louis d’or","zecchini","zecchino","zecchins","pistole","pistoles",
        "crown","crowns","guinea","guineas","florin","florins","livre","livres","franc","francs","dollar","dollars",
        "pound","pounds","sequins","sequin","escudo","escudos","peso","pesos","real","reals","reales","maravedi","maravedis",
        "écu","écus","taler","talers","thaler","thalers","sou","sous"
    }

def collapse_double_doublequotes(text, log):
    new_text, n = re.subn(r'""','"', text)
    log["double_doublequotes_collapsed"] = log.get("double_doublequotes_collapsed",0)+n
    return new_text

def normalize_comma_quote_spacing(text, log):
    # , " -> ," (keep single space after quote)
    new_text, n = re.subn(r',\s+"\s', '," ', text)
    log["comma_space_quote_space_normalized"] = n
    return new_text

def remove_superscripts(text, log):
    pattern = re.compile(r'[\u00B9\u00B2\u00B3\u2070-\u2079]')
    new_text, n = pattern.subn("", text)
    log["superscripts_removed"] = n
    return new_text

def strip_footnote_numbers(text, log, money_terms: set[str]):
    examples = {"standalone": [], "after_punct": [], "glued_to_word": []}
    counts = {"standalone": 0, "after_punct": 0, "glued_to_word": 0}

    money_alt = "|".join(sorted(map(re.escape, money_terms), key=len, reverse=True))
    money_follow = re.compile(rf'^\s*(?:{money_alt})\b', re.IGNORECASE)

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        def repl_standalone(m):
            num = m.group(2)
            trail = m.group(3) or ""
            # ordinals
            if re.match(r'^\d{1,3}(st|nd|rd|th)$', num, re.IGNORECASE):
                return m.group(1)+num+trail
            rest = line[m.end():]
            if money_follow.search(rest):
                return m.group(1)+num+trail
            counts["standalone"] += 1
            if len(examples["standalone"])<10:
                examples["standalone"].append((line[max(0,m.start()-40): m.end()+40]).replace("\n","⏎"))
            return m.group(1)+trail

        line = re.sub(r'(^|[\s,;:—\-\)\(\[\]“”"\'\u00A0])(\d{1,3})(?=($|[\s,;:—\-\)\(\]\[“”"\'\.,!?]))', repl_standalone, line)

        def repl_after_punct(m):
            num = m.group(1)
            rest = line[m.end():]
            if money_follow.search(rest):
                return m.group(0)
            counts["after_punct"] += 1
            if len(examples["after_punct"])<10:
                examples["after_punct"].append((line[max(0,m.start()-40): m.end()+40]).replace("\n","⏎"))
            return m.group(0).replace(num,"")
        line = re.sub(r'[,:;]\s?(\d{1,3})(?=($|[^\w]))', repl_after_punct, line)

        def repl_glued(m):
            num = m.group(1)
            counts["glued_to_word"] += 1
            if len(examples["glued_to_word"])<10:
                examples["glued_to_word"].append((line[max(0,m.start()-40): m.end()+40]).replace("\n","⏎"))
            return m.group(0).replace(num,"")
        line = re.sub(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ]|\.)(\d{1,3})(?=($|[^\w]))', repl_glued, line)

        lines[idx] = line

    new_text = "\n".join(lines)
    log["footnote_numbers_removed"] = counts
    for k,v in examples.items():
        if v:
            log[f"footnote_examples_{k}"] = v
    return new_text

def normalize_intraline_spaces(text, log):
    total=0
    def repl_line(line):
        nonlocal total
        line=line.replace("\t"," ")
        new_line, n = re.subn(r'(?<=\S) {2,}(?=\S)', ' ', line)
        total += n
        return new_line
    lines = [repl_line(ln) for ln in text.splitlines()]
    log["intraline_space_runs_normalized"]=total
    return "\n".join(lines)

def remove_quote_island_blocks(text, log):
    # Replace empty-line, quote-only line (or ""/curly), empty-line with single empty line
    lines = text.splitlines()
    out=[]
    i=0
    removed=0
    def is_empty(s): return s.strip()==""
    def is_lone_quote(s):
        t=s.strip()
        return t in {'"', '""', '“','”'}
    while i<len(lines):
        if i+2<len(lines) and is_empty(lines[i]) and is_lone_quote(lines[i+1]) and is_empty(lines[i+2]):
            if not out or out[-1].strip()!="":
                out.append("")
            removed+=1
            i+=3
            while i<len(lines) and is_empty(lines[i]):
                i+=1
            continue
        out.append(lines[i]); i+=1
    log["quote_island_blocks_removed"]=removed
    return "\n".join(out)

def normalize_double_single_quotes(text, log):
    new_text, n = re.subn(r"''", '"', text)
    log["double_single_to_doublequote"]=n
    return new_text

def fix_quote_apostrophe_artifacts(text, log):
    lines = text.splitlines()
    moves_up=0; moves_down=0; collapses=0; inline_moves=0
    # Inline: ... [.!?]' " -> ..." + new paragraph + "
    pattern_inline = re.compile(r'([\.!\?])(?:\'|’)\s+"')
    for i,s in enumerate(lines):
        new_s, n = pattern_inline.subn(r'\1"\n\n"', s)
        if n: lines[i]=new_s; inline_moves+=n

    # Line start: " ' or "' -> move up if prior line opened quote and is unbalanced
    pattern_line_start = re.compile(r'^\s*" ?(?:\'|’)')
    def line_balanced(q): return (q.count('"')%2)==0
    for i,s in enumerate(lines):
        if not pattern_line_start.match(s): continue
        # find prev non-empty
        j=i-1
        while j>=0 and lines[j].strip()=="": j-=1
        if j is not None and j>=0:
            prev=lines[j]
            if prev.lstrip().startswith('"') and not line_balanced(prev):
                if re.search(r'[\.!\?]\'\s*$', prev):
                    lines[j]=re.sub(r'([\.!\?])\'\s*$', r'\1"', prev)
                else:
                    lines[j]=prev.rstrip()+'"'
                lines[i]=re.sub(r'^\s*" ?(?:\'|’)\s*', '', lines[i], count=1)
                moves_up+=1
                continue
        lines[i]=re.sub(r'^\s*" ?(?:\'|’)', '"', lines[i], count=1); collapses+=1

    # Line end: ' " -> move down if next doesn't start with quote
    pattern_line_end = re.compile(r'(?:\'|’)\s*"$')
    for i,s in enumerate(lines):
        if not pattern_line_end.search(s.strip()): continue
        # next non-empty
        j=i+1
        while j<len(lines) and lines[j].strip()=="": j+=1
        if j<len(lines) and not lines[j].lstrip().startswith('"'):
            lines[i]=re.sub(r'(?:\'|’)\s*"$', '"', s.strip())
            lines[j]='"'+lines[j].lstrip()
            moves_down+=1

    # Final sweep: any remaining " ' or "' -> "
    pattern_inline_collapse = re.compile(r'" ?(?:\'|’)')
    for i,s in enumerate(lines):
        new_s, n = pattern_inline_collapse.subn('"', s)
        if n: lines[i]=new_s; collapses+=n

    log["quote_artifacts_inline_moves"]=inline_moves
    log["quote_artifacts_moved_up"]=moves_up
    log["quote_artifacts_moved_down"]=moves_down
    log["quote_artifacts_collapsed"]=collapses
    return "\n".join(lines)



def collapse_double_quotes_with_space(text: str, log: dict) -> str:
    """
    Collapse wrong double quotes separated by a space into a single quote.
    Examples:
      "  "   -> "
      ”  “   -> “   (keep the *second* quote so curly shape is preserved)
    Handles regular spaces, tabs, and NBSP.
    """
    # Capture closing-or-straight then whitespace then opening-or-straight; keep the 2nd quote char
    pattern = re.compile(r'(”|")([\u00A0 \t]+)("|“)')
    new_text, n = pattern.subn(lambda m: m.group(3), text)
    if n:
        log["double_quotes_with_space_collapsed"] = n
    else:
        log.setdefault("double_quotes_with_space_collapsed", 0)
    return new_text



def split_adjacent_quotes_to_newline(text: str, log: dict) -> str:
    """
    If a closing quote is followed by a space and a new opening quote, split to a new paragraph.
    Examples:
      Now:  "…right." "You may be sure…"
      Out:  "…right."
            
            "You may be sure…"
    Handles straight (") and curly (“ ”) quotes. Keeps punctuation before the closing quote.
    We only split when the second quote is likely an opening of a sentence (next char is a letter or opening quote).
    """
    # Patterns for closing-then-opening with a single space in between
    # Allow any closing char before the quote (.,!?;: or none), then space, then an opening quote and a letter/quote.
    pattern = re.compile(r'(”|")(\s+)("|“)(?=[A-Za-zÀ-ÖØ-öø-ÿ“])')
    count = 0
    def repl(m):
        nonlocal count
        count += 1
        # m.group(1) is the closing quote, we keep it; replace the space + next opening quote with newline+newline + that opening quote
        return f'{m.group(1)}\n\n{m.group(3)}'
    new_text = pattern.sub(repl, text)
    log["adjacent_quotes_split"] = count
    return new_text




def fix_leading_stray_quote_before_narrative(text: str, log: dict) -> str:
    """
    Move a stray leading quote + space (on the next line) UP to close the sentence above.
    """
    lines = text.splitlines()
    n = len(lines)
    patt = re.compile(r'^\s*(["“])\s+([A-ZÀ-ÖØ-Ý].*)$')
    moved = 0
    def prev_nonempty(i):
        p = i - 1
        while p >= 0 and lines[p].strip() == "":
            p -= 1
        return p
    for i in range(n):
        m = patt.match(lines[i])
        if not m:
            continue
        p = prev_nonempty(i)
        if p >= 0:
            closing = '”' if lines[p].lstrip().startswith('“') else '"'
            if not lines[p].rstrip().endswith(('”','"')):
                lines[p] = lines[p].rstrip() + closing
            lines[i] = m.group(2)
            moved += 1
    log['leading_stray_quote_before_narrative_moved'] = moved
    return "\n".join(lines)

def fix_leading_quote_space_opening_quote(text: str, log: dict) -> str:
    """
    Fix lines that begin with a stray quote + space before an actual opening quote, e.g.:
        Prev:  "... didn't look his age.
        Curr:  " "Where did I see him?"
    Becomes:
        Prev:  "... didn't look his age."
        Curr:  "Where did I see him?"
    If the previous non-empty line doesn't already end with a closing quote, we append one.
    """
    lines = text.splitlines()
    n = len(lines)
    pattern = re.compile(r'^\s*"\s+([“"])(.*)$')  # capture the real opening quote and the remainder
    fixed = 0

    def find_prev_nonempty(i):
        p = i - 1
        while p >= 0 and lines[p].strip() == "":
            p -= 1
        return p

    for i in range(n):
        m = pattern.match(lines[i])
        if not m:
            continue
        prev = find_prev_nonempty(i)
        if prev >= 0:
            # If prev doesn't end with a closing quote, append one (curly if prev seems to start with curly)
            closing = '”' if lines[prev].lstrip().startswith('“') else '"'
            if not lines[prev].rstrip().endswith(('”','"')):
                lines[prev] = lines[prev].rstrip() + closing
            # Replace current line by removing the stray leading quote + space
            real_open = m.group(1)
            rest = m.group(2)
            lines[i] = real_open + rest
            fixed += 1

    if fixed:
        log["leading_quote_space_fixed"] = fixed
    return "\n".join(lines)



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


def split_adjacent_dialogue_turns(text: str, log: dict) -> str:
    """
    Insert a paragraph break between two adjacent quoted sentences when they are from (likely) different speakers.
    Heuristic:
      - If we see   [.!?]"  <spaces>  "Capital ...   we split into two paragraphs.
      - We DO NOT touch cases where a reporting clause immediately follows a quote, e.g.:
            "…," he said, "…"
        because those don't have a closing quote + immediate opening quote with space only between; there is text.
    """
    pattern = re.compile(r'([.!?]")\s+(")([A-Z])')
    count = 0
    def repl(m):
        nonlocal count
        count += 1
        return m.group(1) + "\n\n" + m.group(2) + m.group(3)
    new_text = pattern.sub(repl, text)
    log.setdefault("dialogue_splits_new_speaker", 0)
    log["dialogue_splits_new_speaker"] += count
    return new_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile", help="Input UTF‑8 text (output from first script)")
    ap.add_argument("outfile", help="Output UTF‑8 text (formatted)")
    ap.add_argument("--money-terms", default=os.environ.get("STEP2_MONEY_TERMS",""), help="Comma-separated money unit terms to preserve (optional).")
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

    text = fix_leading_quote_space_opening_quote(text, log)
    text = fix_leading_stray_quote_before_narrative(text, log)
    text = split_adjacent_quotes_to_newline(text, log)
    text = collapse_double_quotes_with_space(text, log)
    money_terms = _parse_money_terms(getattr(args, "money_terms", ""))
    text = normalize_double_single_quotes(text, log)
    text = remove_superscripts(text, log)
    text = strip_footnote_numbers(text, log, money_terms)
    text = fix_quote_apostrophe_artifacts(text, log)
    text = normalize_comma_quote_spacing(text, log)
    text = remove_quote_island_blocks(text, log)
    text = split_adjacent_dialogue_turns(text, log)
    text = normalize_intraline_spaces(text, log)
    text = collapse_double_doublequotes(text, log)
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
