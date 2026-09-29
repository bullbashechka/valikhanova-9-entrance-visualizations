"""Create a self-contained local client pack from the verified render set."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote
import hashlib,json,shutil,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OUT=ROOT/'deliverables/section-1';OUT.mkdir(parents=True,exist_ok=True)
report=json.loads((HERE/'review-validation.json').read_text())
assert report['all_pass']
manifest=json.loads((HERE/'render-manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
scene=ROOT/'models/section-1/section-1-revised.blend'
assert sha(scene)==manifest['blend_sha256']
(OUT/'images').mkdir(exist_ok=True);(OUT/'references').mkdir(exist_ok=True)
for n,h in manifest['images'].items():
    assert sha(HERE/'previews'/n)==h
    shutil.copy2(HERE/'previews'/n,OUT/'images'/n)
shutil.copy2(scene,OUT/'section-1.blend')
shutil.copy2(ROOT/'plans/section-1-common-areas.png',OUT/'section-1-plan.png')
for n in ('albina-lobby.jpeg','albina-corridor.jpeg'):shutil.copy2(ROOT/'references'/n,OUT/'references'/n)
for n in ('materials.md','validation.json','render-manifest.json','visual-review.json','provenance.json'):shutil.copy2(HERE/n,OUT/n)
page=(HERE/'review.html').read_text().replace('previews/','images/').replace('../../models/section-1/section-1-revised.blend','section-1.blend').replace('../../plans/section-1-common-areas.png','section-1-plan.png').replace('../../references/','references/')
(OUT/'index.html').write_text(page)
(OUT/'README.md').write_text('''# Секция 1 — комплект для показа\n\nОткройте `index.html` в браузере. Интернет не нужен.\n\nВ папке `images` находятся четыре перспективы 2560 × 1707 px и цветной вид сверху с длинной стороной 2560 px. `section-1.blend` — редактируемая сцена с упакованными ресурсами; `section-1-plan.png` — исходный план без изменений.\n\nСогласованные правки: платформа подъёмника с управлением, металлическая подвальная дверь с небольшим матовым окном, сплошная внутренняя стена вместо двух вставок у квартирной двери, стена вместо двух отмеченных оконных проёмов слева, четыре двери по обеим сторонам коридора в плоскости стен со стороны прохода, древесная отделка двери лестницы с надписью «ЛЕСТНИЦА», указатель «ЛИФТ →».\n\nЭто доработанная концепция. Модель подъёмника условная, конкретное оборудование и фактические строительные размеры не подтверждены. Квартирная дверь сохранена; два синих элемента исходного PNG по уточнению пользователя представлены стеной.\n''')
class Links(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        for key in ('src','href'):
            if key in d and not d[key].startswith('#'):self.paths.append(d[key])
parser=Links();parser.feed(page)
assert all((OUT/unquote(p)).is_file() for p in parser.paths)
zip_path=ROOT/'deliverables/section-1-client.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,Path('section-1')/p.relative_to(OUT))
with zipfile.ZipFile(zip_path) as z:assert z.testzip() is None
print('CLIENT_PACK',OUT,'ZIP',zip_path)
