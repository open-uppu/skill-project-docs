"""Static chart primitives rendered using HTML and CSS only."""
import html
import math


def escape(value): return html.escape(str(value), quote=True)


def text(x, y, value, size=14, anchor='start', fill='#273d45'):
    shift={'start':'0', 'middle':'-50%', 'end':'-100%'}[anchor]
    return f'<span style="position:absolute;left:{x:.2f}px;top:{y:.2f}px;transform:translate({shift},-80%);font-size:{size}px;color:{escape(fill)};white-space:nowrap">{escape(value)}</span>'


def rect(x,y,w,h,fill,title=''):
    return f'<div title="{escape(title)}" style="position:absolute;left:{x:.3f}px;top:{y:.3f}px;width:{max(0,w):.3f}px;height:{max(0,h):.3f}px;background:{escape(fill)}"></div>'


def line(x1,y1,x2,y2,color='#cbd7db',width=1):
    length=math.hypot(x2-x1,y2-y1);angle=math.degrees(math.atan2(y2-y1,x2-x1))
    return f'<div style="position:absolute;left:{x1:.3f}px;top:{y1:.3f}px;width:{length:.3f}px;height:{width}px;background:{escape(color)};transform-origin:0 50%;transform:rotate({angle:.5f}deg)"></div>'


def dot(x,y,r,fill,title=''):
    return f'<div title="{escape(title)}" style="position:absolute;left:{x-r:.3f}px;top:{y-r:.3f}px;width:{r*2:.3f}px;height:{r*2:.3f}px;background:{escape(fill)};border-radius:50%"></div>'


def polyline(points,color,width=3):
    return ''.join(line(a,b,c,d,color,width) for (a,b),(c,d) in zip(points,points[1:]))


def area(points,color,width,height):
    polygon=','.join(f'{x/width*100:.5f}% {y/height*100:.5f}%' for x,y in points)
    return f'<div style="position:absolute;inset:0;background:{escape(color)};opacity:.18;clip-path:polygon({polygon})"></div>'


def chart(title,question,parts,height):
    return f'<div role="img" aria-label="{escape(title)}: {escape(question)}" style="position:relative;width:960px;height:{height:g}px;background:white;font-family:system-ui,sans-serif">'+''.join(parts)+'</div>'


def document(title,visual):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title></head><body><main><h1>'+escape(title)+'</h1><div style="overflow:auto">'+visual+'</div></main></body></html>'
