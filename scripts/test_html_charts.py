"""Charts use static HTML with source values, not SVG."""
import json
import tempfile
import unittest
from pathlib import Path
import presentation_charts

class HtmlChartTests(unittest.TestCase):
    def test_bar_and_area_use_html(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'data.json').write_text(json.dumps([{'x':1,'y':2},{'x':2,'y':4}]))
            for kind in ('bar','area'):
                chart=presentation_charts.render(root,{'id':'fixture','title':'Title','question':'What changes?','type':kind,'source':{'path':'data.json'},'x':'x','y':'y','unit':'ms','limitations':'Fixture only'})
                self.assertNotIn('<svg',chart['html'].lower())
                self.assertIn('role="img"',chart['html'])
                self.assertEqual(chart['rows'],[[1,2],[2,4]])

if __name__=='__main__': unittest.main()
