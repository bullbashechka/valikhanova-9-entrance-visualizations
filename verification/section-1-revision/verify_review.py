"""Static evidence only: images, local links, fragments, freshness and page structure."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote
import json,hashlib
from PIL import Image
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
class Page(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.images=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a' and 'href' in a:self.links.append(a['href'])
        if tag=='img':self.images.append(a)
p=Page();p.feed((HERE/'review.html').read_text());checks=[]
def check(name,value,**kw):checks.append(dict(name=name,passed=bool(value),**kw))
bad=[]
for link in p.links+[i.get('src','') for i in p.images]:
    if link.startswith('#'):
        if link[1:] not in p.ids:bad.append(link)
    elif '://' in link:bad.append(link)
    elif not (HERE/unquote(link)).resolve().is_file():bad.append(link)
check('all local links and anchors resolve',not bad,bad=bad)
check('all images have alt text',all(i.get('alt') for i in p.images))
check('unique ids',len(p.ids)==len(set(p.ids)))
check('five outputs plus two references',len(p.images)==7)
v=json.loads((HERE/'validation.json').read_text());r=json.loads((HERE/'render-manifest.json').read_text())
blend=hashlib.sha256((ROOT/'models/section-1/section-1-revised.blend').read_bytes()).hexdigest()
check('scene validation and render set are current',v['all_pass'] and v['blend_sha256']==r['blend_sha256']==blend)
check('style is current',r['style_sha256']==hashlib.sha256((HERE/'style.json').read_bytes()).hexdigest())
for name in ('01-entry','02-lobby','03-lift','04-exterior','05-top'):
    path=HERE/'previews'/f'{name}.png';im=Image.open(path);im.verify()
    check('image / '+name,max(im.size)==2560 and r['images'][path.name]==hashlib.sha256(path.read_bytes()).hexdigest(),dimensions=im.size)
visual=json.loads((HERE/'visual-review.json').read_text())
check('manual visual review matches current images',visual['images']==r['images'] and visual['passed'])
report={'all_pass':all(c['passed'] for c in checks),'checks':checks,
        'visual_images_reviewed':visual['images']==r['images'] and visual['passed'],
        'browser_verified':False,
        'browser_limitation':'Browser check not performed; local files, links, image dimensions and freshness validated'}
(HERE/'review-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert report['all_pass'],report
print('REVIEW_STATIC_CHECKS_PASSED',len(checks))
