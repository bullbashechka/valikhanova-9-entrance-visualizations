"""Compare source architecture with the saved concept, then check actual scene geometry."""
import bpy,json,hashlib,sys,math
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
BASE=ROOT/'models/section-1/section-1-geometry.blend';OUT=ROOT/'models/section-1/section-1-finish.blend'
STYLE=json.loads((HERE/'style.json').read_text());checks=[]
def check(name,ok,**details):checks.append(dict(name=name,passed=bool(ok),**details))
def meshstate(ob):
    return {'vertices':[[round(c,6) for c in ob.matrix_world@v.co] for v in ob.data.vertices],
            'faces':[list(p.vertices) for p in ob.data.polygons],
            'opening_id':ob.get('opening_id'), 'leaf_index':ob.get('leaf_index'), 'open_angle':ob.get('open_angle')}
bpy.ops.wm.open_mainfile(filepath=str(BASE));bpy.context.view_layer.update()
original={o.name:meshstate(o) for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith(('Proxy / stroller','Proxy / wheel'))}
base_parameters=bpy.context.scene['geometry_data_json']
bpy.ops.wm.open_mainfile(filepath=str(OUT));bpy.context.view_layer.update()
check('source blend unchanged',hashlib.sha256(BASE.read_bytes()).hexdigest()==STYLE['source_blend_sha256'])
changed=[n for n,s in original.items() if n not in bpy.data.objects or meshstate(bpy.data.objects[n])!=s]
check('all original architecture meshes and opening parameters unchanged',not changed,objects=len(original),changed=changed)
check('geometry metadata unchanged',bpy.context.scene['geometry_data_json']==base_parameters)
check('style matches saved scene',json.loads(bpy.context.scene['stage3_style_json'])==STYLE)
check('all five cameras present',all(n in bpy.data.objects for n in ['01-entry','02-lobby','03-lift','04-exterior','05-top']))
for cfg in STYLE['cameras']:
    o=bpy.data.objects[cfg['name']];check('eye height / '+cfg['name'],abs(o.location.z-cfg['height'])<1e-5 and 26<=o.data.lens<=35)
for ob in bpy.data.collections['Ceilings'].objects:
    check('ceiling remains 3m / '+ob.name,abs(min((ob.matrix_world@v.co).z for v in ob.data.vertices)-3)<1e-5 and not ob.hide_render)
check('navigation includes all agreed labels',all(n in bpy.data.objects for n in ('N / stroller label','N / floor number','N / exterior number','N / stroller icon')))
check('one stroller model',sum(o.name=='S / bassinet' for o in bpy.data.collections['Stroller'].objects)==1)
cal=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1'];sx,sy=cal['mm_per_png_pixel_x']/1000,cal['mm_per_png_pixel_y']/1000
coords=[o.matrix_world@v.co for o in bpy.data.collections['Stroller'].objects if o.type=='MESH' for v in o.data.vertices]
check('stroller stays within open niche',all(179.8*sx<v.x<389.4*sx and -157.4*sy<v.y<-56.3*sy for v in coords))
check('no extra partition or mailboxes',not any('mailbox' in o.name.lower() or 'partition' in o.name.lower() for o in bpy.data.collections['Finish'].objects))
sys.path.insert(0,str(ROOT/'verification/stage-2'))
from audit_routes import audit_routes,audit_door_sweeps
data=json.loads(base_parameters)
# The existing sweep checker filters collections; include all new physical details.
linked=[]
for cname in ('Finish','Fixtures','Stroller'):
    for o in bpy.data.collections[cname].objects:
        if o.type=='MESH' and o.name not in bpy.data.collections['Proxies'].objects:
            bpy.data.collections['Proxies'].objects.link(o);linked.append(o)
checks.extend(audit_routes(bpy,data,sx,sy));checks.extend(audit_door_sweeps(bpy))
for o in linked:bpy.data.collections['Proxies'].objects.unlink(o)
img=bpy.data.images.get('section-1-common-areas.png')
check('source PNG packed and unchanged',bool(img and img.packed_file) and hashlib.sha256((ROOT/'plans/section-1-common-areas.png').read_bytes()).hexdigest()==cal['png_sha256'])
check('images self contained',all(i.packed_file or i.source in ('GENERATED','VIEWER') for i in bpy.data.images))
check('fonts self contained',all(f.packed_file or f.filepath=='<builtin>' for f in bpy.data.fonts))
check('no ceiling height reduction',STYLE['ceiling_drop_m']==0)
report={'all_pass':all(c['passed'] for c in checks),'blender':bpy.app.version_string,'blend_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'checks':checks}
(HERE/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
failed=[c for c in checks if not c['passed']]
print('SCENE_CHECKS',len(checks),'FAILED',len(failed))
if failed:raise RuntimeError(json.dumps(failed,ensure_ascii=False))
