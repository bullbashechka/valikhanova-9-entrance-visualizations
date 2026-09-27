"""Create the offline review page and annotated engineering views (Pillow)."""
from pathlib import Path
import json, math, html, textwrap
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent; P=HERE/'previews'
D=json.loads((HERE/'geometry.json').read_text(encoding='utf-8'))
S=json.loads((HERE/'scene-section.json').read_text(encoding='utf-8'))
V=json.loads((HERE/'validation.json').read_text(encoding='utf-8'))
FONT=next(p for p in [Path('C:/Windows/Fonts/segoeui.ttf'),Path('/System/Library/Fonts/Supplemental/Arial.ttf')] if p.exists())
BOLD=next(p for p in [Path('C:/Windows/Fonts/segoeuib.ttf'),Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')] if p.exists())
def font(size,bold=False):return ImageFont.truetype(str(BOLD if bold else FONT),size)
def wrap(draw,text,width,f):
    words=text.split();lines=[];line=''
    for word in words:
        n=(line+' '+word).strip()
        if draw.textlength(n,font=f)>width and line:lines.append(line);line=word
        else:line=n
    return lines+[line]
def paragraphs(draw,text,x,y,width,size=24,color='#334155',bold=False):
    f=font(size,bold)
    for line in wrap(draw,text,width,f):draw.text((x,y),line,font=f,fill=color);y+=size+9
    return y

# The original file stays byte-for-byte unchanged. This is an explicitly labelled derivative.
src=Image.open(ROOT/'plans/section-1-common-areas.png').convert('RGB')
overlay=Image.blend(src,Image.new('RGB',src.size,'white'),.35)
draw=ImageDraw.Draw(overlay)
for line in S['segments']:draw.line([tuple(p) for p in line['points']],fill='#007fa5',width=3)
overlay.save(P/'06-source-overlay.png')

top=Image.open(P/'05-top.png').convert('RGB'); canvas=Image.new('RGB',(1880,1510),'#ffffff')
canvas.paste(top,(0,100));draw=ImageDraw.Draw(canvas)
draw.text((36,22),'Секция 1 · проверка геометрии',font=font(34,True),fill='#142735')
draw.text((36,65),'Концепция по проекту · высоты и условные детали перечислены справа',font=font(20),fill='#52616c')
labels=[(1,380,235),(2,309,100),(3,681,260),(4,112,670),(5,280,621),(6,443,675),(7,846,142)]
for n,x,y in labels:
    y+=100;draw.ellipse((x-17,y-17,x+17,y+17),fill='#163e50',outline='white',width=2)
    t=str(n);b=draw.textbbox((0,0),t,font=font(19,True));draw.text((x-(b[2]-b[0])/2,y-14),t,font=font(19,True),fill='white')
# Door swings: neutral review symbols, same hinge and side as the approved plan.
for oid,o in S['portals'].items():
    if o['kind'] in ['window','lift']:continue
    r=o['rect']; vertical=o['vertical']; length=(r[3]-r[1]) if vertical else (r[2]-r[0])
    mid=(r[0]+r[2])/2 if vertical else (r[1]+r[3])/2
    ends=[(0,length*.64),(length,length*.36)] if o.get('hinge')=='double' else [(length if o.get('hinge')=='end' else 0,length)]
    for offset,radius in ends:
        hinge=(mid,r[1]+offset) if vertical else (r[0]+offset,mid)
        sign=-1 if offset else 1;side=o.get('swing',1)
        points=[]
        for i in range(25):
            a=(math.pi/2)*i/24
            dx=side*radius*math.sin(a) if vertical else sign*radius*math.cos(a)
            dy=sign*radius*math.cos(a) if vertical else side*radius*math.sin(a)
            points.append((hinge[0]+dx,hinge[1]+dy+100))
        draw.line(points,fill='#ba641d',width=2)
        draw.line([(hinge[0],hinge[1]+100),points[-1]],fill='#ba641d',width=2)

x=1280;y=125
for title,body in [
    ('Пространства','1 Вестибюль · 2 Открытая колясочная · 3 Тамбур · 4 Коридор · 5 Лифт · 6 Лестница · 7 Наружная площадка'),
    ('Основные высоты','Потолок 3000 мм. Внутренние проёмы условно 2100 мм. Входные и тамбурные двери 2400 мм по ЭП.'),
    ('Условные элементы','Окна: подоконник 900 мм, верх 2400 мм. Навес: низ 2700 мм. Ограждения: высота 1000 мм. Подъёмник показан объёмом без выбора изделия.'),
    ('Наружные ступени','7 подъёмов по 150 мм между отметками −1,060 и −0,010. Проступи распределены по контуру плана.'),
    ('Лестничная клетка','Внутренний вход ведёт на площадку 0,000: через разворот +1,650 лестница поднимается ко второму этажу +3,300. Отдельная наружная дверь ведёт на площадку −1,050 и далее вниз к подвалу −2,250. Прямого перехода между этой дверью и площадкой 0,000 на разрезе нет. На виде сверху верхний марш закрывает нижний.'),
    ('Что проверить','Положение дверей, форму помещений, открытость колясочной, путь к лифту и лестнице. Оранжевые дуги показывают сторону открывания.'),
    ('Статус','Предварительная геометрия. Окончательное согласование сцены и дата начала срока визуализаций ещё не получены.')]:
    y=paragraphs(draw,title,x,y,555,24,'#142735',True)+8
    y=paragraphs(draw,body,x,y,555,21)+24
draw.text((36,1470),'Контур тамбура: 5,174 м². Подпись исходника: 5,50 м². Геометрия под площадь не изменена.',font=font(19),fill='#52616c')
canvas.save(P/'07-top-annotated.png')

segments=''.join(f'<line x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}"/>' for a,b in (s['points'] for s in S['segments']))
routes=''.join('<polyline points="'+' '.join(f'{x},{y}' for x,y in r)+'"/>' for r in S['routes'])
gallery=''.join(f'<figure><a href="previews/{c["name"]}.png"><img src="previews/{c["name"]}.png" alt="{html.escape(c["label"])}"></a><figcaption>{i+1:02d} · {html.escape(c["label"])}</figcaption></figure>' for i,c in enumerate(D['cameras']))
assumptions=''.join(f'<tr><td>{a["id"]}</td><th scope="row">{a["element"]}</th><td>{a["value"]}</td></tr>' for a in D['assumptions'])
page=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Секция 1 — геометрия для согласования</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f5f6;color:#20313e;font:16px/1.6 'Segoe UI',sans-serif}}main{{max-width:1320px;margin:auto;padding:40px 28px 70px}}header{{margin-bottom:30px}}.tag{{color:#8a4a14;font-size:14px;font-weight:650}}h1{{font-size:38px;line-height:1.2;margin:10px 0}}h2{{font-size:25px;margin:36px 0 16px}}p{{max-width:850px}}a{{color:#075b7b}}.links{{display:flex;gap:20px;flex-wrap:wrap}}.gallery{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}figure{{margin:0;background:white;border:1px solid #dfe5e8;border-radius:8px;overflow:hidden}}figure img{{width:100%;display:block}}figcaption{{padding:12px 18px;font-weight:600}}.panel{{background:white;padding:22px;border:1px solid #dfe5e8;border-radius:8px}}.compare{{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(240px,.65fr);gap:28px}}svg{{width:100%;height:auto;display:block}}label{{display:block;margin:14px 0}}input[type=range]{{display:block;width:100%}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{text-align:left;vertical-align:top;padding:14px;border-bottom:1px solid #dde4e8}}td:first-child{{white-space:nowrap;color:#596a75}}th{{font-weight:600;width:24%}}.note{{color:#5c6b74;font-size:14px}}.full{{width:100%;display:block}}@media(max-width:760px){{main{{padding:24px 14px}}h1{{font-size:29px}}.gallery,.compare{{grid-template-columns:1fr}}td,th{{padding:9px;font-size:14px}}}}</style>
<main><header><div class="tag">ЭТАП 2 · НА СОГЛАСОВАНИЕ · 25.09.2026</div><h1>Секция 1. Геометрия пространства</h1><p>Приблизительная модель по утверждённому плану и проектным исходникам. Нейтральные поверхности позволяют оценить форму помещений, двери и связи между зонами. Отделка и рабочее освещение относятся к следующему этапу.</p><div class="links"><a href="../../models/section-1/section-1-geometry.blend">Сцена Blender</a><a href="previews/07-top-annotated.png">Размеченный вид сверху</a><a href="README.md">Описание комплекта</a></div></header>
<div class="gallery">{gallery}</div>
<h2>Вид сверху и условные параметры</h2><a href="previews/07-top-annotated.png"><img class="full" src="previews/07-top-annotated.png" alt="Вид сверху с номерами зон, направлениями открывания и пояснениями"></a>
<h2>Проверка по исходному PNG</h2><div class="panel compare"><svg viewBox="0 0 {src.width} {src.height}" aria-label="Исходный план с сечением стен 3D-сцены"><image href="../../plans/section-1-common-areas.png" width="{src.width}" height="{src.height}"/><g id="mesh" fill="none" stroke="#0083af" stroke-width="2.5">{segments}</g><g id="routes" fill="none" stroke="#ad4b13" stroke-width="5" stroke-dasharray="10 7" style="display:none">{routes}</g></svg><aside><p><strong>Голубые линии</strong> — сечение реальных стен сцены на высоте 1,2 м, наложенное на исходный PNG.</p><label>Видимость контура сцены<input id="opacity" type="range" min="0" max="1" step=".05" value="1"></label><label><input id="paths" type="checkbox"> Показать проверенные оси проходов</label><p>Сравните стены, дверные проёмы и открытую границу колясочной. Верхние перемычки скрыты только для вида сверху, в редактируемой сцене они сохранены.</p><p class="note">Линии маршрутов показывают связность помещений. Они не являются расчётом нормативной ширины проходов или проверкой оборудования подъёмника.</p><a href="previews/06-source-overlay.png">Открыть статическое наложение</a></aside></div>
<h2>Допущения этой версии</h2><table><tbody>{assumptions}</tbody></table>
<h2>Статус проверки</h2><div class="panel"><p>Проверены свободные отверстия в стенах для 11 дверных проёмов и 4 оконных участков, связность основных маршрутов и размещение коляски. Сцена содержит отдельные редактируемые объекты; исходный PNG встроен в файл Blender и сохранён без изменений.</p><p>Фактических обмеров объекта нет. Согласование этой версии означает принятие приблизительной концепции по проекту. Дата начала отсчёта 3–4 рабочих дней на изображения фиксируется после отдельного подтверждения принятой основы.</p><div class="links"><a href="validation.json">Результаты автоматических проверок</a><a href="../../plans/section-1-common-areas.png">Утверждённый PNG</a></div></div></main>
<script>document.getElementById('opacity').addEventListener('input',e=>document.getElementById('mesh').style.opacity=e.target.value);document.getElementById('paths').addEventListener('change',e=>document.getElementById('routes').style.display=e.target.checked?'':'none');</script></html>'''
(HERE/'review.html').write_text(page,encoding='utf-8')
print('Created review.html and annotated views')
