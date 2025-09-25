#!/usr/bin/env python3
"""
Step4_epub_v1 — Build EPUB with linked TOC from Step 3 output

(see in-canvas documentation for full details)
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

try:
    import pypandoc  # type: ignore
except Exception:
    sys.stderr.write("[Step4] ERROR: pypandoc is required. Install with `pip install pypandoc` and ensure Pandoc is installed.\n")
    raise

def read_and_sanitize(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n","\n").replace("\r","\n")
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

def promote_chapters_to_h2(text: str) -> str:
    return re.sub(r"\nCHAPTER\s+([IVXLCDM]+)\s*\n", lambda m: f"\n\n## CHAPTER {m.group(1)}\n\n", text)

def normalize_hr(text: str) -> str:
    text = re.sub(r"(?m)^\s*---\s*$", lambda m: "\n\n<hr />\n\n", text)
    text = re.sub(r"\s*(<hr\s*/?>)\s*", r"\n\n\1\n\n", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text)

def reflow_paragraphs_conservative(md: str) -> str:
    blocks = md.split("\n\n"); out = []
    for b in blocks:
        bs = b.strip("\n")
        if not bs or bs.startswith("## CHAPTER") or bs == "<hr />" or bs.startswith(("# ","```","> ","- ","* ","1. ")) or "```" in bs:
            out.append(bs); continue
        out.append(re.sub(r"\s*\n\s*", " ", bs).strip())
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(out))

def fix_a1_a2_single_letter_glitches(md: str) -> tuple[str,int]:
    fixes=0
    md,c1=re.subn(r"(\b[IA])\s*\n+\s*<hr\s*/>\s*\n+\s*([A-Z]{2,}\b)",r"\n\n<hr />\n\n\1 \2",md); fixes+=c1
    md,c2=re.subn(r"([\"“”])\s*(\b[IA])\s*\n+\s*<hr\s*/>\s*\n+\s*([A-Z]{2,}\b)",r"\n\n<hr />\n\n\1\2 \3",md); fixes+=c2
    md,c3=re.subn(r"<hr\s*/>\s*\n+([\"“”]?\b[IA])\s*\n+([A-Z]{2,}\b)",r"<hr />\n\n\1 \2",md); fixes+=c3
    md=re.sub(r"\s*(<hr\s*/>)\s*",r"\n\n\1\n\n",md); md=re.sub(r"\n{3,}","\n\n",md)
    return md,fixes

def insert_pagebreaks(md: str) -> tuple[str,int]:
    matches=list(re.finditer(r"^## CHAPTER [IVXLCDM]+",md,flags=re.MULTILINE))
    if len(matches)<=1: return md,0
    for m in reversed(matches[1:]): md=md[:m.start()]+"\n\n<div style=\"page-break-before: always\"></div>\n\n"+md[m.start():]
    return md,len(matches)-1

def make_title_page(title, volume, author, translator):
    vol = f"<p class=\"volume-label\">Volume {volume}</p>\n\n" if volume else ""
    return f"# {title}\n\n{vol}**{author}**  \\\n_{translator}_\n\n<hr />\n\n"

def write_css(path: Path):
    path.write_text("""body{line-height:1.5;font-family:serif;}h1,h2{page-break-after:avoid;}h1{text-align:center;margin:2em 0 .5em;}h2{margin-top:2em;margin-bottom:.75em;}p{margin:.7em 0;text-indent:0;}hr{border:none;border-top:1px solid #666;margin:1.2em 0;}""",encoding="utf-8")

def build_epub(md_path, epub_path, css_path, title, volume, author, translator):
    pypandoc.convert_file(str(md_path),"epub",outputfile=str(epub_path),extra_args=["--toc",f"--css={css_path}",f"--metadata=title:{title} — Volume {volume}",f"--metadata=author:{author}",f"--metadata=contributor:{translator}"])


def extract_and_remove_volume_line(text: str) -> tuple[str, str | None]:
    """If the text begins with a standalone 'VOLUME N' (any case), extract it and remove from body.
    Returns (new_text, volume_label or None)."""
    lines = text.splitlines()
    vol_re = re.compile(r'^\s*VOLUME\s+([0-9IVXLCDM]+)\s*$', re.IGNORECASE)
    # find first non-empty line
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and vol_re.match(lines[i].strip()):
        vol_line = lines[i].strip()
        # remove it and any immediately following blank line
        del lines[i]
        if i < len(lines) and lines[i].strip() == "":
            del lines[i]
        return ("\n".join(lines), vol_line.upper())
    return (text, None)


def main():
    ap=argparse.ArgumentParser();
    ap.add_argument("input",type=Path); ap.add_argument("output",type=Path)
    ap.add_argument("--md-out",type=Path); ap.add_argument("--title",default="History of My Life"); ap.add_argument("--volume",default="10"); ap.add_argument("--author",default="Giacomo Casanova"); ap.add_argument("--translator",default="Translated by Willard R. Trask")
    a=ap.parse_args()
    text=read_and_sanitize(a.input)
    text, vol_found = extract_and_remove_volume_line(text)
    if not a.volume and vol_found:
        a.volume = vol_found
    text=promote_chapters_to_h2(text); text=normalize_hr(text); text=reflow_paragraphs_conservative(text); text,f1=fix_a1_a2_single_letter_glitches(text); text,pb=insert_pagebreaks(text)
    md=make_title_page(a.title,a.volume,a.author,a.translator)+text
    md_out=a.md_out or a.output.with_suffix(".md"); md_out.write_text(md,encoding="utf-8")
    css_path=a.output.with_name("hol_epub.css"); write_css(css_path)
    build_epub(md_out,a.output,css_path,a.title,a.volume,a.author,a.translator)
    print("[Step4] EPUB build complete")

if __name__=='__main__': main()
