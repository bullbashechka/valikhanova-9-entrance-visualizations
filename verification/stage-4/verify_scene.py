"""Independent checks on reopened geometry or finish, including routes and moving doors."""
import bpy,json,hashlib,sys,math,csv
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
finish='--finish' in sys.argv
BASE=ROOT/'models/section-2/section-2-geometry.blend';OUT=ROOT/('models/section-2/section-2-finish.blend' if finish else 'models/section-2/section-2-geometry.blend')
D=json.loads((HERE/'geometry.json').read_text());cal=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['2'];sx=cal['mm_per_png_pixel_x']/1000;sy=cal['mm_per_png_pixel_y']/1000
checks=[]
def check(n,ok,**kw):checks.append(dict(name=n,passed=bool(ok),**kw))
def state(ob):return {'vertices':[[round(v,6) for v in ob.matrix_world@p.co] for p in ob.data.vertices],'faces':[list(p.vertices) for p in ob.data.polygons],'opening_id':ob.get('opening_id'),'angle':ob.get('open_angle')}
if finish:
    bpy.ops.wm.open_mainfile(filepath=str(BASE));bpy.context.view_layer.update()
    original={o.name:state(o) for o in bpy.data.objects if o.type=='MESH'}
bpy.ops.wm.open_mainfile(filepath=str(OUT));bpy.context.view_layer.update()
check('stored geometry data matches configuration',json.loads(bpy.context.scene['geometry_data_json'])==D)
if finish:
    changed=[n for n,s in original.items() if n not in bpy.data.objects or state(bpy.data.objects[n])!=s]
    check('all source architecture unchanged after finish',not changed,changed=changed,count=len(original))
    st=json.loads((HERE/'style.json').read_text())
    check('saved style matches',json.loads(bpy.context.scene['stage4_style_json'])==st)
    check('geometry source hash',hashlib.sha256(BASE.read_bytes()).hexdigest()==st['source_blend_sha256'])
    check('all navigation labels',all(n in bpy.data.objects for n in ['N / stroller label','N / lift direction','N / exterior number','N / floor number']))
    check('correct section number',bpy.data.objects['N / exterior number'].data.body=='2')
    coords=[o.matrix_world@v.co for o in bpy.data.collections['Stroller'].objects if o.type=='MESH' for v in o.data.vertices]
    check('one stroller in open zone',sum(o.name=='S / bassinet' for o in bpy.data.collections['Stroller'].objects)==1 and all(20.5*sx<v.x<203.4*sx and -217.4*sy<v.y<-122.3*sy for v in coords))
    check('no mailboxes or added partition',not any('mailbox' in o.name.lower() or 'partition' in o.name.lower() for o in bpy.data.collections['Finish'].objects))
check('source PNG unchanged',hashlib.sha256((ROOT/'plans/section-2-common-areas.png').read_bytes()).hexdigest()==cal['png_sha256'])
check('source PNG packed',bool(bpy.data.images.get('section-2-common-areas.png').packed_file))
check('all resources packed',all(i.packed_file or i.source in ('GENERATED','VIEWER') for i in bpy.data.images) and all(f.packed_file or f.filepath=='<builtin>' for f in bpy.data.fonts))
for f in json.loads((ROOT/'verification/stage-1/floor-contours.json').read_text()):
    if f['section']!=2:continue
    ob=bpy.data.objects['Floor / '+f['zone']]
    top=sum(p.area for p in ob.data.polygons if p.normal.z>.9)
    check('floor area / '+f['zone'],abs(top-f['area_m2'])<.005,actual_m2=top,source_estimate_m2=f['area_m2'],label_m2=f['label_area_m2'])
for ob in bpy.data.collections['Ceilings'].objects:
    check('3m ceiling / '+ob.name,abs(min((ob.matrix_world@v.co).z for v in ob.data.vertices)-3)<1e-6)
portals=json.loads((HERE/'scene-section.json').read_text())['portals']
check('all openings accounted for',set(portals)==set(D['openings']))
trees=[]
for cname in ('Walls','UpperWalls'):
    for ob in bpy.data.collections[cname].objects:
        trees.append((ob.name,BVHTree.FromPolygons([ob.matrix_world@v.co for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons])))
for oid,o in portals.items():
    r=o['rect'];z=o['base']+min(1,o['height']/2);hits=[]
    for frac in (.1,.3,.5,.7,.9):
        if o['vertical']:a=Vector(((r[0]-1)*sx,-(r[1]+(r[3]-r[1])*frac)*sy,z));b=Vector(((r[2]+1)*sx,a.y,z))
        else:a=Vector(((r[0]+(r[2]-r[0])*frac)*sx,-(r[1]-1)*sy,z));b=Vector((a.x,-(r[3]+1)*sy,z))
        for n,t in trees:
            if t.ray_cast(a,(b-a).normalized(),(b-a).length)[0] is not None:hits.append(n)
    check('actual wall opening / '+oid,not hits,obstructions=sorted(set(hits)))
measurements={r['id']:r for r in csv.DictReader((ROOT/'verification/stage-1/measurements.csv').open(encoding='utf-8-sig')) if r['section']=='2'}
for oid,o in portals.items():
    if o['kind']=='open':continue
    m=measurements[oid];vertical=o['vertical'];axis=1 if vertical else 0
    points=[v for name in ('jamb-start','jamb-end') for v in [bpy.data.objects[oid+'/'+name].matrix_world@p.co for p in bpy.data.objects[oid+'/'+name].data.vertices]]
    actual=max(v[axis] for v in points)-min(v[axis] for v in points)
    expected=abs(float(m['y2' if vertical else 'x2'])-float(m['y1' if vertical else 'x1']))*(sy if vertical else sx)
    check('actual frame width from source / '+oid,abs(actual-expected)<1e-5,actual_m=actual,source_m=expected)
check('S2-17 upper level and explicit override',portals['S2-17']['base']==3.3 and bool(D['openings']['S2-17'].get('level_decision')))
a=Vector((525*sx,-370*sy,1));d=Vector((0,-1,0));blocked=any(t.ray_cast(a,d,.8)[0] is not None for _,t in trees)
check('no S2-17 first-floor entrance',blocked)
check('open stroller boundary',not any(t.ray_cast(Vector((100*sx,-220*sy,1)),Vector((0,1,0)),.3)[0] is not None for _,t in trees))
for cfg in D['cameras']:
    ob=bpy.data.objects[cfg['name']];check('eye camera / '+cfg['name'],abs(ob.location.z-cfg['height'])<1e-6 and 24<=ob.data.lens<=35)
check('five cameras',len(bpy.data.collections['Cameras'].objects)==5)
sys.path.insert(0,str(ROOT/'verification/stage-2'))
from audit_routes import audit_routes,audit_door_sweeps
linked=[]
if finish:
    for name in ('Finish','Fixtures','Stroller'):
        for o in bpy.data.collections[name].objects:
            if o.type=='MESH':bpy.data.collections['Proxies'].objects.link(o);linked.append(o)
checks.extend(audit_routes(bpy,D,sx,sy));checks.extend(audit_door_sweeps(bpy))
for o in linked:bpy.data.collections['Proxies'].objects.unlink(o)
# Negative controls establish that route checks detect real mesh errors.
if not finish:
    bpy.ops.mesh.primitive_cube_add(size=1,location=(90*sx,-600*sy,1.7))
    obstacle=bpy.context.object;obstacle.name='Negative control / blocked corridor';obstacle.dimensions=(1,1,.25)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);bpy.context.view_layer.update()
    negative=audit_routes(bpy,dict(review_routes=[D['review_routes'][0]]),sx,sy)[0]
    check('negative control detects blocked route',not negative['passed'])
    bpy.data.objects.remove(obstacle,do_unlink=True)
    bpy.data.objects.remove(bpy.data.objects['Stair / upper destination fragment'],do_unlink=True);bpy.context.view_layer.update()
    negative=audit_routes(bpy,dict(review_routes=[D['review_routes'][3]]),sx,sy)[0]
    check('negative control detects missing upper support',not negative['passed'] and any(f['kind'] in ('no_support','unsupported_footprint') for f in negative['failures']))
report=dict(all_pass=all(c['passed'] for c in checks),blender=bpy.app.version_string,blend_sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),checks=checks)
(HERE/('validation.json' if finish else 'geometry-validation.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
failed=[c for c in checks if not c['passed']];print('CHECKS',len(checks),'FAILED',len(failed))
if failed:raise RuntimeError(json.dumps(failed,ensure_ascii=False))
