#!/usr/bin/env python3
# Wrapper around Step1 to preserve standalone 'CHAPTER I' if removed.
import argparse, subprocess, sys, re, pathlib, json

ap = argparse.ArgumentParser()
ap.add_argument("infile")
ap.add_argument("outfile")
ap.add_argument("--log", default=None)
ap.add_argument("--rtf", action="store_true")
args = ap.parse_args()

# Run the original Step1
ret = subprocess.run(
    ["python3", "/mnt/data/Step1_ocr_cleanup_v3_patched.py",
     args.infile, args.outfile] + (["--log", args.log] if args.log else []) + (["--rtf"] if args.rtf else []),
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
