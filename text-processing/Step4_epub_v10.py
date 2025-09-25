#!/usr/bin/env python3
# Step4_epub_v10.py — Build EPUB (title/volume as paragraphs) and ensure chapters-only TOC
import argparse, re, os, shutil, zipfile
from pathlib import Path

try:
    import pypandoc
except Exception as e:
    raise SystemExit("pypandoc is required to build the EPUB. Please install pandoc/pypandoc.")


def read_and_sanitize(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    # strip control chars (except newlines & tabs)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return text

def promote_chapters_to_h2(text: str) -> str:
    # Turn CHAPTER N blocks into markdown h2
    return re.sub(r"\nCHAPTER\s+([IVXLCDM]+)\s*\n", lambda m: f"\n\n## CHAPTER {m.group(1)}\n\n", text)

def normalize_hr(text: str) -> str:
    # Ensure proper <hr /> and spacing
    text = re.sub(r"(?m)^\s*---\s*$", lambda m: "\n\n<hr />\n\n", text)
    text = re.sub(r"\s*(<hr\s*/?>)\s*", r"\n\n\1\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def reflow_paragraphs_conservative(md: str) -> str:
    blocks = md.split("\n\n")
    out = []
    for b in blocks:
        bs = b.strip("\n")
        if not bs or bs.startswith("## CHAPTER") or bs == "<hr />" or bs.startswith(("# ","```","> ","- ","* ","1. ")) or "```" in bs:
            out.append(bs); continue
        out.append(re.sub(r"\s*\n\s*", " ", bs).strip())
    return "\n\n".join(out) + ("\n" if md.endswith("\n") else "")

def insert_pagebreaks(md: str) -> tuple[str, int]:
    matches = list(re.finditer(r"^## CHAPTER [IVXLCDM]+", md, flags=re.MULTILINE))
    if len(matches) <= 1:
        return md, 0
    for m in reversed(matches[1:]):
        md = md[:m.start()] + "\n\n<div style=\"page-break-before: always\"></div>\n\n" + md[m.start():]
    return md, len(matches) - 1

def make_title_page(title: str, volume: str|None, author: str, translator: str) -> str:
    # Render as paragraphs (not headings) so they don't end up in the TOC
    title_html = f"<p class=\"book-title\">{title}</p>\n\n" if title else ""
    vol_html = f"<p class=\"volume-label\">{volume}</p>\n\n" if volume else ""
    return f"{title_html}{vol_html}**{author}**  \\\n_{translator}_\n\n<hr />\n\n"

def write_css(path: Path):
    path.write_text(
        "body{line-height:1.5;font-family:serif;}"
        "h1,h2{page-break-after:avoid;}"
        ".book-title{font-family:Georgia,serif;font-size:2.2em;font-weight:700;text-align:center;margin:1.2em 0 .5em;}"
        ".volume-label{font-size:1.6em;font-weight:700;text-align:center;margin:0 0 1em;}"
        "hr{border:0;border-top:1px solid #666;margin:1.2em 0;}",
        encoding="utf-8"
    )

def build_epub(md_path: Path, epub_path: Path, css_path: Path, title: str, volume: str|None, author: str, translator: str):
    # Compose metadata title with volume if available (used in ebook metadata, not TOC)
    meta_title = f"{title} — {volume}" if volume else title
    pypandoc.convert_file(
        str(md_path),
        "epub",
        outputfile=str(epub_path),
        extra_args=[
            f"--css={css_path}",
            f"--metadata=title:{meta_title}",
            f"--metadata=creator:{author}",
            f"--metadata=contributor:{translator}",
        ],
    )

def _extract_volume_line(text: str) -> tuple[str, str|None]:
    """Extract a leading 'VOLUME N' style line if present, return (new_text, 'Volume N' or None)."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    vol_re = re.compile(r'^\s*VOLUME\s+([0-9IVXLCDM]+)\s*$', re.IGNORECASE)
    if i < len(lines) and vol_re.match(lines[i].strip()):
        vol_num = vol_re.match(lines[i].strip()).group(1)
        # remove that line and an immediate blank
        del lines[i]
        if i < len(lines) and lines[i].strip() == "":
            del lines[i]
        return ("\n".join(lines), f"Volume {vol_num}")
    return text, None

def _flatten_toc_nav(epub_path: Path, title_substr: str = "History of My Life") -> None:
    """Remove the wrapper LI that contains the title anchor; promote nested chapter LIs."""
    tmpdir = epub_path.with_suffix(".navtmp")
    if tmpdir.exists():
        shutil.rmtree(tmpdir)
    tmpdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(epub_path, 'r') as z:
        z.extractall(tmpdir)
    nav_path = next((p for p in tmpdir.rglob("nav.xhtml")), None)
    if not nav_path:
        shutil.rmtree(tmpdir, ignore_errors=True); return
    txt = nav_path.read_text(encoding="utf-8", errors="ignore")

    m = re.search(r'(<nav[^>]*epub:type="toc"[^>]*>)(.*?)(</nav>)', txt, flags=re.I|re.DOTALL)
    if not m:
        shutil.rmtree(tmpdir, ignore_errors=True); return
    pre, toc_inner, post = m.group(1), m.group(2), m.group(3)

    # If already flat and contains CHAPTERs, do nothing
    if re.search(r'>\s*CHAPTER\s+[IVXLCDM]+\s*<', toc_inner, flags=re.I):
        # Also ensure there is no title anchor
        toc_inner = re.sub(r'<li[^>]*>\s*<a[^>]*>[^<]*'+re.escape(title_substr)+r'[^<]*</a>\s*</li>\s*', '', toc_inner, flags=re.I|re.DOTALL)
        new_txt = txt[:m.start()] + pre + toc_inner + post + txt[m.end():]
        nav_path.write_text(new_txt, encoding="utf-8")
    else:
        # Find title wrapper LI with nested OL of chapters
        wrap = re.search(
            r'(<li[^>]*>\s*<a[^>]*>[^<]*'+re.escape(title_substr)+r'[^<]*</a>\s*<ol>(.*?)</ol>\s*</li>)',
            toc_inner, flags=re.I|re.DOTALL
        )
        if wrap:
            toc_inner2 = toc_inner.replace(wrap.group(1), wrap.group(2))
            new_txt = txt[:m.start()] + pre + toc_inner2 + post + txt[m.end():]
            nav_path.write_text(new_txt, encoding="utf-8")
        else:
            # As a last resort, rebuild TOC from chapter sections in content
            _rebuild_toc_from_content(tmpdir)

    # Rezip
    new_zip = epub_path.with_suffix(".tmp.epub")
    with zipfile.ZipFile(new_zip, 'w') as z:
        mimetype_file = tmpdir / "mimetype"
        if mimetype_file.exists():
            z.writestr("mimetype", mimetype_file.read_bytes(), compress_type=zipfile.ZIP_STORED)
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                full = Path(root)/f
                rel = str(full.relative_to(tmpdir))
                if rel == "mimetype":
                    continue
                z.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)
    os.replace(new_zip, epub_path)
    shutil.rmtree(tmpdir, ignore_errors=True)

def _rebuild_toc_from_content(extracted_dir: Path) -> None:
    """Create a chapters-only TOC by scanning EPUB/text/*.xhtml for <section id='chapter-*'><h2>CHAPTER ...</h2>."""
    nav_path = next((p for p in extracted_dir.rglob("nav.xhtml")), None)
    if not nav_path:
        return
    text_dir = extracted_dir / "EPUB" / "text"
    li_items = []
    for p in sorted(text_dir.glob("*.xhtml")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        # Prefer section id form
        for m in re.finditer(r'<section[^>]*id="([^"]*chapter[^"]*)"[^>]*>\s*<h2[^>]*>(CHAPTER\s+[IVXLCDM]+)</h2>', t, flags=re.I|re.DOTALL):
            sec_id = m.group(1); title = m.group(2).upper()
            href = f"text/{p.name}#{sec_id}"
            li_items.append(f'<li><a href="{href}">{title}</a></li>')
    # If nothing found, try plain h2 ids
    if not li_items:
        for p in sorted(text_dir.glob("*.xhtml")):
            t = p.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'<h2[^>]*id="([^"]*chapter[^"]*)"[^>]*>(CHAPTER\s+[IVXLCDM]+)</h2>', t, flags=re.I):
                sec_id = m.group(1); title = m.group(2).upper()
                href = f"text/{p.name}#{sec_id}"
                li_items.append(f'<li><a href="{href}">{title}</a></li>')
    # Write new nav only if we actually detected chapters
    if li_items:
        new_nav = f'<nav epub:type="toc" id="toc"><ol>{"".join(li_items)}</ol></nav>'
        nav_path.write_text(new_nav, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="input TXT (Step 3 output)")
    ap.add_argument("output", help="output EPUB path")
    ap.add_argument("--title", default="History of My Life")
    ap.add_argument("--author", default="Giacomo Casanova")
    ap.add_argument("--translator", default="Translated by Willard R. Trask")
    ap.add_argument("--volume", default="")  # optional; we may auto-detect
    args = ap.parse_args()

    txt = read_and_sanitize(Path(args.input))
    txt, vol_found = _extract_volume_line(txt)
    volume_label = args.volume or vol_found or ""

    md = promote_chapters_to_h2(txt)
    md = normalize_hr(md)
    md = reflow_paragraphs_conservative(md)
    md, _ = insert_pagebreaks(md)

    # Write intermediate markdown (next to output EPUB)
    out = Path(args.output)
    md_out = out.with_suffix(".md")
    css_path = out.with_suffix(".css")
    md_out.write_text(
        make_title_page(args.title, volume_label, args.author, args.translator) + md,
        encoding="utf-8"
    )
    write_css(css_path)

    # Build EPUB with pandoc
    build_epub(md_out, out, css_path, args.title, volume_label, args.author, args.translator)

    # Flatten TOC so only chapters appear
    _flatten_toc_nav(out)

    print("[Step4] EPUB build complete")
    # Optionally keep md_out for debugging; otherwise comment out the next line
    # md_out.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
