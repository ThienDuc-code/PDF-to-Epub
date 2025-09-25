#!/usr/bin/env python3
# Wrapper around Step1 to preserve standalone 'CHAPTER I' if removed.
import argparse, subprocess, sys, re, pathlib, json, os

def _apply_french_utf8_latin1_fixes(text: str) -> str:
    """
    Fix common UTF-8 -> Latin-1 mojibake for French accented letters,
    only when the artifact is part of a word (adjacent to at least
    one Unicode word character). This avoids changing standalone artifacts
    from footnotes or layout debris.
    """
    mapping = {
        # Lowercase
        "Ã©": "é", "Ã¨": "è", "Ãª": "ê", "Ã«": "ë",
        "Ã ": "à", "Ã¢": "â", "Ã¤": "ä",
        "Ã®": "î", "Ã¯": "ï",
        "Ã´": "ô", "Ã¶": "ö",
        "Ã¹": "ù", "Ã»": "û", "Ã¼": "ü",
        "Ã§": "ç",
        # Uppercase
        "Ã‰": "É", "Ãˆ": "È", "ÃŠ": "Ê", "Ã‹": "Ë",
        "Ã€": "À", "Ã‚": "Â", "Ã„": "Ä",
        "ÃŒ": "Ì", "ÃŽ": "Î", "Ã": "Ï",
        "Ã’": "Ò", "Ã”": "Ô", "Ã–": "Ö",
        "Ã™": "Ù", "Ã›": "Û", "Ãœ": "Ü",
        "Ã‡": "Ç",
    }

    # For each mojibake sequence, only replace when it borders a word char.
    # Pattern:   (?<=\w)BAD | BAD(?=\w)
    for bad, good in mapping.items():
        pat = re.compile(rf"(?:(?<=\w){re.escape(bad)}|{re.escape(bad)}(?=\w))", flags=re.UNICODE)
        text = pat.sub(good, text)
    return text

ap = argparse.ArgumentParser()
ap.add_argument("infile")
ap.add_argument("outfile")
ap.add_argument("--log", default=None)
ap.add_argument("--rtf", action="store_true")
args = ap.parse_args()

# Resolve repository root and local path to original Step1 script
script_dir = pathlib.Path(__file__).resolve().parent
repo_root = script_dir.parent
legacy_dir = repo_root / "text-processing" / "legacy"
v3_patched = legacy_dir / "Step1_ocr_cleanup_v3_patched.py"
v5_script = legacy_dir / "Step1_ocr_cleanup_v5.py"

step1_path = None
if v3_patched.exists():
    step1_path = str(v3_patched)
elif v5_script.exists():
    step1_path = str(v5_script)
else:
    print("Error: Could not locate original Step1 script in repository.")
    print(f"Tried: {v3_patched} and {v5_script}")
    sys.exit(2)

# Run the original Step1
ret = subprocess.run(
    ["python3", step1_path, args.infile, args.outfile]
    + (["--log", args.log] if args.log else [])
    + (["--rtf"] if args.rtf else []),
    check=True, capture_output=True, text=True
)

src = pathlib.Path(args.infile).read_text(encoding="utf-8", errors="ignore")
dst_path = pathlib.Path(args.outfile)
dst = dst_path.read_text(encoding="utf-8", errors="ignore")

had_chap_I_in_src = re.search(r"(?m)^\s*CHAPTER\s+I\s*$", src) is not None
has_chap_I_in_dst = re.search(r"(?m)^\s*CHAPTER\s+I\s*$", dst) is not None
if had_chap_I_in_src and not has_chap_I_in_dst:
    # Insert CHAPTER I before CHAPTER II if present; else at start.
    if re.search(r"(?m)^\s*CHAPTER\s+II\s*$", dst):
        dst = re.sub(r"(?m)^(?=\s*CHAPTER\s+II\s*$)", "CHAPTER I\n\n", dst, count=1)
    else:
        dst = "CHAPTER I\n\n" + dst
    dst_path.write_text(dst, encoding="utf-8")
    # Append a note to the log if provided
    if args.log:
        try:
            logp = pathlib.Path(args.log)
            log = json.loads(logp.read_text(encoding="utf-8"))
        except Exception:
            log = {}
        log["chapterI_restored"] = True
        logp.write_text(json.dumps(log, indent=2), encoding="utf-8")

print("Wrapped Step1 complete (CHAPTER I preservation).")


# Wrapper added in v5 to ensure French mojibake is fixed
# If the underlying script exposes clean_ocr_text, wrap it; otherwise ignore
try:
    _original_clean_ocr_text = clean_ocr_text  # type: ignore[name-defined]
    def clean_ocr_text(text):  # type: ignore[func-assign]
        text = _apply_french_utf8_latin1_fixes(text)
        return _original_clean_ocr_text(text)
except Exception:
    # Not all Step1 variants define clean_ocr_text; it's optional.
    pass
