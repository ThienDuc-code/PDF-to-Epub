#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wrapper around Step1_ocr_cleanup_v7.py that guarantees:
  - The FIRST "Volume ... CHAPTER ..." block is preserved
  - Any ALL-CAPS standalone "CHAPTER <NUM/ROMAN>" headings are never removed
Usage (same CLI as Step1):
    python3 Step1_ocr_cleanup_v7_preserve.py INFILE OUTFILE [--log JSON] [--rtf]
"""

import argparse, pathlib, importlib.util, re, sys

def _preserve_allcaps_chapter_and_first_volume_chapter(text: str, original_text: str) -> str:
    chap_line_re = re.compile(r'(?m)^\s*CHAPTER\s+(?:[IVXLCDM]+|[A-Z0-9]+)\s*$')

    # 1) Ensure first ALL-CAPS chapter from original exists as a standalone line
    m = chap_line_re.search(original_text)
    if m:
        first_chap = m.group(0).strip()
        if not re.search(r'(?m)^\s*' + re.escape(first_chap) + r'\s*$', text):
            # Insert near the top after leading blanks
            lines = text.splitlines()
            i = 0
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            lines[i:i] = ["", first_chap, ""]
            text = "\n".join(lines)

    # 2) Ensure presence of "Volume <...>" line if it existed at the very top of the original
    m_vol = re.search(r'(?m)^\s*Volume\s+\S.*$', original_text)
    if m_vol:
        vol_line = m_vol.group(0).strip()
        # Put it above the chapter if missing near the top
        if not re.search(r'(?m)^\s*' + re.escape(vol_line) + r'\s*$', text):
            lines = text.splitlines()
            i = 0
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            lines[i:i] = ["", vol_line, ""]
            text = "\n".join(lines)

    return text

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--log", default=None)
    ap.add_argument("--rtf", action="store_true")
    args = ap.parse_args()

    # Load the original Step1 module dynamically
    step1_path = pathlib.Path(__file__).with_name("Step1_ocr_cleanup_v7.py")
    spec = importlib.util.spec_from_file_location("step1_core", str(step1_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Run the core v3 pipeline
    text = mod.run_v3_sequence(args.infile, args.rtf, args.log)

    # Apply the French fixes (script's extra step)
    if hasattr(mod, "_apply_french_utf8_latin1_fixes"):
        text = mod._apply_french_utf8_latin1_fixes(text)

    # Apply heading-preservation safeguard using the original input as reference
    original_text = pathlib.Path(args.infile).read_text(encoding="utf-8")
    text = _preserve_allcaps_chapter_and_first_volume_chapter(text, original_text)

    # Write out
    pathlib.Path(args.outfile).write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
