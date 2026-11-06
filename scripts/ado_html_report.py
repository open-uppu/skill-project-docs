"""Validate and explicitly attach a self-contained HTML report to an ADO work item."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from provider_api import API, quote


class ReportHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_html = False
        self.style = False
        self.errors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html': self.has_html = True
        if tag in {'svg', 'img', 'object', 'embed', 'iframe', 'script', 'base', 'form'}:
            self.errors.append('unsupported element: ' + tag)
        if tag == 'link' and 'stylesheet' in attrs.get('rel', '').lower().split():
            self.errors.append('external stylesheet')
        if any('.svg' in str(v).lower() or 'image/svg' in str(v).lower() or re.search(r'url\s*\(', str(v), re.I) for v in attrs.values()):
            self.errors.append('external or SVG asset reference')
        if any(k.lower().startswith('on') or re.search(r'javascript\s*:', str(v), re.I) for k,v in attrs.items()):
            self.errors.append('active content')
        if tag == 'meta' and attrs.get('http-equiv','').lower() == 'refresh': self.errors.append('active content')
        if tag == 'style': self.style = True

    def handle_endtag(self, tag):
        if tag == 'style': self.style = False

    def handle_data(self, data):
        if self.style and re.search(r'url\s*\(|@import|expression\s*\(', data, re.I): self.errors.append('external or active CSS')


def validate_html(data):
    if len(data) > 60 * 1024 * 1024: raise ValueError('Report exceeds 60 MiB; check your project attachment limit.')
    try: text = data.decode('utf-8-sig')
    except UnicodeDecodeError: raise ValueError('Report must be UTF-8 HTML.') from None
    parsed = ReportHTML(); parsed.feed(text); parsed.close()
    if not parsed.has_html: raise ValueError('Report must be a complete HTML document.')
    if parsed.errors: raise ValueError('; '.join(sorted(set(parsed.errors))))


def publish(api, work_item, filename, data):
    if api.provider != 'azure-devops': raise ValueError('Connection must use Azure DevOps.')
    if not api.writing: raise ValueError('Publishing requires a write-enabled connection.')
    if not str(work_item).isdigit() or int(work_item) < 1: raise ValueError('Work item ID must be a positive integer.')
    if Path(filename).name != filename or not filename.lower().endswith(('.html', '.htm')): raise ValueError('Report must be an HTML file.')
    validate_html(data)
    checksum = hashlib.sha256(data).hexdigest()
    attachment_name = 'project-docs-' + checksum + '-' + filename
    prefix = api.prefix()
    item_path = prefix + '/workitems/' + quote(work_item) + '?$expand=relations&api-version=7.1'
    item = api.json('GET', item_path)
    if str(item.get('id')) != str(work_item) or not isinstance(item.get('rev'), int): raise ValueError('Unexpected work item response.')
    for relation in item.get('relations', []):
        if relation.get('rel') == 'AttachedFile' and relation.get('attributes', {}).get('name') == attachment_name:
            existing = api.request('GET', relation['url'], binary=True)[0]
            if hashlib.sha256(existing).hexdigest() != checksum: raise ValueError('Existing attachment checksum does not match its name.')
            return {'uploaded': False, 'sha256': checksum, 'url': relation['url'], 'revision': item['rev']}
    result = api.json('POST', prefix+'/attachments?fileName='+quote(attachment_name)+'&api-version=7.1', data, content_type='application/octet-stream')
    url = result['url']
    actual = api.request('GET', url, binary=True)[0]
    if hashlib.sha256(actual).hexdigest() != checksum: raise ValueError('Uploaded attachment checksum mismatch.')
    patch = [{'op': 'test', 'path': '/rev', 'value': item['rev']},
             {'op': 'add', 'path': '/relations/-', 'value': {'rel': 'AttachedFile', 'url': url, 'attributes': {'name': attachment_name}}}]
    api.json('PATCH', prefix+'/workitems/'+quote(work_item)+'?api-version=7.1', patch, content_type='application/json-patch+json')
    checked = api.json('GET', item_path)
    if not any(r.get('rel') == 'AttachedFile' and r.get('url') == url for r in checked.get('relations', [])):
        raise ValueError('Attachment was not present in the read-back work item.')
    actual = api.request('GET', url, binary=True)[0]
    if hashlib.sha256(actual).hexdigest() != checksum: raise ValueError('Uploaded attachment checksum mismatch.')
    return {'uploaded': True, 'sha256': checksum, 'url': url, 'revision': checked['rev']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--connection', required=True)
    parser.add_argument('--work-item', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Upload and attach the report to the named work item.')
    args=parser.parse_args();root=args.root.resolve();path=(root/args.report).resolve()
    if not path.is_relative_to(root) or not path.is_file(): parser.error('Report must be a file inside the project root.')
    if not args.work_item.isdigit() or int(args.work_item) < 1: parser.error('Work item ID must be a positive integer.')
    if path.suffix.lower() not in ('.html', '.htm'): parser.error('Report must be an HTML file.')
    data=path.read_bytes();validate_html(data)
    config=json.loads((root/'.project-docs/config.json').read_text(encoding='utf-8'))
    connection=config['integrations']['connections'][args.connection]
    if connection.get('provider') != 'azure-devops': parser.error('Connection must use Azure DevOps.')
    if not args.apply:
        print(json.dumps({'mode':'dry-run','work_item':args.work_item,'report':str(path.relative_to(root)),'sha256':hashlib.sha256(data).hexdigest()}));return
    result=publish(API(args.connection,connection,writing=True),args.work_item,path.name,data)
    print(json.dumps(result))


if __name__=='__main__':main()
