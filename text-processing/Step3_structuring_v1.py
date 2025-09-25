#!/usr/bin/env python3
# Step3_formatting_v1.py — Clean consolidated version
# Pass 0: promote inline CHAPTER markers; enforce exactly two newlines after Roman numerals
# Pass 1: insert page break before CHAPTER (no HR here)
# Pass 2: inside each chapter, find A1/A2 and insert \n\n---\n before A1 (or before preceding quote)
# Notes: CHAPTER and pure Roman numerals are excluded from A1 candidacy

import sys, re
from typing import List, Tuple

ROMAN_RE = r"[IVXLCDM]+"
CHAPTER_PAT = re.compile(rf"(?m)^(CHAPTER)\s+({ROMAN_RE})\b")
HR = "---"
PAGE_BREAK = "\f"
A1_RE = re.compile(r"\b[A-Z]{2,}\b")
OPEN_QUOTES = "\"“”"
WINDOW_CHARS_AFTER_A1 = 60
SEARCH_MARGIN_AROUND_A1 = 10
SINGLE_LETTER_A = re.compile(r"\b[IA]\b")

def _is_pure_roman(tok: str) -> bool:
    return bool(re.fullmatch(r"[IVXLCDM]+", tok))

def _is_disallowed_a1(tok: str) -> bool:
    return tok == "CHAPTER" or _is_pure_roman(tok)

# ---- Pass 0
def pass_normalize_inline_chapter_markers(text: str):
    # (a) Promote inline CHAPTER <ROMAN> with two newlines before
    promote_pat = re.compile(r'(?m)(?<!^)(?<!\n)(CHAPTER\s+(?:[IVXLCDM]+)\b)')
    text, n_promote = promote_pat.subn(r'\n\n\1', text)

    # (b) Enforce exactly two newlines after Roman numeral on every CHAPTER line
    def _split_after_roman(m):
        head = m.group(1)
        rest = m.group(2).rstrip()
        return f"{head}\n\n{rest}" if rest else f"{head}\n\n"
    after_pat = re.compile(r'(?m)^(CHAPTER\s+[IVXLCDM]+)\b[ \t]*(.*)$')
    text, n_after = after_pat.subn(_split_after_roman, text)

    return text, {"inline_chapter_promoted": n_promote, "newline_after_roman_normalized": n_after}

# ---- Pass 1
def pass_insert_pagebreak_and_hr(text: str):
    out = []
    last_idx = 0
    total_pagebreaks = 0
    for m in CHAPTER_PAT.finditer(text):
        out.append(text[last_idx:m.start()])
        out.append(PAGE_BREAK + "\n")
        total_pagebreaks += 1
        line_end = text.find("\n", m.end())
        if line_end == -1: line_end = len(text)
        chapter_line = text[m.start():line_end]
        out.append(chapter_line)
        last_idx = line_end
    out.append(text[last_idx:])
    return "".join(out), {"pagebreaks": total_pagebreaks, "hr_after_heading": 0}

# Utilities
def find_chapter_spans(text: str) -> List[Tuple[int,int,re.Match]]:
    matches = list(CHAPTER_PAT.finditer(text))
    spans = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        spans.append((start, end, m))
    return spans

def _choose_insertion_index_for_A1(block: str, a1_start: int) -> int:
    i = a1_start
    if i > 1 and block[i-1] == " " and block[i-2] in OPEN_QUOTES: return i-2
    if i > 0 and block[i-1] in OPEN_QUOTES: return i-1
    return i

def _detect_A2(block: str, a1_match: re.Match):
    a1_end = a1_match.end()
    win = block[a1_end:a1_end+WINDOW_CHARS_AFTER_A1]
    m2 = A1_RE.search(win)
    if m2: return True, False
    left = max(0, a1_match.start() - SEARCH_MARGIN_AROUND_A1)
    right = min(len(block), a1_end + SEARCH_MARGIN_AROUND_A1)
    around = block[left:right]
    if SINGLE_LETTER_A.search(around): return True, True
    return False, False

# ---- Pass 2
def pass_break_before_first_allcaps_in_chapter(text: str, debug_log: bool = True):
    spans = find_chapter_spans(text)
    inserts_done = 0
    a2_found = 0
    used_single_letter = 0
    quote_inclusion = 0
    logs = []

    pieces = []
    last_idx = 0

    for (start, end, m) in spans:
        pieces.append(text[last_idx:start])
        block = text[start:end]

        # start A1 scan at end of CHAPTER <ROMAN> match
        search_from = (m.end() - start)
        a1 = None
        for m_a1 in A1_RE.finditer(block, search_from):
            tok = m_a1.group(0)
            if not _is_disallowed_a1(tok):
                a1 = m_a1
                break

        if a1:
            # capture logging
            a1_text = block[a1.start():a1.end()]
            ctx_start = max(0, a1.start()-40)
            ctx_end = min(len(block), a1.end()+80)
            ctx = block[ctx_start:ctx_end].replace("\n","⏎")

            # A2 logic (direct window + fallback)
            win = block[a1.end():a1.end()+WINDOW_CHARS_AFTER_A1]
            m2 = A1_RE.search(win)
            a2_text = m2.group(0) if m2 else None
            has_a2, used_single = _detect_A2(block, a1)
            if has_a2:
                a2_found += 1
                if used_single: used_single_letter += 1

            ins_idx_in_block = _choose_insertion_index_for_A1(block, a1.start())
            if ins_idx_in_block < a1.start(): quote_inclusion += 1

            before = block[:ins_idx_in_block]
            after = block[ins_idx_in_block:]
            block = before + "\n\n" + HR + "\n" + after
            inserts_done += 1

            if debug_log:
                chap_line_end = block.find("\n")
                chap_line = block[:chap_line_end if chap_line_end!=-1 else len(block)]
                logs.append({
                    "chapter_heading": chap_line.strip(),
                    "A1": a1_text,
                    "A2_direct": a2_text,
                    "A2_found_any": has_a2,
                    "A2_via_single_letter": used_single,
                    "A1_context": ctx
                })

        pieces.append(block)
        last_idx = end

    pieces.append(text[last_idx:])
    new_text = "".join(pieces)
    return new_text, {
        "chapters_processed": len(spans),
        "insertions_before_A1": inserts_done,
        "A2_detected_total": a2_found,
        "A2_via_single_letter": used_single_letter,
        "inserted_before_quote": quote_inclusion,
        "logs": logs,
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: python Step3_formatting_v1.py <input.txt> <output.txt>")
        sys.exit(1)
    inp, outp = sys.argv[1], sys.argv[2]
    with open(inp, "r", encoding="utf-8") as f:
        txt = f.read()

    # Pass 0
    txt, log0 = pass_normalize_inline_chapter_markers(txt)
    # Pass 1
    txt, log1 = pass_insert_pagebreak_and_hr(txt)
    # Pass 2
    txt, log2 = pass_break_before_first_allcaps_in_chapter(txt, debug_log=True)

    with open(outp, "w", encoding="utf-8") as f:
        f.write(txt)

    print("[Step3] Inline CHAPTER→block promotions:", log0["inline_chapter_promoted"])
    print("[Step3] Normalized double newline after Roman:", log0["newline_after_roman_normalized"])
    print("[Step3] Chapters found:", log2["chapters_processed"])
    print("[Step3] Page breaks inserted (before CHAPTER):", log1["pagebreaks"])
    print("[Step3] HR inserted after CHAPTER heading lines:", log1["hr_after_heading"], "(none; HR added before A1 in Pass 2)")
    print("[Step3] Insertions before A1:", log2["insertions_before_A1"])
    print("[Step3] A2 detected (any method):", log2["A2_detected_total"])
    print("[Step3] A2 via single-letter fallback (I/A):", log2["A2_via_single_letter"])
    print("[Step3] Inserted before preceding quote:", log2["inserted_before_quote"])
    for i, rec in enumerate(log2.get("logs", []), 1):
        print(f"[Step3][Chapter {i}] {rec['chapter_heading']}")
        print(f"  A1: {rec['A1']}; A2_direct: {rec['A2_direct']} | A2_found_any={rec['A2_found_any']}, via_single={rec['A2_via_single_letter']}")
        print(f"  ctx: …{rec['A1_context']}…")

if __name__ == "__main__":
    main()
