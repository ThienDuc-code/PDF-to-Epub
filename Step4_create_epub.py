
# See: make_epub_step4.py in previous cell (a self-contained script)
# Rewriting the full script here for download convenience.
import sys, zipfile, os, re, uuid, shutil, datetime
from pathlib import Path

def html_escape(s):
    return (s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

def build_epub(src_txt, template_epub, out_epub, title_override=None, creator_override=None, lang_override=None):
    src_txt = Path(src_txt); template_epub = Path(template_epub); out_epub = Path(out_epub)
    assert src_txt.exists(), f"Missing input TXT: {src_txt}"
    assert template_epub.exists(), f"Missing template EPUB: {template_epub}"

    ROMAN = r"(?:M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))"

    # Unpack template
    work_tmpl = src_txt.parent / "_tmpl_epub_step4"
    if work_tmpl.exists(): shutil.rmtree(work_tmpl)
    work_tmpl.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(template_epub, 'r') as z:
        z.extractall(work_tmpl)

    container_xml = work_tmpl / "META-INF" / "container.xml"
    container_text = container_xml.read_text(encoding="utf-8", errors="ignore") if container_xml.exists() else ""
    m = re.search(r'full-path="([^"]+)"', container_text)
    opf_rel = m.group(1) if m else "content.opf"
    opf_path = work_tmpl / opf_rel
    opf_text = opf_path.read_text(encoding="utf-8", errors="ignore") if opf_path.exists() else ""
    oebps_root = opf_path.parent
    css_files = list(oebps_root.rglob("*.css"))

    # Metadata
    title = title_override or (re.search(r"<dc:title>(.*?)</dc:title>", opf_text or "", flags=re.S|re.I).group(1).strip() if re.search(r"<dc:title>(.*?)</dc:title>", opf_text or "", flags=re.S|re.I) else "History of My Life — Volume 6")
    creator = creator_override or (re.search(r"<dc:creator[^>]*>(.*?)</dc:creator>", opf_text or "", flags=re.S|re.I).group(1).strip() if re.search(r"<dc:creator[^>]*>(.*?)</dc:creator>", opf_text or "", flags=re.S|re.I) else "Giacomo Casanova (Trask tr.)")
    lang = lang_override or (re.search(r"<dc:language[^>]*>(.*?)</dc:language>", opf_text or "", flags=re.S|re.I).group(1).strip() if re.search(r"<dc:language[^>]*>(.*?)</dc:language>", opf_text or "", flags=re.S|re.I) else "en")
    pub_id = f"urn:uuid:{uuid.uuid4()}"

    # Read and split chapters
    txt = src_txt.read_text(encoding="utf-8", errors="ignore").replace("\r\n","\n").replace("\r","\n")
    chap_re = re.compile(rf"(?m)^\s*CHAPTER\s+({ROMAN})\s*$")
    matches = list(chap_re.finditer(txt))
    chapters = []
    if matches:
        if matches[0].start()>0:
            pre = txt[:matches[0].start()].strip()
            if pre: chapters.append(("Front Matter", pre))
        for i,mx in enumerate(matches):
            title_text = f"CHAPTER {mx.group(1)}"
            start = mx.end()
            end = matches[i+1].start() if i+1 < len(matches) else len(txt)
            body = txt[start:end].strip()
            chapters.append((title_text, body))
    else:
        chapters.append(("Body", txt.strip()))

    # Build dirs
    build = src_txt.parent / "_build_epub_step4"
    if build.exists(): shutil.rmtree(build)
    (build / "OEBPS" / "Text").mkdir(parents=True, exist_ok=True)
    (build / "OEBPS" / "Styles").mkdir(parents=True, exist_ok=True)
    (build / "META-INF").mkdir(parents=True, exist_ok=True)

    # mimetype + container
    (build / "mimetype").write_text("application/epub+zip", encoding="utf-8")
    (build / "META-INF" / "container.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles>\n'
        '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        '  </rootfiles>\n'
        '</container>\n', encoding="utf-8"
    )

    # CSS
    copied_css = []
    if css_files:
        for css in css_files:
            dest = build / "OEBPS" / "Styles" / css.name
            shutil.copy2(css, dest)
            copied_css.append(dest.name)
    else:
        base_css = (build / "OEBPS" / "Styles" / "style.css")
        base_css.write_text('body{font-family:serif;line-height:1.4}h1{page-break-before:always;text-align:center}p{margin:0;text-indent:1.2em}', encoding="utf-8")
        copied_css.append(base_css.name)

    # Chapters
    items = []
    def normalize_lines(block): return re.sub(r"\s*\n\s*", " ", block).strip()
    for idx,(tt, body) in enumerate(chapters, start=1):
        fn = f"chap_{idx:03d}.xhtml"
        path = build / "OEBPS" / "Text" / fn
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        content = "\n".join(f"<p>{html_escape(normalize_lines(p))}</p>" for p in paras)
        classes = "chapter-open" if idx>1 or tt.upper().startswith("CHAPTER") else "frontmatter"
        css_link = f'<link rel="stylesheet" type="text/css" href="../Styles/{copied_css[0]}"/>' if copied_css else ""
        path.write_text(
            f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">\n<head>\n<meta charset="utf-8"/>\n<title>{html_escape(tt)}</title>\n{css_link}\n</head>\n'
            f'<body class="{classes}">\n<h1 id="h{idx}">{html_escape(tt)}</h1>\n{content}\n</body>\n</html>\n',
            encoding="utf-8"
        )
        items.append({"id": f"chap{idx}", "href": f"Text/{fn}", "title": tt})

    # nav.xhtml
    nav_path = build / "OEBPS" / "nav.xhtml"
    css_link_nav = f'<link rel="stylesheet" type="text/css" href="Styles/{copied_css[0]}"/>' if copied_css else ""
    nav_items = "\n".join([f'<li><a href="{it["href"]}#h{n+1}">{html_escape(it["title"])}</a></li>' for n,it in enumerate(items)])
    nav_path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">\n<head>\n<meta charset="utf-8"/>\n<title>Contents</title>\n{css_link_nav}\n</head>\n'
        f'<body>\n<nav epub:type="toc" id="toc">\n<h1>Contents</h1>\n<ol>\n{nav_items}\n</ol>\n</nav>\n</body>\n</html>\n',
        encoding="utf-8"
    )

    # OPF
    manifest_items = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n']
    for it in items:
        manifest_items.append(f'<item id="{it["id"]}" href="{it["href"]}" media-type="application/xhtml+xml"/>\n')
    for css in copied_css:
        manifest_items.append(f'<item id="{css}" href="Styles/{css}" media-type="text/css"/>\n')
    spine_items = "\n".join([f'<itemref idref="{it["id"]}"/>' for it in items])
    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    (build / "OEBPS" / "content.opf").write_text(
        f'''<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="pub-id" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">urn:uuid:{uuid.uuid4()}</dc:identifier>
    <dc:title>{html_escape(title)}</dc:title>
    <dc:creator>{html_escape(creator)}</dc:creator>
    <dc:language>{html_escape(lang)}</dc:language>
    <meta property="dcterms:modified">{now_iso}</meta>
  </metadata>
  <manifest>
    {''.join(manifest_items)}
  </manifest>
  <spine>
    {spine_items}
  </spine>
</package>
''', encoding="utf-8"
    )

    # Zip to epub
    if out_epub.exists(): out_epub.unlink()
    with zipfile.ZipFile(out_epub, 'w') as z:
        z.writestr("mimetype", (build / "mimetype").read_bytes(), compress_type=zipfile.ZIP_STORED)
        for root, dirs, files in os.walk(build):
            for fname in files:
                fp = Path(root) / fname
                rel = fp.relative_to(build).as_posix()
                if rel == "mimetype": continue
                z.write(fp, rel, compress_type=zipfile.ZIP_DEFLATED)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python make_epub_step4.py INPUT_TXT TEMPLATE_EPUB OUTPUT_EPUB")
        sys.exit(1)
    build_epub(sys.argv[1], sys.argv[2], sys.argv[3])
