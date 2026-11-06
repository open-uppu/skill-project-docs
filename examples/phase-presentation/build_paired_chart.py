#!/usr/bin/env python3
"""Generate a static HTML paired comparison from source JSON.

python3 build_paired_chart.py project/results/measurements.json project/results/charts/paired.html
"""
import hashlib
import html
import json
import math
import sys
from pathlib import Path

source, output = map(Path, sys.argv[1:3])
rows = json.loads(source.read_text(encoding='utf-8'))['paired']
values = [r[k] for r in rows for k in ('before_ms', 'after_ms')]
if not rows or len(rows)>8 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in values):
    raise SystemExit('use 1–8 scenarios with finite nonnegative millisecond values')
maximum=max(values) or 1
parts=['<!doctype html><html lang="en"><head><meta charset="utf-8">',
       '<meta name="project-docs-source-sha256" content="'+hashlib.sha256(source.read_bytes()).hexdigest()+'">',
       '<meta name="project-docs-generator-sha256" content="'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()+'">',
       '<title>Paired latency comparison</title></head><body>',
       '<div style="font-family:system-ui,sans-serif;max-width:960px;padding:16px;color:#273d45"><p>Baseline (gray) · Candidate (green) · Latency in ms; lower is faster.</p>']
for row in rows:
    before,after=(100*row[k]/maximum for k in ('before_ms','after_ms'))
    parts += ['<section style="margin:24px 0"><strong>'+html.escape(str(row['scenario']))+'</strong>',
              '<p>Baseline '+format(row['before_ms'],'g')+' ms · Candidate '+format(row['after_ms'],'g')+' ms</p>',
              '<div style="position:relative;margin:12px 8px;height:12px;background:#edf3f3">',
              f'<span style="position:absolute;top:4px;left:{min(before,after):.4f}%;width:{abs(after-before):.4f}%;height:4px;background:#b7c6c9"></span>',
              f'<span style="position:absolute;left:{before:.4f}%;top:0;width:12px;height:12px;transform:translateX(-50%);border-radius:50%;background:#63757b"></span>',
              f'<span style="position:absolute;left:{after:.4f}%;top:0;width:12px;height:12px;transform:translateX(-50%);border-radius:50%;background:#17665c"></span></div></section>']
parts.append('<p>Scale: 0–'+format(maximum,'g')+' ms. Synthetic fixture data.</p></div></body></html>')
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(''.join(parts),encoding='utf8')
