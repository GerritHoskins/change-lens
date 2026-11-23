"""Builds the landing page's legal pages from the drafts in docs/legal.

    python scripts/build_legal_pages.py

Writes web/{imprint,privacy,terms}.html and web/de/{imprint,privacy,terms}.html. The Markdown drafts stay
the source: edit them, run this, commit both. A page whose draft still has a placeholder or a review note
in [SQUARE BRACKETS] gets `noindex`, and each bracket is marked on the page.

Only the Markdown the drafts use is understood: #, ## and ### headings, paragraphs (a line break inside one
is kept, for address blocks), `-` lists, tables, `>` notes, `---`, **bold**, `code` and [text](url) links.
"""
import html
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = "https://changelens.pixeltronic.dev/"
BRACKET = re.compile(r"\[([^\]\[]+)\](?!\()")

TEXT = {
    "en": {"dir": "", "home": "./", "other": "de/", "list": "Early-bird list", "page_nav": "Page",
           "legal_nav": "Legal", "imprint": "Imprint", "privacy": "Privacy policy", "terms": "Terms",
           "table": "Table, scrolls sideways", "home_label": "ChangeLens, home",
           "desc": {"imprint": "Who runs ChangeLens and how to reach us.",
                    "privacy": "Which personal data ChangeLens processes, why, for how long, and your rights.",
                    "terms": "The terms for using the ChangeLens app and service."}},
    "de": {"dir": "de/", "home": "./", "other": "../", "list": "Early-Bird-Liste", "page_nav": "Seite",
           "legal_nav": "Rechtliches", "imprint": "Impressum", "privacy": "Datenschutzerklärung",
           "terms": "Nutzungsbedingungen", "table": "Tabelle, seitlich scrollbar",
           "home_label": "ChangeLens, Startseite",
           "desc": {"imprint": "Wer ChangeLens betreibt und wie du uns erreichst.",
                    "privacy": "Welche personenbezogenen Daten ChangeLens verarbeitet, wozu, wie lange, und deine Rechte.",
                    "terms": "Die Bedingungen für die Nutzung der ChangeLens-App und des Dienstes."}},
}


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return BRACKET.sub(r'<mark class="todo">[\1]</mark>', text)


def render(markdown: str, lang: str, drop_title: bool = False) -> str:
    """The draft's body as HTML blocks, one per line."""
    out, lines, i = [], markdown.replace("\r\n", "\n").split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip() == "---":
            i += 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if not (level == 1 and drop_title):
                out.append("<h%d>%s</h%d>" % (level, inline(line[level:].strip()), level))
            i += 1
        elif line.startswith(">"):
            out.append('<p class="msg msg-warning msg-banner"><span>%s</span></p>' % inline(line[1:].strip()))
            i += 1
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append("<li>%s</li>" % inline(lines[i][2:].strip()))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")])
                i += 1
            head = "".join('<th scope="col">%s</th>' % inline(cell) for cell in rows[0])
            body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(cell) for cell in row) for row in rows[2:])
            out.append('<div class="table-scroll" role="region" tabindex="0" aria-label="%s"><table><thead><tr>%s</tr></thead>'
                       "<tbody>%s</tbody></table></div>" % (TEXT[lang]["table"], head, body))
        else:
            block = []
            while i < len(lines) and lines[i].strip() and not re.match(r"[#>|]|- |---$", lines[i]):
                block.append(inline(lines[i].strip()))
                i += 1
            out.append("<p>%s</p>" % "<br>".join(block))
    return "\n".join("      " + block for block in out)


def page(lang: str, name: str, body: str, draft: bool) -> str:
    t = TEXT[lang]
    up = "../" if lang == "de" else ""
    en, de = ORIGIN + name + ".html", ORIGIN + "de/" + name + ".html"
    own = en if lang == "en" else de
    switch = [('<a class="tap" href="%s" lang="en" hreflang="en"%s data-lang-switch>EN</a>',
               name + ".html" if lang == "en" else "../" + name + ".html", lang == "en"),
              ('<a class="tap" href="%s" lang="de" hreflang="de"%s data-lang-switch>DE</a>',
               name + ".html" if lang == "de" else "de/" + name + ".html", lang == "de")]
    lang_links = '\n        <span aria-hidden="true">/</span>\n        '.join(
        tag % (href, ' aria-current="page"' if current else "") for tag, href, current in switch)
    legal = "\n".join('        <a class="tap" href="%s.html"%s>%s</a>'
                      % (key, ' aria-current="page"' if key == name else "", t[key])
                      for key in ("imprint", "privacy", "terms"))
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t[name]} · ChangeLens</title>
<meta name="description" content="{t["desc"][name]}">
{'<meta name="robots" content="noindex">' if draft else '<meta name="robots" content="index, follow">'}
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#F5F5F2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#121214" media="(prefers-color-scheme: dark)">
<link rel="canonical" href="{own}">
<link rel="alternate" hreflang="en" href="{en}">
<link rel="alternate" hreflang="de" href="{de}">
<link rel="alternate" hreflang="x-default" href="{en}">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/svg+xml" href="{up}assets/changelens-favicon-light.svg" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/svg+xml" href="{up}assets/changelens-favicon-dark.svg" media="(prefers-color-scheme: dark)">
<link rel="stylesheet" href="{up}site.css">
<script src="{up}site.js" defer></script>
</head>
<body>
<!-- Built by scripts/build_legal_pages.py from docs/legal. Edit the draft there, not this file. -->

<header class="topbar">
  <div class="wrap">
    <a class="logo" href="{t["home"]}" aria-label="{t["home_label"]}">
      <picture>
        <source srcset="{up}assets/changelens-logo-dark.svg" media="(prefers-color-scheme: dark)">
        <img src="{up}assets/changelens-logo-light.svg" width="179" height="40" alt="">
      </picture>
    </a>
    <nav class="topnav" aria-label="{t["page_nav"]}">
      <span class="lang">
        {lang_links}
      </span>
      <a class="tap" href="{t["home"]}#early-bird">{t["list"]}</a>
    </nav>
  </div>
</header>

<main>
  <div class="wrap">
    <article class="legal">
      <h1>{t[name]}</h1>
{body}
    </article>
  </div>
</main>

<footer class="footer">
  <div class="wrap">
    <div class="footer-inner">
      <nav class="footer-nav no-hyphens" aria-label="{t["legal_nav"]}">
{legal}
      </nav>
    </div>
  </div>
</footer>

</body>
</html>
"""


def read(name: str) -> str:
    return io.open(os.path.join(ROOT, "docs", "legal", name), encoding="utf-8").read()


def main() -> None:
    imprint = read("imprint.md").replace("\r\n", "\n")
    german, english = imprint.split("\n---\n", 1)
    english = re.sub(r"^## .*\n", "", english.strip(), count=1)  # the page title already says "Imprint"
    sources = {
        ("en", "privacy"): render(read("privacy-en.md"), "en", drop_title=True),
        ("de", "privacy"): render(read("privacy-de.md"), "de", drop_title=True),
        ("en", "terms"): render(read("terms-en.md"), "en", drop_title=True),
        ("de", "terms"): render(read("terms-de.md"), "de", drop_title=True),
        ("de", "imprint"): render(german, "de", drop_title=True),
        # The mandatory details exist in German only; the English page shows them first, marked as German.
        ("en", "imprint"): '      <div lang="de">\n' + render(german, "de", drop_title=True)
                           + "\n      </div>\n" + render(english, "en"),
    }
    for (lang, name), body in sources.items():
        target = os.path.join(ROOT, "web", TEXT[lang]["dir"], name + ".html")
        draft = 'class="todo"' in body or "msg-warning" in body
        io.open(target, "w", encoding="utf-8", newline="\n").write(page(lang, name, body, draft))
        print("%s%s.html %s" % (TEXT[lang]["dir"], name, "draft, noindex" if draft else "final"))


if __name__ == "__main__":
    main()
