#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Step1_ocr_cleanup_v6.py — Integrated single-file version
# - Contains full Step1 v3 logic inline (no subprocess)
# - Adds v6's French mojibake-in-words fixer after v3 cleanup
# - Same CLI: infile outfile [--log JSON] [--rtf]

import argparse, json, re, pathlib, sys

def _apply_french_utf8_latin1_fixes(text: str) -> str:
    """Fix common UTF-8→Latin-1 mojibake only when inside words."""
    mapping = {
        # Lowercase
        "Ã©": "é", "Ã¨": "è", "Ãª": "ê", "Ã«": "ë",
        "Ã ": "à", "Ã¢": "â", "Ã¤": "ä",
        "Ã¬": "ì", "Ã­": "í", "Ã®": "î", "Ã¯": "ï",
        "Ã²": "ò", "Ã³": "ó", "Ã´": "ô", "Ã¶": "ö",
        "Ã¹": "ù", "Ãº": "ú", "Ã»": "û", "Ã¼": "ü",
        "Ã§": "ç",
        # Uppercase
        "Ã‰": "É", "Ãˆ": "È", "ÃŠ": "Ê", "Ã‹": "Ë",
        "Ã€": "À", "Ã‚": "Â", "Ã„": "Ä",
        "ÃŒ": "Ì", "Ã": "Í", "ÃŽ": "Î", "Ã": "Ï",
        "Ã’": "Ò", "Ã“": "Ó", "Ã”": "Ô", "Ã–": "Ö",
        "Ã™": "Ù", "Ãš": "Ú", "Ã›": "Û", "Ãœ": "Ü",
        "Ã‡": "Ç",
    }
    for bad, good in mapping.items():
        pat = re.compile(rf"(?:(?<=\w){re.escape(bad)}|{re.escape(bad)}(?=\w))")
        text = pat.sub(good, text)
    return text

# ======= BEGIN: Inlined Step1 v3 code (verbatim) =======
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, re

def remove_volume_chapter_headers(text: str) -> str:
    """
    Remove header/footer artifacts of the form:
        Volume <word/roman/number> [possibly across newlines/artifacts] Chapter <word/roman/number>
    Works across linebreaks (DOTALL) and is careful not to touch real "CHAPTER X" headings
    that appear on their own lines without a preceding "Volume".
    """
    import re
    pat = re.compile(
        r'''(?ix)             # ignore case, verbose
            Volume
            (?:(?!Chapter).){0,250}?   # up to 250 chars, but don't skip past 'Chapter' (tempered dot)
            Chapter \s+
            (?:[A-Za-z]+ | [IVXLCDM]+ | \d+)
        ''',
        re.DOTALL
    )
    cleaned = pat.sub("", text)
    # Tidy fallout: drop lone bullets / mojibake lines and collapse excessive blanks
    cleaned = re.sub(r"^(?:[•\-\u2022â€¢]+)\s*$", "", cleaned, flags=re.M)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


CURRENCY_WORDS = set("""
louis livre livres ducat ducats florin florins franc francs crown crowns
sequin sequins lira lire scudo scudi guilder guilders ecu ecus écus
pound pounds sterling thaler thalers taler talers paolo paoli soldi sou sous
pistole pistoles doubloon doubloons
""".split())

CURRENCY_SYMBOLS = set(list("£€$₤₣"))
STOPWORDS_TINY = set("a an the of to in on at for per da de di du la le les el il lo un une".split())

def is_year(num_str: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", num_str)) and 1500 <= int(num_str) <= 2099

def next_word_is_currency(text: str, idx_after_number: int) -> bool:
    i = idx_after_number
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i < n and text[i] in CURRENCY_SYMBOLS:
        return True
    m = re.match(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", text[i:])
    if m:
        return m.group(0).lower() in CURRENCY_WORDS
    return False

def rtf_to_text(raw_bytes: bytes) -> str:
    s = raw_bytes.decode("latin-1")
    def _hex(m):
        b = bytes([int(m.group(1),16)]); return b.decode("cp1252","replace")
    s = re.sub(r"\\'([0-9a-fA-F]{2})", _hex, s)
    def _uni(m):
        num = int(m.group(1));  num = num+65536 if num<0 else num
        try: return chr(num)
        except: return ""
    s = re.sub(r"\\u(-?\d+)\??", _uni, s)
    s = s.replace(r"\par","\n").replace(r"\line","\n").replace(r"\tab","    ")
    s = re.sub(r"\\[A-Za-z]+-?\d* ?", "", s)
    s = s.replace("{","").replace("}","")
    s = s.replace("\r\n","\n").replace("\r","\n")
    s = s.replace("\\\n","\n").replace("\n\\","\n")
    return s

def normalize_double_quotes(text: str, log: dict) -> str:
    variants = {
        "“": '"', "”": '"', "„": '"', "‟": '"', "〝": '"', "〞": '"',
        "«": '"', "»": '"', "‹": '"', "›": '"', "＂": '"', "❝": '"', "❞": '"',
        "â€œ": '"', "â€\x9d": '"', "â€\x9c": '"', "Ã¢Â€Âœ": '"', "Ã¢Â€Â�": '"', "Ã¢Â€Âž": '"',
        "Â«": '"', "Â»": '"',
    }
    counts = {}
    for tok, repl in variants.items():
        c = text.count(tok)
        if c:
            text = text.replace(tok, repl); counts[tok] = c
    log["normalized_double_quotes"] = {"total_replacements": sum(counts.values()), "by_token": counts}
    return text

def collapse_mixed_quotes(text: str, log: dict) -> str:
    pat = re.compile(r"""('?\s*"\s*'|'\s*"\s*|"\s*'\s*)""")
    n = len(list(pat.finditer(text)))
    text = pat.sub('"', text)
    log["collapsed_mixed_quotes"] = n
    return text

def splice_lone_quote_lines(text: str, log: dict) -> str:
    lines = text.split("\n"); quote_only = {'"', '“', '”'}; count = 0; i = 0
    while i < len(lines):
        if lines[i].strip() in quote_only:
            if i>0: lines[i-1] = lines[i-1] + lines[i].strip()
            del lines[i]; count += 1; continue
        i += 1
    log["spliced_lone_quote_lines"] = count
    return "\n".join(lines)

def remove_headers_footers(text: str, log: dict) -> str:
    lines = text.split("\n")
    def is_page(line): return re.fullmatch(r"\s*\d{1,4}\s*", line) is not None
    def has_vol(line): return re.search(r"(?i)\bvolume\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[IVXLCDM]+|[1-9]|1[0-2])\b", line) is not None
    def has_ch(line): return re.search(r"(?:Chapter|chapter)", line) is not None
    def is_bullet(line): return line.strip() in ("â€¢","•","·","•")

    header_spans = []
    i = 0
    while i < len(lines):
        win = [lines[i+j].strip() if i+j<len(lines) else "" for j in range(5)]
        vi = next((j for j,ln in enumerate(win) if has_vol(ln)), None)
        ci = next((j for j,ln in enumerate(win) if has_ch(ln)), None)
        ni = next((j for j,ln in enumerate(win) if is_page(ln)), None)
        if vi is not None and ci is not None and ni is not None:
            lo = i+min(vi,ci,ni); hi = i+max(vi,ci,ni)
            block = [lines[k].strip() for k in range(lo,hi+1)]
            if all(has_vol(x) or has_ch(x) or is_page(x) or is_bullet(x) for x in block):
                header_spans.append((lo,hi)); i = hi+1; continue
        i += 1

    footer_spans = []
    for j in range(len(lines)-1):
        if is_page(lines[j]) and re.search(r"(?i)^\s*history\s+of\s+my\s+life\s*$", lines[j+1]):
            footer_spans.append((j,j+1))

    to_del = set()
    for lo,hi in header_spans+footer_spans: to_del.update(range(lo,hi+1))
    cleaned = [ln for idx,ln in enumerate(lines) if idx not in to_del]

    # Single-line "Volume Seven Chapter X"
    single_pat = re.compile(r"^\s*(?:[•â€¢·]\s*)?(?i:volume\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[IVXLCDM]+|[1-9]|1[0-2]))\s+(?:Chapter|chapter)\s+(?:[A-Za-z]+|[IVXLCDM]+|\d+)\s*$")
    extra = 0; cleaned2 = []
    for ln in cleaned:
        if single_pat.match(ln): extra += 1; continue
        cleaned2.append(ln)

    # Two-line form: "Volume Seven" then punct/quotes then "Chapter X"
    cleaned3 = []
    skip_next = False
    two_count = 0
    for idx, ln in enumerate(cleaned2):
        if skip_next: skip_next = False; continue
        if re.match(r"^\s*(?i:volume\s+seven)\s*$", ln):
            nxt = cleaned2[idx+1] if idx+1 < len(cleaned2) else ""
            if re.match(r"^\s*([\.,•â€¢·\-\u2010\u2011\u2013\u2014\'\"”’])?\s*(?:Chapter|chapter)\s+[A-Za-z]+\s*$", nxt):
                two_count += 1; skip_next = True; continue
        cleaned3.append(ln)

    # Inline "Volume Seven Chapter X"
    inline_pat = re.compile(r"(?i:volume\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[IVXLCDM]+|[1-9]|1[0-2]))\s+(?:Chapter|chapter)\s+(?:[A-Za-z]+|[IVXLCDM]+|\d+)")
    inline_count = len(inline_pat.findall("\n".join(cleaned3)))
    inline_cleaned = inline_pat.sub("", "\n".join(cleaned3))
    inline_cleaned = re.sub(r" {2,}", " ", inline_cleaned)

    log["headers_removed"] = len(header_spans) + extra + two_count
    log["footers_removed"] = len(footer_spans)
    log["extra_header_line_hits"] = extra
    log["two_line_header_hits"] = two_count
    log["inline_header_hits"] = inline_count
    return inline_cleaned

def remove_superscript_artifacts(text: str, log: dict) -> str:
    count = sum(text.count(tok) for tok in ("Â¹","Â²","Â³"))
    text = text.replace("Â¹","").replace("Â²","").replace("Â³","")
    log["superscript_artifacts_removed"] = count
    return text

def remove_glued_word_numbers(text: str, log: dict) -> str:
    pat = re.compile(r"(?P<word>[^\W\d_]+(?:-[^\W\d_]+)*)(?P<num>\d{1,3})\b", re.UNICODE)
    matches = 0; out = []; last = 0
    for m in pat.finditer(text):
        matches += 1; out.append(text[last:m.start("num")]); last = m.end("num")
    out.append(text[last:])
    log["glued_word_numbers_removed"] = matches
    return "".join(out)

def remove_numbers_general(text: str, log: dict) -> str:
    s = text
    deletions = {
        "after_punct_tight": 0, "after_punct": 0, "after_punct_newline": 0,
        "after_comma": 0, "standalone_line": 0,
        "word_num_ctx": 0, "num_at_eol": 0,
        "punct_opt_quotes_num_tight": 0, "punct_opt_quotes_num": 0,
        "word_num_dash": 0, "num_then_tiny_glue_currency": 0,
        "after_currency_word": 0, "start_of_line_token": 0,
        "inline_token_before_letter": 0, "before_parenthesis": 0,
        "mixed_quotes_collapses_post": 0,
    }

    # Patterns
    pat_A0 = re.compile(r'(?<=[\.\!\?\)"”’\]\}\);:])(\d{1,3})\b')
    pat_A  = re.compile(r'(?<=[\.\!\?\)"”’\]\}\);:])\s+(\d{1,3})\b')
    pat_A2 = re.compile(r'(?<=[\.\!\?\)"”’\]\}\);:])\s*\n\s*(\d{1,3})\b')
    pat_B  = re.compile(r',\s*(\d{1,3})\b')
    pat_C  = re.compile(r'^\s*(\d{1,3})\s*$', re.M)
    pat_D  = re.compile(r"(?P<prev>\b[^\W\d_][^\W\d_'\-]{0,}(?:['’][sS])?(?:-[^\W\d_]+)*)\s+(?P<num>\d{1,3})\b(?=\s*(\(|[A-Za-zÀ-ÖØ-öø-ÿ]|,))", re.UNICODE)
    pat_E  = re.compile(r"(\b[^\W\d_][^\W\d_'\-]*(?:-[^\W\d_]+)*)\s+(\d{1,3})(\s*$)", re.UNICODE | re.M)
    pat_F0 = re.compile(r"(?<=[\.\!\?\]\}\);:])(?:\s*['\"’”]{0,2})\s*(\d{1,3})\b")
    pat_F  = re.compile(r"(?<=[\.\!\?\]\}\);:])(?:\s*['\"’”]{0,2})\s+(\d{1,3})\b")
    dash_chars = r"\-–—‑‐"
    pat_G  = re.compile(rf"(?P<word>\b[^\W\d_][^\W\d_'\-]*(?:-[^\W\d_]+)*)\s+(?P<num>\d{{1,3}})\s*(?P<dash>[{dash_chars}])", re.UNICODE)
    pat_G2 = re.compile(rf"(?P<num>\d{{1,3}})\s*(?P<dash>[{dash_chars}])")
    pat_H  = re.compile(r'\b(\d{1,3})\b((?:\s+[A-Za-zÀ-ÖØ-öø-ÿ]{1,3}){0,2})\s+\b(' + '|'.join(sorted(CURRENCY_WORDS)) + r')\b', re.IGNORECASE)
    pat_I  = re.compile(r'\b(' + '|'.join(sorted(CURRENCY_WORDS)) + r')\b\s+(\d{1,3})\b', re.IGNORECASE)
    pat_J  = re.compile(r'^\s*(\d{1,3})\s+(?=[A-Za-zÀ-ÖØ-öø-ÿ])', re.M)
    pat_K  = re.compile(r'(?<=\s)(\d{1,3})(?=\s+[A-Za-zÀ-ÖØ-öø-ÿ])')
    pat_L  = re.compile(r'(?<=\s)(\d{1,3})(?=\s*\()')
    pat_mx = re.compile(r"""('?\s*"\s*'|'\s*"\s*|"\s*'\s*)""")

    def del_matches(s, it, key):
        cnt = 0; out = []; last = 0
        for m in it:
            g = m.group(1)
            if is_year(g):
                continue
            if key in ("after_punct_tight","after_punct","after_punct_newline","after_comma","start_of_line_token","inline_token_before_letter","before_parenthesis"):
                if int(g) >= 100 and next_word_is_currency(s, m.end(1)):
                    continue
            out.append(s[last:m.start(1)]); last = m.end(1); cnt += 1
        out.append(s[last:])
        deletions[key] += cnt
        return "".join(out)

    # Apply
    s = del_matches(s, pat_A0.finditer(s), "after_punct_tight")
    s = del_matches(s, pat_A.finditer(s),  "after_punct")
    s = del_matches(s, pat_A2.finditer(s), "after_punct_newline")
    s = del_matches(s, pat_B.finditer(s),  "after_comma")
    s = del_matches(s, pat_C.finditer(s),  "standalone_line")
    s = del_matches(s, pat_D.finditer(s),  "word_num_ctx")
    s = re.sub(pat_E, lambda m: m.group(1)+m.group(3) if not is_year(m.group(2)) else m.group(0), s)
    s = del_matches(s, pat_F0.finditer(s), "punct_opt_quotes_num_tight")
    s = del_matches(s, pat_F.finditer(s),  "punct_opt_quotes_num")
    s = re.sub(pat_G,  lambda m: " " + m.group("dash") if not is_year(m.group("num")) else m.group(0), s)
    s = re.sub(pat_G2, lambda m: " " + m.group("dash"), s)
    def repl_H(m):
        num = m.group(1)
        if is_year(num): return m.group(0)
        middle = (m.group(2) or "").strip()
        if middle:
            words = [w.lower() for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", middle)]
            if not all((w in STOPWORDS_TINY or len(w) <= 3) for w in words):
                return m.group(0)
        return m.group(0).replace(num, "", 1)
    s = re.sub(pat_H, repl_H, s)
    s = re.sub(pat_I, lambda m: m.group(0).replace(m.group(2), "", 1) if not is_year(m.group(2)) else m.group(0), s)
    s = del_matches(s, pat_J.finditer(s), "start_of_line_token")
    s = del_matches(s, pat_K.finditer(s), "inline_token_before_letter")
    s = del_matches(s, pat_L.finditer(s), "before_parenthesis")

    # Tidy spaces
    s = re.sub(r",\s+(?=[A-Za-z])", ", ", s)
    s = re.sub(r'([\.\!\?\)"”’\]\}\);:])\s+(?=["A-Za-z])', r"\1 ", s)

    # Mixed quotes collapse (post)
    before = len(list(pat_mx.finditer(s)))
    s = pat_mx.sub('"', s)
    deletions["mixed_quotes_collapses_post"] = before

    log["number_removals"] = {"deletions": deletions}
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--log", default=None)
    ap.add_argument("--rtf", action="store_true")
    args = ap.parse_args()

    if args.rtf:
        raw = open(args.infile, "rb").read()
        text = rtf_to_text(raw)
    else:
        text = open(args.infile, "r", encoding="utf-8").read()

    log = {}
    text = remove_volume_chapter_headers(text)
    text = remove_headers_footers(text, log)
    text = splice_lone_quote_lines(text, log)
    text = normalize_double_quotes(text, log)
    text = collapse_mixed_quotes(text, log)
    text = remove_superscript_artifacts(text, log)
    text = remove_glued_word_numbers(text, log)
    text = remove_numbers_general(text, log)

    with open(args.outfile, "w", encoding="utf-8") as f:
        f.write(text)
    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    print("Cleaned written to:", args.outfile)
    if args.log:
        print("Log written to:", args.log)


# ======= END: Inlined Step1 v3 code =======

def run_v3_sequence(infile: str, is_rtf: bool, log_path: str|None) -> str:
    # replicate v3 main() flow without writing files mid-way
    if is_rtf:
        raw = pathlib.Path(infile).read_bytes()
        text = rtf_to_text(raw)
    else:
        text = pathlib.Path(infile).read_text(encoding="utf-8")
    log = {}
    # exact sequence
    text = remove_volume_chapter_headers(text)
    text = remove_headers_footers(text, log)
    text = splice_lone_quote_lines(text, log)
    text = normalize_double_quotes(text, log)
    text = collapse_mixed_quotes(text, log)
    text = remove_superscript_artifacts(text, log)
    text = remove_glued_word_numbers(text, log)
    text = remove_numbers_general(text, log)
    if log_path:
        pathlib.Path(log_path).write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return text

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--log", default=None)
    ap.add_argument("--rtf", action="store_true")
    args = ap.parse_args()

    # Run v3 cleanup
    text = run_v3_sequence(args.infile, args.rtf, args.log)

    # Apply v6 extra: French mojibake fixes inside words
    text = _apply_french_utf8_latin1_fixes(text)

    # Write final Step1 output
    pathlib.Path(args.outfile).write_text(text, encoding="utf-8")
    if args.log:
        # v3 already wrote a detailed log; v6 writes none additional — preserving behavior
        pass

if __name__ == "__main__":
    main()
