"""ADO HTML report publishing tests; no remote connections."""
import hashlib
import unittest
from unittest import mock
import ado_html_report as reports

class FakeAPI:
    provider='azure-devops'
    writing=True
    def __init__(self): self.revision=2; self.relations=[];self.files={};self.calls=[]
    def prefix(self):return '/org/project/_apis/wit'
    def json(self,method,path,body=None,**kwargs):
        self.calls.append((method,path,body))
        if method=='GET':return {'id':7,'rev':self.revision,'relations':list(self.relations)}
        if method=='POST':self.files['https://dev.azure.com/org/attachment']=body;return {'url':'https://dev.azure.com/org/attachment'}
        if method=='PATCH':
            if body[0]['value']!=self.revision:raise RuntimeError('revision conflict')
            self.relations.append(body[1]['value']);self.revision+=1;return {'id':7,'rev':self.revision}
        raise AssertionError(method)
    def request(self,method,path,**kwargs):return self.files[path],{}

class AdoHtmlReportTests(unittest.TestCase):
    def test_rejects_svg_and_nonstandalone_resources(self):
        for data in (b'<html><svg></svg></html>',b'<html><script>bad()</script></html>',b'<html><p onclick=bad()>x</p></html>',b'<html><iframe src=x></iframe></html>',b'<html><img src="plot.svg"></html>',b'<link rel="stylesheet" href="external.css">',b'<style>body{background:url(a.png)}</style>'):
            with self.subTest(data=data),self.assertRaises(ValueError): reports.validate_html(data)
        reports.validate_html(b'<!doctype html><html><body><h1>Report</h1><p>3 passed</p></body></html>')
    def test_publish_is_revision_guarded_verified_and_idempotent(self):
        api=FakeAPI(); data=b'<!doctype html><html><body><h1>Report</h1></body></html>'
        first=reports.publish(api,'7','report.html',data)
        self.assertTrue(first['uploaded']);self.assertEqual(first['sha256'],hashlib.sha256(data).hexdigest())
        self.assertEqual([x[0] for x in api.calls],['GET','POST','PATCH','GET'])
        self.assertEqual(api.calls[2][2][0],{'op':'test','path':'/rev','value':2})
        before=len(api.calls);second=reports.publish(api,'7','report.html',data)
        self.assertFalse(second['uploaded']);self.assertEqual([x[0] for x in api.calls[before:]],['GET'])
    def test_concurrent_edit_is_not_overwritten(self):
        api=FakeAPI();original=api.json
        def change(method,path,body=None,**kwargs):
            if method=='PATCH':api.revision+=1
            return original(method,path,body,**kwargs)
        api.json=change
        with self.assertRaisesRegex(RuntimeError,'revision conflict'):
            reports.publish(api,'7','report.html',b'<html><body>ok</body></html>')
        self.assertEqual(api.relations,[])

if __name__=='__main__':unittest.main()
