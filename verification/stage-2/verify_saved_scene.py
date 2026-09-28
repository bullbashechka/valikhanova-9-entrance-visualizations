"""Run after opening the delivered .blend in a fresh Blender process."""
import bpy, json, hashlib, math, sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
DATA=json.loads((HERE/'geometry.json').read_text())
checks=[]
def check(name,ok,**data):checks.append(dict(name=name,passed=bool(ok),**data))
def world_verts(o):return [o.matrix_world@v.co for v in o.data.vertices]
bpy.context.view_layer.update()
portals=[o for o in bpy.data.objects if o.type=='EMPTY' and o.get('source_id')]
check('identified openings match source registry',len(portals)==len(DATA['openings']) and {o['source_id'] for o in portals}==set(DATA['openings']))
check('saved parameters match builder input',json.loads(bpy.context.scene['geometry_data_json'])==DATA)
for o in portals:
    expected=DATA['openings'][o['source_id']]
    physical_leaves=len({part['leaf_index'] for part in bpy.data.objects if part.get('opening_id')==o['source_id'] and 'leaf_index' in part})
    leaf_geometry_ok=physical_leaves==expected['leaf_count'] if expected['kind'] in ('door','glazed_door') else True
    check('opening configuration/'+o['source_id'],leaf_geometry_ok and o['leaf_count']==expected['leaf_count'] and abs(o['base_m']-expected['base'])<.001)
check('street door is a single leaf',bpy.data.objects['S1-19 / Лестница — улица']['leaf_count']==1)
check('4 perspective cameras and orthographic camera',all(n in bpy.data.objects for n in ['01-entry','02-lobby','03-lift','04-exterior','05-top']))
check('editable geometry',len([o for o in bpy.data.objects if o.type=='MESH'])>100)
for o in bpy.data.collections['Ceilings'].objects:
    z=min(v.z for v in world_verts(o));check('ceiling/'+o.name,abs(z-3)<1e-5,underside_m=round(z,6))
check('full-height model preserved',all(abs(max(v.z for v in world_verts(o))-o['expected_top_m'])<1e-5 for cname in ('Walls','UpperWalls') for o in bpy.data.collections[cname].objects))
source=json.loads((ROOT/'verification/stage-1/floor-contours.json').read_text(encoding='utf-8'))
for f in (a for a in source if a['section']==1):
    o=bpy.data.objects['Floor / '+f['zone']];area=0;verts=world_verts(o)
    for face in o.data.polygons:
        p=[verts[i] for i in face.vertices]
        if all(abs(v.z)<1e-6 for v in p):
            for i in range(1,len(p)-1):area+=(p[i]-p[0]).cross(p[i+1]-p[0]).length/2
    check('floor area/'+f['zone'],abs(area-f['area_m2'])<.002,actual_m2=round(area,4),stage1_m2=f['area_m2'])

def topz(name):return max(v.z for v in world_verts(bpy.data.objects[name]))
elevations=[topz('Exterior / upper platform')]+[topz(f'Exterior / tread {i}') for i in range(1,7)]+[topz('Exterior / lower approach')]
rises=[elevations[i]-elevations[i+1] for i in range(7)]
check('7 exterior risers at 150mm',len(rises)==7 and all(abs(h-.15)<1e-5 for h in rises),levels_m=[round(z,3) for z in elevations])
check('stair and exterior levels kept separate',abs(topz('Stair / lower entry landing')+1.05)<1e-5 and abs(topz('Exterior / lower approach')+1.06)<1e-5)
stair_levels=[topz('Stair / first-floor landing')]+[topz(f'Stair / ascending tread {i}') for i in range(1,11)]+[topz('Stair / first turning landing')]+[topz(f'Stair / upper return tread {i}') for i in range(1,11)]+[topz('Stair / second-floor landing')]
check('continuous rise to second floor',len(stair_levels)==23 and all(abs(b-a-.15)<1e-5 for a,b in zip(stair_levels,stair_levels[1:])) and abs(stair_levels[-1]-3.30)<1e-5,levels_m=[round(z,3) for z in stair_levels])
lower_levels=[topz('Stair / lower entry landing')]+[topz(f'Stair / visible lower tread {i}') for i in range(1,8)]+[topz('Stair / basement landing')]
check('separate descent from exterior door to basement',all(abs(a-b-.15)<1e-5 for a,b in zip(lower_levels,lower_levels[1:])) and abs(lower_levels[-1]+2.25)<1e-5 and bpy.data.objects['S1-19 / Лестница — улица']['status']=='project_height',levels_m=[round(z,3) for z in lower_levels])

sys.path.insert(0,str(HERE))
from audit_routes import audit_routes, audit_door_sweeps
cal=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
checks.extend(audit_routes(bpy,DATA,cal['mm_per_png_pixel_x']/1000,cal['mm_per_png_pixel_y']/1000))
checks.extend(audit_door_sweeps(bpy))
# Negative controls ensure the route checker actually detects missing floors and overhead obstacles.
route_data=dict(DATA,review_routes=[next(r for r in DATA['review_routes'] if r['id']=='first_to_second')])
sx,sy=cal['mm_per_png_pixel_x']/1000,cal['mm_per_png_pixel_y']/1000
bpy.ops.mesh.primitive_cube_add(size=1,location=(440*sx,-430*sy,1.8))
probe=bpy.context.object;probe.name='QA temporary overhead obstacle';probe.dimensions=(.8,.8,.1)
bpy.context.view_layer.update()
try:
    negative=audit_routes(bpy,route_data,sx,sy)[0]
    check('route checker rejects low overhead obstruction',not negative['passed'] and any(f['kind']=='headroom' for f in negative['failures']))
finally:bpy.data.objects.remove(probe,do_unlink=True)
landing=bpy.data.objects['Stair / basement landing'];original=landing.matrix_world.copy()
try:
    landing.location.z-=5;bpy.context.view_layer.update()
    negative=audit_routes(bpy,dict(DATA,review_routes=[next(r for r in DATA['review_routes'] if r['id']=='outside_to_basement')]),sx,sy)[0]
    check('route checker rejects missing landing',not negative['passed'] and any(f['kind'] in ('no_support','unsupported_footprint') for f in negative['failures']))
finally:landing.matrix_world=original;bpy.context.view_layer.update()

# Sample the source floor interiors against serialized wall meshes.
trees=[]
for ob in bpy.data.collections['Walls'].objects:
    trees.append((ob.name,BVHTree.FromPolygons(world_verts(ob),[list(p.vertices) for p in ob.data.polygons])))
cal=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
sx,sy=cal['mm_per_png_pixel_x']/1000,cal['mm_per_png_pixel_y']/1000
def inside(x,y,poly):
    hit=False
    for (ax,ay),(bx,by) in zip(poly,poly[1:]+poly[:1]):
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:hit=not hit
    return hit
bad=[];count=0
for f in (a for a in source if a['section']==1):
    poly=f['points_png']
    for x in range(math.ceil(min(p[0] for p in poly))+3,math.floor(max(p[0] for p in poly)),7):
        for y in range(math.ceil(min(p[1] for p in poly))+3,math.floor(max(p[1] for p in poly)),7):
            if inside(x,y,poly):
                count+=1;origin=Vector((x*sx,-y*sy,3.2))
                for name,t in trees:
                    if t.ray_cast(origin,Vector((0,0,-1)),3.19)[0] is not None:bad.append((f['zone'],x,y,name))
check('no walls inside source floor zones',not bad,samples=count,collisions=bad[:20])
img=bpy.data.images.get('section-1-common-areas.png')
check('source reference packed in blend',img is not None and img.packed_file is not None)
sha=hashlib.sha256((ROOT/'plans/section-1-common-areas.png').read_bytes()).hexdigest()
check('approved PNG unchanged',sha==cal['png_sha256'],sha256=sha)
check('ceilings and canopy visible in saved scene',not bpy.data.collections['Ceilings'].hide_render and not bpy.data.objects['Conditional / canopy'].hide_render)
check('no missing file assets',all(i.packed_file or i.source in ('GENERATED','VIEWER') or Path(bpy.path.abspath(i.filepath)).exists() for i in bpy.data.images))
mesh_state=[{'name':o.name,'vertices':[[round(c,6) for c in v] for v in world_verts(o)],'faces':[list(p.vertices) for p in o.data.polygons],'materials':[m.name for m in o.data.materials]} for o in sorted(bpy.data.objects,key=lambda o:o.name) if o.type=='MESH']
geometry_signature=hashlib.sha256(json.dumps(mesh_state,sort_keys=True).encode()).hexdigest()
report={'geometry_signature':geometry_signature,'blender':bpy.app.version_string,'blend_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'all_pass':all(c['passed'] for c in checks),'checks':checks}
(HERE/'reopen-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
review_meshes=[]
for o in bpy.data.collections['Stairs'].objects:
    if o.type=='MESH' and not any(token in o.name for token in ('handrail','post','guard')):
        review_meshes.append({'name':o.name,'vertices':[list(v) for v in world_verts(o)],'faces':[list(p.vertices) for p in o.data.polygons],'level':o.get('level'),'flight_id':o.get('flight_id')})
wall_sections=[]
for cut in (-.50,1.20,4.50):
    segments=[]
    for cname in ('Walls','UpperWalls'):
        for ob in bpy.data.collections[cname].objects:
            vertices=world_verts(ob)
            for face in ob.data.polygons:
                hits=[];ids=list(face.vertices)
                for ia,ib in zip(ids,ids[1:]+ids[:1]):
                    a,b=vertices[ia],vertices[ib]
                    if (a.z-cut)*(b.z-cut)<0:
                        q=a.lerp(b,(cut-a.z)/(b.z-a.z));hits.append([q.x/sx,-q.y/sy])
                if len(hits)==2:segments.append(hits)
    wall_sections.append({'cut_m':cut,'segments':segments})
(HERE/'stair-review.json').write_text(json.dumps({'meshes':review_meshes,'wall_sections':wall_sections,'routes':DATA['review_routes'],'levels_m':DATA['levels_m'],'scale':[sx,sy]},ensure_ascii=False,indent=2))
if not report['all_pass']:raise RuntimeError(json.dumps([c for c in checks if not c['passed']],ensure_ascii=True))
# Reproduce a camera image from the delivered file, not from the builder's live state.
s=bpy.context.scene;s.camera=bpy.data.objects['02-lobby'];s.render.resolution_x=720;s.render.resolution_y=480;s.cycles.samples=12
s.render.filepath=str(HERE/'previews/reopen-check.png');bpy.ops.render.render(write_still=True)
print('REOPEN_CHECKS_PASSED',len(checks))
