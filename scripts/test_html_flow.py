"""Regression checks for standalone HTML phase and failure flows."""
import json
import tempfile
import unittest
from pathlib import Path
import phase_visuals
import test_reporting

class HtmlFlowTests(unittest.TestCase):
    def test_phase_flow_is_html_without_svg(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'.project-docs').mkdir()
            (root/'.project-docs/config.json').write_text(json.dumps({'language':'English'}))
            tasks=[{'id':'1.1','uid':'one','title':'Prepare <safe>','mark':'/'}]
            output=phase_visuals.outputs(root,1,tasks)
            asset=root/'project/phases/phase-1/phase-flow.html'
            self.assertIn(asset,output['assets'])
            self.assertIn('Prepare &lt;safe&gt;',output['assets'][asset])
            self.assertIn('phase-flow.html',output['md_flow'])
            self.assertNotIn('<svg',output['html_flow'].lower())
            self.assertNotIn('<svg',output['assets'][asset].lower())

    def test_failure_flow_is_html_without_svg(self):
        case={'id':'case <1>','outcome':'failed','events':[],'failures':[{'stage':'test','kind':'assertion'}]}
        fragment=test_reporting.workflow_html(case,'sample')
        self.assertNotIn('<svg',fragment.lower())
        self.assertIn('Test body / assertion',fragment)
        self.assertIn('failed',fragment.lower())

if __name__=='__main__': unittest.main()
