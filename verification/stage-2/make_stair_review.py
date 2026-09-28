"""Vector engineering views from meshes exported by the reopened Blender file."""
from pathlib import Path
import json,html
HERE=Path(__file__).resolve().parent
R=json.loads((HERE/'stair-review.json').read_text())
D=json.loads((HERE/'geometry.json').read_text())
P=HERE/'previews';sx,sy=R['scale']
colors={'ascending':'#30877a','upper return':'#3276b7','visible lower':'#b57032'}
def txt(x,y,s,size=18,color='#20313e'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{html.escape(s)}</text>'
def poly(points,color,opacity=1):
    return '<polygon points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in points)+f'" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="1.5"/>'
def shell(w,h,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#fff"/><g font-family="Arial,sans-serif">'+body+'</g></svg>'
def hull(points):
    pts=sorted(set(points))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[];hi=[]
    for p in pts:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return lo[:-1]+hi[:-1]
# Project both parallel flights onto a common longitudinal plane, matching the section reading direction.
xmap=lambda y:100+(865.3-y)*1.75
zmap=lambda z:535-z*115
body=txt(40,44,'Секция 1 · продольная проекция лестницы',28)
body+=txt(40,77,'Контуры из сохранённой модели. Параллельные марши совмещены в одной проекции.',18,'#52616c')
for key in ['basement','lower_entry','first_floor','turn','second_floor']:
    z=R['levels_m'][key];v=zmap(z)
    body+=f'<line x1="65" y1="{v}" x2="1220" y2="{v}" stroke="#cbd5dc" stroke-dasharray="5 5"/>'
    body+=txt(1230,v+5,f'{z:+.3f}'.replace('.',','),18)
for mesh in R['meshes']:
    if mesh['name'].endswith('second-floor corridor'):continue
    c=colors.get(mesh.get('flight_id'),'#526977')
    points=hull([(xmap(-v[1]/sy),zmap(v[2])) for v in mesh['vertices']])
    body+=poly(points,c,.30 if mesh.get('level') else .50)
body+=txt(85,142,'+3,300 → внутренний коридор; наружная дверь здесь не предусмотрена',19,'#3276b7')
body+=txt(890,515,'Из вестибюля',17,'#30877a')
body+=txt(875,635,'Дверь с улицы → −1,050',17,'#b57032')
body+=txt(80,837,'Верх: 2 × 11 подъёмов. Низ: 8 подъёмов. Высота подъёма 150 мм — принята для концепции.',18)
body+=txt(80,869,'Толщина маршей 150 мм условно. Источник вертикальной схемы: ЭП, страницы 13, 19, 22.',18,'#52616c')
(P/'08-stair-section.svg').write_text(shell(1390,900,body))
body=txt(35,42,'Секция 1 · маршруты по уровням',28)
body+=txt(35,75,'Проекции фактических площадок и ступеней. Серые линии — сечения стен с проёмами.',18,'#52616c')
configs=[('Нижний вход и подвал',{'lower_entry','basement'},{'visible lower'},'outside_to_basement'),('Первый этаж и разворот',{'first_floor','turn'},{'ascending'},'first_to_second'),('Второй этаж и коридор',{'second_floor','turn'},{'upper return'},'first_to_second')]
for j,(title,levels,flights,routeid) in enumerate(configs):
    left=25+j*455
    body+=txt(left+12,120,title,22)
    def xy(x,y):return (left+18+(x-24.4)*.60,175+(y-300)*.60)
    # Actual wall sections retain door/window openings; clip to this panel's local fragment.
    body+=f'<defs><clipPath id="panel{j}"><rect x="{left+10}" y="175" width="433" height="360"/></clipPath></defs><g clip-path="url(#panel{j})">'
    for segment in R['wall_sections'][j]['segments']:
        (a,b),(c,d)=[xy(*p) for p in segment]
        body+=f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="#bbc5cb" stroke-width="1.5"/>'
    body+='</g>'
    for mesh in R['meshes']:
        if mesh.get('level') not in levels and mesh.get('flight_id') not in flights:continue
        points=hull([xy(v[0]/sx,-v[1]/sy) for v in mesh['vertices']])
        body+=poly(points,colors.get(mesh.get('flight_id'),'#95aab5'),.50)
    route=next(r for r in R['routes'] if r['id']==routeid)
    points=route['points']
    if j==1:points=points[:6]
    if j==2:points=points[5:]
    body+='<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in [xy(p[0],p[1]) for p in points])+f'" fill="none" stroke="{colors["visible lower"] if j==0 else "#163e50"}" stroke-width="3"/>'
    for i,(a,b) in enumerate(zip(points,points[1:])):
        x0,y0=xy(a[0],a[1]);x1,y1=xy(b[0],b[1]);dx=x1-x0;dy=y1-y0;l=(dx*dx+dy*dy)**.5
        if l<20:continue
        x=x0+dx*.65;y=y0+dy*.65;ux=dx/l;uy=dy/l
        body+=poly([(x,y),(x-ux*10-uy*4,y-uy*10+ux*4),(x-ux*10+uy*4,y-uy*10-ux*4)],'#163e50')
    captions=[['Улица → −1,050 → −2,250','Отдельный нижний маршрут.'],['Вестибюль 0,000 → +1,650','Сохранены дверь и контуры первого этажа.'],['+1,650 → +3,300 → коридор','Верхняя площадка открыта в коридор.']][j]
    for i,line in enumerate(captions):body+=txt(left+12,630+i*29,line,17)
body+=txt(35,732,'Незавершённые края коридора и подвала — границы моделируемого фрагмента, а не дверные проёмы.',18,'#52616c')
body+=txt(35,765,'План типового этажа совмещён с первым по контуру лестничной клетки и шахты лифта.',18,'#52616c')
(P/'09-stair-levels.svg').write_text(shell(1400,805,body))
print('Created mesh-based stair section and level plans')
