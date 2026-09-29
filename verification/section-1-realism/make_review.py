"""Package only the three accepted-for-review pilot renders, with provenance checks."""
from pathlib import Path
from PIL import Image
from html.parser import HTMLParser
import hashlib
import json
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT/'deliverables/section-1-realism'
CFG = json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
SCENE = ROOT/'models/section-1/section-1-realism.blend'
hashfile = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
validation = json.loads((HERE/'validation.json').read_text(encoding='utf-8'))
visual = json.loads((HERE/'visual-review.json').read_text(encoding='utf-8'))
assert validation['all_pass'] and validation['blend_sha256'] == hashfile(SCENE)
assert visual['passed'] and visual['blend_sha256'] == hashfile(SCENE)
(OUT/'images').mkdir(parents=True, exist_ok=True)
(OUT/'references').mkdir(exist_ok=True)
records = []
for shot in CFG['pilot_outputs']:
    image = HERE/'previews'/(shot['name']+'.png')
    info = json.loads(image.with_suffix('.json').read_text(encoding='utf-8'))
    assert info['blend_sha256'] == hashfile(SCENE)
    assert info['settings_sha256'] == hashfile(HERE/'settings.json')
    assert info['sha256'] == hashfile(image) == visual['images'][image.name]
    with Image.open(image) as im:
        assert im.size == (3200, 2133)
        assert max(channel[1] for channel in im.getextrema()) > 180
    shutil.copy2(image, OUT/'images'/image.name)
    records.append(info)
assert records[0]['camera_matrix'] == records[1]['camera_matrix']
for name in ('albina-lobby.jpeg', 'albina-corridor.jpeg'):
    shutil.copy2(ROOT/'references'/name, OUT/'references'/name)
shutil.copy2(ROOT/'verification/section-1-revision/previews/01-entry.png', OUT/'references/previous-entry.png')
shutil.copy2(SCENE, OUT/'section-1-realism.blend')
for file in ('settings.json', 'asset-register.json', 'validation.json', 'visual-review.json', 'render_scene.py'):
    shutil.copy2(HERE/file, OUT/file)
(OUT/'render-manifest.json').write_text(json.dumps({'stage': 'pilot_pending_user_review', 'renders': records}, indent=2), encoding='utf-8')

html = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Секция 1 — образец качества</title>
<style>
:root{--ink:#272b28;--muted:#666b65;--paper:#f3f1eb;--line:#d7d8cf;--accent:#555b48}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 Georgia,serif}header,main,footer{max-width:1440px;margin:auto;padding:36px 5vw}header{padding-top:52px;padding-bottom:26px}.eyebrow,nav,button,.meta,.label{font-family:Arial,sans-serif}.eyebrow{font-size:12px;letter-spacing:.17em;text-transform:uppercase;color:var(--muted)}h1{font-weight:400;font-size:clamp(34px,4.8vw,65px);line-height:1.07;margin:17px 0}h2{font-weight:400;font-size:32px;margin:0 0 12px}p{max-width:760px}header p{color:var(--muted);margin:15px 0 0}nav{display:flex;gap:24px;flex-wrap:wrap;margin-top:26px;font-size:14px}a{color:inherit;text-underline-offset:4px}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:18px}.label{font-size:12px;color:var(--muted);letter-spacing:.06em}.tabs{display:flex;border:1px solid var(--line);padding:4px;border-radius:4px;gap:3px}button{background:none;border:0;padding:10px 19px;cursor:pointer;color:var(--ink);font-size:14px;border-radius:2px}button[aria-pressed=true]{background:var(--ink);color:#fff}button:focus-visible,a:focus-visible{outline:2px solid #ad815d;outline-offset:4px}.hero{display:block;width:100%;height:auto;background:#ddd}.caption{display:flex;justify-content:space-between;gap:24px;margin-top:14px;font-size:14px;color:var(--muted)}section{margin-bottom:58px}.detail{display:grid;grid-template-columns:1.4fr 1fr;gap:35px;align-items:center}.detail img,.refs img,.previous img{display:block;width:100%;height:auto}.detail p{color:var(--muted)}.refs{display:grid;grid-template-columns:1.35fr 1fr;gap:24px;align-items:start}.refs figure{margin:0}.refs img{max-height:780px;object-fit:contain;object-position:top left}.refs figcaption{font-size:14px;color:var(--muted);margin-top:12px}.previous{display:block;max-width:880px}.checklist{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;border-top:1px solid var(--line);padding-top:25px}.checklist h3{font-size:21px;font-weight:400;margin:0}.checklist p{font-size:15px;color:var(--muted)}footer{border-top:1px solid var(--line);font-size:13px;color:var(--muted);padding-top:25px;padding-bottom:40px}.meta{font-size:12px}.hidden{display:none}@media(max-width:700px){header,main,footer{padding-left:20px;padding-right:20px}.toolbar{align-items:start;flex-direction:column}.detail,.refs,.checklist{grid-template-columns:1fr}.caption{flex-direction:column;gap:6px}section{margin-bottom:38px}.refs img{max-height:none}h2{font-size:28px}nav{gap:18px}}
</style></head><body>
<header><div class="eyebrow">Валиханова, 9 · Секция 1 · 29 сентября 2026</div><h1>Материалы. Свет. Детали.</h1><p>Три изображения для оценки нового качества визуализации. Дневная и вечерняя версии показывают одну отделку с одного ракурса.</p><nav><a href="#overview">Общий вид</a><a href="#detail">Деталь двери</a><a href="#references">Референсы</a><a href="#previous">Предыдущий вариант</a></nav></header>
<main>
<section id="overview"><div class="toolbar"><span class="label">01 / ВЕСТИБЮЛЬ</span><div class="tabs" aria-label="Освещение"><button type="button" data-mode="day" aria-pressed="true">День</button><button type="button" data-mode="evening" aria-pressed="false">Вечер</button></div></div>
<a id="hero-link" href="images/01-overview-day.png"><img id="hero" class="hero" src="images/01-overview-day.png" width="3200" height="2133" alt="Дневной вид вестибюля с деревянной дверью и прозрачными стеклянными дверями"></a>
<div class="caption"><span id="mode-caption">Дневная подача с включёнными светильниками.</span><span>Нажмите на изображение для просмотра оригинала.</span></div>
<noscript><p><a href="images/02-overview-evening.png">Открыть вечерний вариант</a></p></noscript></section>
<section class="detail" id="detail"><a href="images/03-door-detail.png"><img src="images/03-door-detail.png" width="3200" height="2133" alt="Крупный план деревянной двери: рисунок дерева, рельефная вставка и чёрная ручка"></a><div><span class="label">02 / ДЕТАЛЬ</span><h2>Дерево и графит</h2><p>Естественный рисунок тёмного дерева, сдержанная рельефная вставка и чёрная фурнитура. Панель над дверью продолжает оформление до потолка.</p><p>Стеклянные двери сохраняют прозрачность и раскрывают соседнее пространство.</p></div></section>
<section id="references"><h2>Ориентиры оформления</h2><p>Исходные референсы для сопоставления дверей, материалов и характера освещения.</p><div class="refs"><figure><a href="references/albina-lobby.jpeg"><img src="references/albina-lobby.jpeg" alt="Референс Альбины — вестибюль" loading="lazy"></a><figcaption>Вестибюль: светлые стены, графитовый профиль, прозрачное стекло.</figcaption></figure><figure><a href="references/albina-corridor.jpeg"><img src="references/albina-corridor.jpeg" alt="Референс Альбины — коридор" loading="lazy"></a><figcaption>Коридор: деревянная дверь с продолжением до потолка.</figcaption></figure></div></section>
<section id="previous"><h2>Предыдущий вариант</h2><p>Сохранён для сравнения. Положение камеры в новом обзоре скорректировано.</p><a class="previous" href="references/previous-entry.png"><img src="references/previous-entry.png" alt="Прежняя визуализация вестибюля" loading="lazy"></a></section>
<section><h2>Что оцениваем на этом этапе</h2><div class="checklist"><div><h3>Сходство</h3><p>Характер дверей, оттенок дерева и сочетание со светлыми стенами.</p></div><div><h3>Свет</h3><p>Читаемость отделки днём и атмосфера вечернего варианта.</p></div><div><h3>Детали</h3><p>Фактура поверхностей, фурнитура, стекло и чёткость изображения.</p></div></div></section>
</main><footer><p>Образец для согласования качества. Расширенный комплект, коляска и велосипед — после принятия образца. Концепция сохраняет оценочные размеры и условную модель подъёмника.</p><p class="meta"><a href="section-1-realism.blend">Редактируемая сцена Blender</a> · <a href="README.md">Состав комплекта</a> · <a href="materials.md">Материалы</a></p></footer>
<script>
const modes={day:{file:'images/01-overview-day.png',caption:'Дневная подача с включёнными светильниками.',alt:'Дневной вид вестибюля'},evening:{file:'images/02-overview-evening.png',caption:'Вечерняя подача. Материалы и ракурс сохранены.',alt:'Вечерний вид вестибюля'}};
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{const selected=modes[button.dataset.mode];document.getElementById('hero').src=selected.file;document.getElementById('hero').alt=selected.alt;document.getElementById('hero-link').href=selected.file;document.getElementById('mode-caption').textContent=selected.caption;document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));}));
</script></body></html>'''
(OUT/'index.html').write_text(html, encoding='utf-8')
(OUT/'README.md').write_text('''# Секция 1 — пробный набор нового качества

Откройте index.html в браузере. Интернет не нужен.

Три изображения по 3200 × 2133 px: дневной и вечерний обзор с одного ракурса, дневной крупный план деревянной двери. Все изображения рассчитаны непосредственно из приложенной сцены Blender.

Это образец для принятия визуального качества пользователем. После принятия готовится расширенный комплект из 23 изображений. Детализированная коляска и велосипед относятся к следующей части работ.

Сцена section-1-realism.blend содержит упакованные текстуры. Сохранён дневной режим; параметры обоих режимов и камер находятся в settings.json. Проверки и происхождение изображений записаны в validation.json, visual-review.json и render-manifest.json.

Архитектурная основа сохраняет последние исправления секции 1. Фактические строительные размеры и конкретное оборудование этим набором не подтверждаются.
''', encoding='utf-8')
(OUT/'materials.md').write_text('''# Материалы пробного набора

- Стены: светлая матовая окраска с мелкой фактурой поверхности.
- Глухие двери: тёмный коричневый древесный декор с вертикальным рисунком, тёмная рельефная вставка, графитовые ручки и коробки. Над дверью — неподвижная декоративная панель до потолка.
- Акцентные панели: древесный декор из той же группы; существующие вставки у лифта и в колясочной сохранены.
- Стеклянные двери: прозрачное стекло с тёмными профилями и фурнитурой. Вставка подвальной двери остаётся матовой.
- Пол: матовый бежевый каменный рисунок; сохранены модуль 600 × 600 мм, швы и тёмное обрамление.
- Свет: дневная и вечерняя подача с тёплыми линейными светильниками. Это визуальная настройка, без светотехнического расчёта.

Текстура дерева: Oak Veneer 01, Poly Haven, CC0 — https://polyhaven.com/a/oak_veneer_01. Исходные карты сохранены, оттенок скорректирован в материале сцены. Подробности в asset-register.json.

Категории и внешний вид материалов не являются спецификацией конкретных товаров.
''', encoding='utf-8')

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('src', 'href') and value and not value.startswith(('#', 'https:', 'http:')):
                self.links.append(value)

parser=Links()
parser.feed(html)
assert all((OUT/path).is_file() for path in parser.links)
zip_path = ROOT/'deliverables/section-1-realism-pilot.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            archive.write(path, Path(OUT.name)/path.relative_to(OUT))
with zipfile.ZipFile(zip_path) as archive:
    assert archive.testzip() is None
    for path in OUT.rglob('*'):
        if path.is_file():
            assert hashlib.sha256(archive.read((Path(OUT.name)/path.relative_to(OUT)).as_posix())).hexdigest() == hashfile(path)
images_zip = ROOT/'deliverables/section-1-realism-previews.zip'
image_names = {
    '01-overview-day.png': '01-Дневной-обзор.png',
    '02-overview-evening.png': '02-Вечерний-обзор.png',
    '03-door-detail.png': '03-Деталь-двери.png',
}
with zipfile.ZipFile(images_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for source, name in image_names.items():
        archive.write(OUT/'images'/source, name)
with zipfile.ZipFile(images_zip) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(image_names.values())
    for source, name in image_names.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == hashfile(OUT/'images'/source)
(HERE/'review-validation.json').write_text(json.dumps({'passed': True, 'images': len(records),
    'links_checked': len(parser.links), 'same_day_evening_camera': True,
    'zip_crc_and_contents_match': True, 'zip_sha256': hashfile(zip_path),
    'previews_zip_crc_and_contents_match': True, 'previews_zip_sha256': hashfile(images_zip),
    'visual_approval': 'pending_user_review'}, indent=2), encoding='utf-8')
print('PILOT_PACKAGE_VERIFIED', OUT, zip_path.stat().st_size)
print('PREVIEWS_ONLY_PACKAGE_VERIFIED', images_zip, images_zip.stat().st_size)
