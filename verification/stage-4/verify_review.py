"""Check delivered resources, current hashes, image sizes and local page wiring."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import hashlib,json,subprocess
from PIL import Image
H=Path(__file__).resolve().parent;R=H.parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(n,ok,**kw):checks.append(dict(name=n,passed=bool(ok),**kw))
m=json.loads((H/'render-manifest.json').read_text());v=json.loads((H/'validation.json').read_text());g=json.loads((H/'geometry-validation.json').read_text())
check('scene checks pass',v['all_pass'] and g['all_pass'])
check('current finish hashes',m['blend_sha256']==v['blend_sha256']==sha(R/'models/section-2/section-2-finish.blend'))
check('current geometry hash',g['blend_sha256']==sha(R/'models/section-2/section-2-geometry.blend'))
check('current style hash',m['style_sha256']==sha(H/'style.json'))
expected=['01-entry','02-lobby','03-lift','04-exterior','05-top']
check('exactly five presentation images',set(m['images'])=={x+'.png' for x in expected})
for n in expected:
 p=H/'previews'/(n+'.png');im=Image.open(p);check('image current / '+n,m['images'][p.name]==sha(p));check('resolution / '+n,max(im.size)==1920 and (n=='05-top' or im.size==(1920,1280)),size=im.size)
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=set();self.script=False;self.js=''
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.add(a['id'])
  for k in ('href','src'):
   if k in a:self.links.append(a[k])
  if tag=='script':self.script=True
 def handle_endtag(self,tag):
  if tag=='script':self.script=False
 def handle_data(self,data):
  if self.script:self.js+=data
page=Page();page.feed((H/'review.html').read_text());bad=[]
for link in page.links:
 u=urlsplit(link)
 if u.scheme:continue
 if not u.path:
  if u.fragment and u.fragment not in page.ids:bad.append(link)
 elif not (H/unquote(u.path)).resolve().exists():bad.append(link)
check('all local links and anchors resolve',not bad,missing=bad)
node=subprocess.run(['node','--check','-'],input=page.js,text=True,capture_output=True)
check('page script parses',node.returncode==0,error=node.stderr)
check('all presentation images on page',all('previews/'+n+'.png' in page.links for n in expected))
check('source overlay and control present',{'mesh','opacity'}<=page.ids and '../../plans/section-2-common-areas.png' in page.links)
visual=json.loads((H/'visual-review.json').read_text())
check('visual review matches current images',visual['passed'] and visual['images']==m['images'])
report=dict(all_static_checks_pass=all(x['passed'] for x in checks),checks=checks,browser=dict(status='unavailable',reason='Installed Browser plugin failed to connect: missing browser-service.mjs in referenced runtime version. No browser pass claimed.'))
(H/'review-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('REVIEW_CHECKS',len(checks),'PASS',report['all_static_checks_pass'])
if not report['all_static_checks_pass']:raise SystemExit(1)
