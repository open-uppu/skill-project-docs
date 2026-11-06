"""Detect SVG use in reader-facing HTML and Markdown without changing files."""
import re
from html.parser import HTMLParser
from urllib.parse import unquote

SVG_REF = re.compile(r'(?:\.svg(?:[?#\s)"\']|$)|image/svg\+xml)', re.I)

class SVGDetector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = False
        self.raw = None

    def handle_starttag(self, tag, attrs):
        if tag == 'svg': self.found = True
        for key, value in attrs:
            if key in {'src', 'srcset', 'href', 'data', 'style', 'poster', 'xlink:href'} and SVG_REF.search(unquote(value or '')):
                self.found = True
        if tag in ('script', 'style'): self.raw = tag
        if tag == 'script' and any(key == 'src' and 'mermaid' in (value or '').lower() for key, value in attrs):
            self.found = True

    def handle_endtag(self, tag):
        if self.raw == tag: self.raw = None

    def handle_data(self, data):
        if self.raw and (SVG_REF.search(unquote(data)) or re.search(r'createElementNS\s*\(\s*["\']http://www\.w3\.org/2000/svg', data, re.I)):
            self.found = True


def uses_svg(text, markdown=False):
    parser = SVGDetector(); parser.feed(text); parser.close()
    if parser.found: return True
    return bool(markdown and re.search(r'!?\[[^\]]*\]\(\s*<?[^\s)>]*\.svg(?:[?#][^\s)>]*)?>?\s*\)', unquote(text), re.I))
