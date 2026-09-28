"""Build the offline review page only from a verified, current render set."""
from pathlib import Path
import json,html,hashlib
from PIL import Image
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
style=json.loads((HERE/'style.json').read_text());v=json.loads((HERE/'validation.json').read_text());r=json.loads((HERE/'render-manifest.json').read_text())
sha=hashlib.sha256((ROOT/'models/section-1/section-1-finish.blend').read_bytes()).hexdigest()
assert v['all_pass'] and v['blend_sha256']==r['blend_sha256']==sha
assert r['style_sha256']==hashlib.sha256((HERE/'style.json').read_bytes()).hexdigest()
names=[c['name'] for c in style['cameras']]+['05-top']
for n in names:
    p=HERE/'previews'/f'{n}.png'
    assert r['images'][p.name]==hashlib.sha256(p.read_bytes()).hexdigest()
    assert max(Image.open(p).size)>=1920
descriptions=[
    'Вход в вестибюль. Слева — дверь к лестнице; справа — проход через остеклённую дверь в коридор.',
    'Открытая зона колясочной: защищённый низ стены, древесный акцент и одна коляска для масштаба.',
    'Лифт и продолжение коридора. Тёмный плинтус и полоса пола поддерживают единый рисунок.',
    'Основной вход выделен обрамлением, номером секции и светом под навесом. Левая дверь ведёт к нижнему уровню.'
]
gallery=''.join(f'''<figure id="view-{i+1}"><a href="previews/{c['name']}.png"><img src="previews/{c['name']}.png" width="1920" height="1280" alt="{html.escape(c['label'])}"></a><figcaption><span class="num">0{i+1}</span><div><h2>{html.escape(c['label'])}</h2><p>{descriptions[i]}</p></div></figcaption></figure>''' for i,c in enumerate(style['cameras']))
labels={'wall':'Стены','floor':'Основной пол','entry_floor':'Тамбур','wood':'Дерево','charcoal':'Детали','outdoor_floor':'Площадка'}
palette=''.join(f'<div class="swatch"><span style="background:{style["palette"][key]}"></span><strong>{label}</strong><small>{style["palette"][key]}</small></div>' for key,label in labels.items())
pins=[(1,455,248,'Вестибюль'),(2,281,106,'Колясочная'),(3,676,265,'Тамбур'),(4,113,700,'Коридор'),(5,282,450,'Лифт'),(6,442,470,'Лестница'),(7,875,143,'Наружная площадка')]
markers=''.join(f'<span class="pin" style="left:{(x+10)/1040*100:.3f}%;top:{(y+4)/1220*100:.3f}%" aria-label="{label}">{n}</span>' for n,x,y,label in pins)
legend=''.join(f'<li><b>{n}</b>{label}</li>' for n,x,y,label in pins)
page=f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Секция 1 — отделка и свет</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f0e9;color:#302d29;font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}main{{max-width:1400px;margin:auto;padding:44px 32px 70px}}header{{max-width:980px;margin-bottom:36px}}.eyebrow{{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#796347}}h1{{font:normal clamp(32px,4.5vw,54px)/1.12 Georgia,serif;margin:16px 0}}header p{{max-width:810px;color:#625c52}}a{{color:inherit;text-underline-offset:4px}}nav{{display:flex;gap:10px 24px;flex-wrap:wrap;margin-top:24px;font-size:14px}}.gallery{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}figure{{margin:0;background:#fffdf9;border:1px solid #e2dbcf}}figure img{{width:100%;height:auto;display:block}}figcaption{{display:flex;gap:18px;padding:21px}}.num{{color:#8b7355;font-size:13px;line-height:28px}}h2{{font-size:19px;line-height:1.4;margin:0 0 7px}}figcaption p{{font-size:14px;line-height:1.5;margin:0;color:#6c6459}}section{{margin-top:54px}}h3{{font:normal 30px/1.2 Georgia,serif;margin:0 0 22px}}.top-layout{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(240px,.75fr);gap:36px;align-items:start}}.top-image{{position:relative;background:#e7e2d9}}.top-image img{{width:100%;display:block}}.pin{{position:absolute;transform:translate(-50%,-50%);display:grid;place-items:center;width:28px;height:28px;background:#3d493f;color:white;border:2px solid white;border-radius:50%;font-size:12px;font-weight:bold}}.legend{{list-style:none;padding:0;margin:0 0 28px}}.legend li{{display:flex;gap:13px;margin:10px 0}}.legend b{{font-size:13px;width:24px;color:#66745f}}.note{{font-size:14px;color:#71685c;max-width:580px}}.palette{{display:grid;grid-template-columns:repeat(6,1fr);gap:14px}}.swatch{{display:flex;flex-direction:column;gap:4px}}.swatch span{{display:block;height:90px;border:1px solid #d1c9bd}}.swatch strong{{font-size:14px}}small{{font-size:12px;color:#75695a}}.ref-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.ref-grid img{{display:block;width:100%;height:270px;object-fit:contain;background:#e9e3d8}}.review{{padding:26px 30px;background:#e9e3d8;border-left:4px solid #8b7355}}.review p{{margin:0;max-width:900px}}.review h3{{font-size:26px;margin-bottom:14px}}footer{{margin-top:50px;border-top:1px solid #d6cdbc;padding-top:22px;font-size:13px;color:#71685c}}@media(max-width:800px){{main{{padding:26px 16px 45px}}.gallery,.top-layout{{grid-template-columns:1fr}}.palette{{grid-template-columns:repeat(3,1fr)}}.ref-grid img{{height:210px}}.top-layout{{gap:20px}}figcaption{{padding:16px}}}}@media(max-width:420px){{.ref-grid{{grid-template-columns:1fr}}.pin{{width:24px;height:24px}}}}
</style></head><body><main>
<header><div class="eyebrow">Этап 3 · Принят как основа концепции</div><h1>Секция 1.<br>Отделка и свет</h1><p>Тёплые светлые стены, бежевый камень, сдержанные древесные акценты и графитовые детали. Открытая колясочная остаётся частью вестибюля; высота потолка — 3 м.</p><nav><a href="#images">Четыре ракурса</a><a href="#top">Вид сверху</a><a href="#palette">Палитра</a><a href="#references">Референсы</a><a href="../../models/section-1/section-1-finish.blend">Сцена Blender</a></nav></header>
<div id="images" class="gallery">{gallery}</div>
<section id="top"><h3>Расположение отделки</h3><div class="top-layout"><div class="top-image"><a href="previews/05-top.png"><img src="previews/05-top.png" alt="Ортогональный цветной вид секции 1 сверху"></a>{markers}</div><aside><ol class="legend">{legend}</ol><p>Более тёмный пол выделяет тамбур. Колясочная соединена с вестибюлем общим полом, без перегородки и порога. Полоса коридора прерывается у дверей.</p><p class="note">Для этого вида потолки и верхние части стен скрыты. В редактируемой сцене они сохранены. Первый этаж и нижняя наружная дверь имеют разные маршруты.</p><a href="../../plans/section-1-common-areas.png">Утверждённый исходный план</a></aside></div></section>
<section id="palette"><h3>Палитра первого варианта</h3><div class="palette">{palette}</div><p class="note">Это цветовые ориентиры без освещения. На ракурсах оттенки меняются под влиянием света и отражений. Для подбора материалов нужны образцы.</p><a href="materials.md">Материалы и места применения</a></section>
<section id="references"><h3>Утверждённые ориентиры</h3><div class="ref-grid"><a href="../../references/albina-lobby.jpeg"><img src="../../references/albina-lobby.jpeg" alt="Референс вестибюля: дерево, светлые стены и линейный свет"></a><a href="../../references/albina-corridor.jpeg"><img src="../../references/albina-corridor.jpeg" alt="Референс коридора: тёмный плинтус и полоса пола"></a></div></section>
<section class="review"><h3>Основа для секций 2 и 3</h3><p>Первый вариант принят 28.09.2026: палитра, древесные акценты, тёплый свет и навигация переносятся с адаптацией к планировкам. Общие корректировки собираются на этапе 6.</p></section>
<footer><p>Геометрия сохранена по согласованной основе этапа 2. Размеры и отдельные детали остаются оценочными; одна коляска показывает масштаб, без утверждения вместимости. Это концепция оформления, а не рабочая строительная документация.</p><a href="README.md">Состав комплекта и воспроизведение</a> · <a href="validation.json">Проверка сцены</a></footer>
</main></body></html>'''
(HERE/'review.html').write_text(page,encoding='utf-8')
print('REVIEW_CREATED')
