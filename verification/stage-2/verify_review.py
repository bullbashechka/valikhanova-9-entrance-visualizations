"""Offline artifact checks. Does not claim an interactive browser test."""
from pathlib import Path
from html.parser import HTMLParser
import json,hashlib,xml.etree.ElementTree as ET
from PIL import Image
H=Path(__file__).resolve().parent
class Resources(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        for key in ('src','href'):
            if d.get(key):self.links.append(d[key])
        if d.get('id'):self.ids.append(d['id'])
p=Resources();p.feed((H/'review.html').read_text())
missing=[u for u in p.links if not u.startswith(('#','http','data:')) and not (H/u.split('#')[0]).exists()]
checks=[{'name':'all local links and resources exist','passed':not missing,'missing':missing}, {'name':'overlay controls and targets exist','passed':all(i in p.ids for i in ('opacity','mesh','paths','routes'))}]
images=[]
for path in sorted((H/'previews').glob('*.png')):
    with Image.open(path) as im:im.verify()
    images.append(path.name)
checks.append({'name':'PNG images decode','passed':True,'images':images})
for path in sorted((H/'previews').glob('*.svg')):
    root=ET.fromstring(path.read_text());width=float(root.attrib['width']);height=float(root.attrib['height'])
    checks.append({'name':'SVG dimensions/'+path.name,'passed':width>0 and height>0})
checks.append({'name':'saved model verification current','passed':json.loads((H/'reopen-validation.json').read_text())['blend_sha256']==hashlib.sha256((H.parent.parent/'models/section-1/section-1-geometry.blend').read_bytes()).hexdigest()})
report={'date':'2026-09-27','all_executed_checks_pass':all(c['passed'] for c in checks),'checks':checks,'visual_review':['four perspectives','annotated overview','source overlay','stair section','level plans'],'browser':{'status':'not_run','reason':'Browser plugin bootstrap cannot import its browser-service.mjs; no claim of interactive or mobile UI validation'},'diagram_renderer':'macOS Quick Look; square scratch canvases used to avoid thumbnail cropping'}
(H/'review-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
assert report['all_executed_checks_pass'],report
print('REVIEW_STATIC_CHECKS_PASSED',len(checks))
