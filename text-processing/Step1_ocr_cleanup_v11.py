#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, pathlib, re

# ---------- French mojibake fixes (inside words only) ----------
def _apply_french_utf8_latin1_fixes(text: str) -> str:
    mapping = {
        "Ã©": "é", "Ã¨": "è", "Ãª": "ê", "Ã«": "ë",
        "Ã ": "à", "Ã¢": "â", "Ã¤": "ä",
        "Ã¹": "ù", "Ã»": "û", "Ã¼": "ü",
        "Ã®": "î", "Ã¯": "ï",
        "Ã´": "ô", "Ã¶": "ö",
        "Ã‡": "Ç", "Ã§": "ç",
        "Ã‰": "É", "Ãˆ": "È", "ÃŠ": "Ê", "Ã‹": "Ë",
        "Ã€": "À", "Ã‚": "Â", "Ã„": "Ä",
        "Ã™": "Ù", "Ã›": "Û", "Ãœ": "Ü",
        "ÃŽ": "Î", "Ã\u008f": "Ï",
        "Ã”": "Ô", "Ã–": "Ö",
    }
    # Replace only when the artifact is part of a word
    def fix_word(m):
        s = m.group(0)
        for k, v in mapping.items():
            s = s.replace(k, v)
        return s
    return re.sub(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]{2,}", fix_word, text)

# ---------- Preservation rule ----------
def _preserve_allcaps_chapter_and_first_volume_chapter(text: str, original_text: str) -> str:
    chap_line_re = re.compile(r'(?m)^\s*CHAPTER\s+(?:[IVXLCDM]+|[A-Z0-9]+)\s*$')
    m = chap_line_re.search(original_text)
    if m:
        first_chap = m.group(0).strip()
        if not re.search(r'(?m)^\s*' + re.escape(first_chap) + r'\s*$', text):
            lines = text.splitlines()
            i = 0
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            lines[i:i] = ["", first_chap, ""]
            text = "\n".join(lines)

    m_vol = re.search(r'(?m)^\s*Volume\s+\S.*$', original_text)
    if m_vol:
        vol_line = m_vol.group(0).strip()
        if not re.search(r'(?m)^\s*' + re.escape(vol_line) + r'\s*$', text):
            lines = text.splitlines()
            i = 0
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            lines[i:i] = ["", vol_line, ""]
            text = "\n".join(lines)

    return text

# ---------- Integrated header/footer remover ----------

def _find_first_chapter_heading_idx(lines):
    chap_line_ci = re.compile(r'^\s*chapter\s+[ivxlcdm]+[.\u00B9\u00B2\u00B3\u2070-\u2079\u02DA]*\s*$', re.IGNORECASE)
    for i, s in enumerate(lines):
        if chap_line_ci.match(s.strip()):
            return i
    return None

def remove_header_footer_blocks(text: str, log: dict) -> str:
    """
    Remove header/footer blocks centered on lines with 'Volume' or 'History of My Life'.
    Expand across blank lines, bullets, numeric-only (Arabic or Roman), punctuation-only,
    and mixed-case 'Chapter ...' running heads. Never remove all-caps CHAPTER <X> headings.
    """
    lines = text.splitlines()
    n = len(lines)

    protected_chapter_idx = _find_first_chapter_heading_idx(lines)

    vol_re = re.compile(r"(?i)\bvolume\b")
    hist_re = re.compile(r"(?i)\bhistory\s+of\s+my\s+life\b")
    chapter_inline_re = re.compile(r"(?i)\bchapter\b")

    bullet_re = re.compile(r"^\s*[•·]\s*$")
    punct_only_re = re.compile(r'^\s*[\.,;:!?—–\-\"“”„‟’\']+\s*$')
    quote_only_re = re.compile(r'^\s*[\"\'“”„‟’]+\s*$')
    numeric_only_re = re.compile(r"^\s*(?:\d{1,4}|[IVXLCDM]+)\.?\s*$")
    allcaps_chapter_heading_re = re.compile(r"^\s*CHAPTER\s+(?:[IVXLCDM]+|[A-Z0-9]+)\s*$")

    def is_headerish(idx: int) -> bool:
        if protected_chapter_idx is not None and idx == protected_chapter_idx:
            return False
        s = lines[idx].strip()
        if s == "":
            return True
        if bullet_re.match(s) or punct_only_re.match(s) or quote_only_re.match(s):
            return True
        if numeric_only_re.match(s):
            return True
        if vol_re.search(s) or hist_re.search(s):
            return True
        if chapter_inline_re.search(s) and not allcaps_chapter_heading_re.match(s):
            return True
        return False

    def is_body_line(idx: int) -> bool:
        s = lines[idx].strip()
        if s == "":
            return False
        if allcaps_chapter_heading_re.match(s):
            return True
        if re.search(r"[a-zà-öø-ÿ]", s):
            return True
        if re.search(r"[A-Za-z].*[\.!?;:]\s*$", s):
            return True
        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", s)
        return len(words) >= 2

    to_delete = []
    visited = set()

    for i in range(n):
        if i in visited:
            continue
        s = lines[i]
        if vol_re.search(s) or hist_re.search(s):
            lo = i
            while lo - 1 >= 0 and (lo-1 != protected_chapter_idx) and is_headerish(lo - 1) and not allcaps_chapter_heading_re.match(lines[lo-1].strip()):
                lo -= 1
            hi = i
            while hi + 1 < n and (hi+1 != protected_chapter_idx) and is_headerish(hi + 1) and not allcaps_chapter_heading_re.match(lines[hi+1].strip()):
                hi += 1

            # absorb dangling tiny punct/num clusters just outside the block
            def absorb_up(lo0):
                k = lo0 - 1; taken = 0
                while k >= 0 and taken < 3:
                    s = lines[k].strip()
                    if s and (k != protected_chapter_idx) and (numeric_only_re.match(s) or punct_only_re.match(s) or quote_only_re.match(s)):
                        lo0 = k; taken += 1; k -= 1; continue
                    break
                return lo0

            def absorb_down(hi0):
                k = hi0 + 1; taken = 0
                while k < n and taken < 3:
                    s = lines[k].strip()
                    if s and (k != protected_chapter_idx) and (numeric_only_re.match(s) or punct_only_re.match(s) or quote_only_re.match(s)):
                        hi0 = k; taken += 1; k += 1; continue
                    break
                return hi0

            lo = absorb_up(lo); hi = absorb_down(hi)

            lo_ok = (lo == 0) or (lo - 1 >= 0 and is_body_line(lo - 1))
            hi_ok = (hi == n-1) or (hi + 1 < n and is_body_line(hi + 1))

            if protected_chapter_idx is not None and lo <= protected_chapter_idx <= hi:
                # Avoid deleting the real first chapter heading
                if protected_chapter_idx - lo > hi - protected_chapter_idx:
                    lo = protected_chapter_idx + 1
                else:
                    hi = protected_chapter_idx - 1
            if lo <= hi and (lo_ok or hi_ok):
                to_delete.append((lo, hi))
                for k in range(lo, hi + 1):
                    visited.add(k)

    if not to_delete:
        log.setdefault("header_footer_blocks_removed", 0)
        return text

    to_delete.sort()
    merged = []
    cur_lo, cur_hi = to_delete[0]
    for lo, hi in to_delete[1:]:
        if lo <= cur_hi + 1:
            cur_hi = max(cur_hi, hi)
        else:
            merged.append((cur_lo, cur_hi))
            cur_lo, cur_hi = lo, hi
    merged.append((cur_lo, cur_hi))

    delset = set()
    examples = []
    for lo, hi in merged:
        delset.update(range(lo, hi + 1))
        examples.append("\n".join(lines[lo:hi+1])[:200])

    keep = [ln for idx, ln in enumerate(lines) if idx not in delset]
    log["header_footer_blocks_removed"] = len(merged)
    if protected_chapter_idx is not None:
        log["protected_first_chapter_idx"] = protected_chapter_idx
    if examples:
        log["header_footer_examples"] = examples[:5]
    return "\n".join(keep)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    original_text = pathlib.Path(args.infile).read_text(encoding="utf-8", errors="ignore")
    log = {}

    text = original_text
    text = remove_header_footer_blocks(text, log)
    text = _apply_french_utf8_latin1_fixes(text)
    text = _preserve_allcaps_chapter_and_first_volume_chapter(text, original_text)

    pathlib.Path(args.outfile).write_text(text, encoding="utf-8")
    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({
                "status": "ok",
                "infile": args.infile,
                "outfile": args.outfile,
                "length_in": len(original_text),
                "length_out": len(text),
                **log
            }, f, indent=2)

if __name__ == "__main__":
    main()
