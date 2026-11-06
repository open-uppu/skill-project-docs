import unittest
from svg_policy import uses_svg

class SvgPolicyTests(unittest.TestCase):
    def test_detects_inline_external_and_encoded_svg(self):
        for text, markdown in [('<SVG></SVG>', False), ('<img src="plot%2Esvg?version=1">', False), ('<object data="data:image/svg+xml;base64,ABC"></object>', False), ('<style>x{background:url(plot.svg)}</style>', False), ('![chart](plots/x.svg)', True), ('<script src="mermaid.min.js"></script>', False)]:
            with self.subTest(text=text): self.assertTrue(uses_svg(text, markdown))

    def test_plain_text_and_html_visual_are_allowed(self):
        self.assertFalse(uses_svg('<html><div role="img">Chart</div><p>SVG is prohibited</p></html>'))
        self.assertFalse(uses_svg('[HTML chart](plot.html)', True))

if __name__ == '__main__': unittest.main()
