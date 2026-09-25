"""Blender 5.2: --background --python build_scene.py -- [--render] [--draft]."""
import bpy, csv, json, math, hashlib, sys
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / 'models' / 'section-1'
OUT.mkdir(parents=True, exist_ok=True)
PREVIEW = HERE / 'previews'
PREVIEW.mkdir(exist_ok=True)
DATA = json.loads((HERE/'geometry.json').read_text(encoding='utf-8'))
CAL = json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
SX, SY = CAL['mm_per_png_pixel_x']/1000, CAL['mm_per_png_pixel_y']/1000
with (ROOT/'verification/stage-1/measurements.csv').open(encoding='utf-8-sig', newline='') as f:
    MEAS = {r['id']:r for r in csv.DictReader(f) if r['section']=='1'}
FLOORS = [r for r in json.loads((ROOT/'verification/stage-1/floor-contours.json').read_text(encoding='utf-8')) if r['section']==1]
PNG = ROOT/'plans/section-1-common-areas.png'
assert hashlib.sha256(PNG.read_bytes()).hexdigest()==CAL['png_sha256'], 'Source PNG changed'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection': bpy.data.collections.remove(c)
COLS = {}
for name in ['Walls','Floors','Ceilings','Doors','Windows','Stairs','Exterior','Proxies','Context','Cameras','Lights','Reference']:
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); COLS[name]=c

def material(name, color, alpha=1):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,alpha)
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=.72
    if alpha<1:
        # Deliberately simple transparent infill for geometry review, not selected glazing.
        nt=m.node_tree; tr=nt.nodes.new('ShaderNodeBsdfTransparent'); mix=nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value=alpha
        nt.links.new(tr.outputs[0],mix.inputs[1]); nt.links.new(bs.outputs[0],mix.inputs[2])
        nt.links.new(mix.outputs[0],nt.nodes.get('Material Output').inputs[0])
    return m
MAT={
    'wall':material('Neutral / walls',(.55,.56,.57)),
    'floor':material('Neutral / floor',(.28,.30,.32)),
    'ceiling':material('Neutral / ceiling',(.78,.79,.80)),
    'frame':material('Neutral / frames',(.055,.065,.075)),
    'door':material('Neutral / solid doors',(.18,.21,.23)),
    'glass':material('Conditional / glazing',(.55,.68,.70),.13),
    'proxy':material('Conditional / equipment',(.34,.41,.44)),
    'ground':material('Context / neutral ground',(.57,.59,.60)),
    'stroller':material('Conditional / stroller',(.22,.26,.29))
}

def link(obj, collection, mat=None, status='graphical_estimate', source='PNG section 1'):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    COLS[collection].objects.link(obj)
    if mat: obj.data.materials.append(MAT[mat])
    obj['source']=source; obj['status']=status
    return obj

def box(name, center, dims, collection='Walls', mat='wall', status='graphical_estimate', angle=0):
    x,y,z=[v/2 for v in dims]
    verts=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); obj.location=center; obj.rotation_euler.z=angle
    return link(obj,collection,mat,status)

def rect(name, r, z0, z1, collection='Walls', mat='wall', status='graphical_estimate'):
    a,b,c,d=r
    return box(name,((a+c)*SX/2,-(b+d)*SY/2,(z0+z1)/2),((c-a)*SX,(d-b)*SY,z1-z0),collection,mat,status)

def prism(name, pts, z0, z1, collection='Floors', mat='floor', status='graphical_estimate'):
    xy=[Vector((x*SX,-y*SY,0)) for x,y in pts]
    n=len(xy); verts=[(v.x,v.y,z) for z in (z0,z1) for v in xy]
    faces=[]
    for t in tessellate_polygon([xy]):
        ids=list(t) if isinstance(t[0],int) else [min(range(n),key=lambda i:(xy[i]-v).length) for v in t]
        # Polygon source coordinates are clockwise after the Y flip.
        if (xy[ids[1]]-xy[ids[0]]).cross(xy[ids[2]]-xy[ids[0]]).z<0: ids.reverse()
        faces.extend([tuple(reversed(ids)),tuple(i+n for i in ids)])
    area=sum(xy[i].x*xy[(i+1)%n].y-xy[(i+1)%n].x*xy[i].y for i in range(n))
    for i in range(n):
        j=(i+1)%n; f=(i,j,j+n,i+n)
        faces.append(f if area>0 else tuple(reversed(f)))
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    return link(obj,collection,mat,status)

def rod(name,a,b,r=.018,collection='Exterior',mat='frame'):
    a,b=Vector(a),Vector(b); vec=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=r,depth=vec.length,location=(a+b)/2)
    o=bpy.context.object; o.name=name; o.rotation_euler=vec.to_track_quat('Z','Y').to_euler()
    return link(o,collection,mat,'conditional')

def pxy(x,y,z): return Vector((x*SX,-y*SY,z))

# Four measured floor zones; the stroller boundary creates no wall or threshold.
for i,f in enumerate(FLOORS):
    o=prism('Floor / '+f['zone'],f['points_png'],-.15,0)
    o['zone']=f['zone']; o['source_area_m2']=f['area_m2']; o['label_area_m2']=f['label_area_m2']
    prism('Ceiling / '+f['zone'],f['points_png'],3,3.15,'Ceilings','ceiling','project_height')

PORTALS={}
for w in DATA['walls']:
    r=w['rect']; vertical=(r[3]-r[1])>(r[2]-r[0]); axis=1 if vertical else 0
    lo,hi=r[axis],r[axis+2]; cursor=lo; zmin=w.get('base',0)
    cuts=[]
    for oid in w.get('openings',[]):
        m=MEAS[oid]; o=DATA['openings'][oid]
        a,b=sorted((float(m['y1' if vertical else 'x1']),float(m['y2' if vertical else 'x2'])))
        cuts.append((a,b,oid,o))
    for a,b,oid,o in sorted(cuts):
        assert lo<=a<b<=hi,(w['id'],oid)
        def part(start,end,bottom,top,suffix):
            if end-start>.0001 and top-bottom>.0001:
                q=r.copy();q[axis]=start;q[axis+2]=end
                rect(w['id']+'/'+suffix,q,bottom,top)
        part(cursor,a,zmin,3,'solid-'+oid)
        part(a,b,zmin,o['base'],'sill-'+oid)
        part(a,b,o['base']+o['height'],3,'lintel-'+oid)
        q=r.copy();q[axis]=a;q[axis+2]=b
        PORTALS[oid]={'rect':q,'vertical':vertical,**o}
        cursor=b
    if cursor<hi:
        q=r.copy();q[axis]=cursor;rect(w['id']+'/solid',q,zmin,3)

for oid,o in PORTALS.items():
    r=o['rect']; vertical=o['vertical']; z=o['base']; h=o['height']
    a=pxy((r[0]+r[2])/2,r[1],z) if vertical else pxy(r[0],(r[1]+r[3])/2,z)
    b=pxy((r[0]+r[2])/2,r[3],z) if vertical else pxy(r[2],(r[1]+r[3])/2,z)
    u=(b-a).normalized(); length=(b-a).length; angle=math.atan2(u.y,u.x)
    collection='Windows' if o['kind']=='window' else 'Doors'
    def slab(s,e,base,top,mat,name,depth=.055):
        c=a+u*((s+e)/2);c.z=(base+top)/2
        ob=box(oid+'/'+name,c,(e-s,depth,top-base),collection,mat,o['status'],angle)
        ob['opening_id']=oid; return ob
    fw=.045
    slab(0,fw,z,z+h,'frame','jamb-start',.09)
    slab(length-fw,length,z,z+h,'frame','jamb-end',.09)
    slab(fw,length-fw,z+h-fw,z+h,'frame','head',.09)
    if o['kind']=='window':
        slab(fw,length-fw,z,z+fw,'frame','sill',.09)
        slab(fw,length-fw,z+fw,z+h-fw,'glass','pane',.018)
        slab(length/2-.018,length/2+.018,z+fw,z+h-fw,'frame','mullion')
    elif o['kind']=='glazed_door':
        split=length*.64
        for j,(s,e) in enumerate([(fw,split),(split,length-fw)]):
            slab(s,e,z+.012,z+.095,'frame',f'leaf-{j}-bottom')
            slab(s,e,z+h-.085,z+h-fw,'frame',f'leaf-{j}-top')
            slab(e-.04,e,z+.095,z+h-.085,'frame',f'leaf-{j}-edge')
            slab(s,e-.04,z+.095,z+h-.085,'glass',f'leaf-{j}-glass',.018)
        slab(split-.10,split-.07,z+.85,z+1.15,'frame','handle',.12)
    else:
        if o['kind']=='lift':
            slab(fw,length/2-.007,z+.015,z+h-fw,'door','left-panel')
            slab(length/2+.007,length-fw,z+.015,z+h-fw,'door','right-panel')
        else:
            slab(fw,length-fw,z+.015,z+h-fw,'door','closed-leaf')
            slab(length-fw-.19,length-fw-.06,z+.97,z+1.00,'frame','handle',.13)
    if o['kind']!='window': rect(oid+'/threshold',r,z-.15,z,'Floors','floor')
    empty=bpy.data.objects.new(oid+' / '+MEAS[oid]['description'],None)
    COLS['Reference'].objects.link(empty);empty.location=(a+b)/2;empty.empty_display_size=.10
    empty['source_id']=oid;empty['width_m']=length;empty['height_m']=h;empty['status']=o['status']
    empty['hinge']=o.get('hinge','none');empty['swing_side']=o.get('swing',0)

# Stairwell: first visible rising flight; lower exterior access is a separate level.
rect('Stair / first-floor landing',[392.2,346.8,485.4,539.1],-.15,0,'Stairs','floor')
for i in range(10):
    y0=539.1+(764.3-539.1)*i/10; y1=539.1+(764.3-539.1)*(i+1)/10
    rect(f'Stair / ascending tread {i+1}',[392.2,y0,485.4,y1],-.15,(i+1)*.15,'Stairs','floor','conditional')
rect('Stair / first turning landing',[392.2,764.3,594.3,865.3],1.50,1.65,'Stairs','floor','conditional')
rect('Stair / lower entry landing',[494.9,346.8,594.3,599.0],-1.20,-1.05,'Stairs','floor','project_elevation')
for i in range(7):
    y0=599+(764.3-599)*i/7;y1=599+(764.3-599)*(i+1)/7
    top=-1.05-(i+1)*.15
    rect(f'Stair / visible lower tread {i+1}',[494.9,y0,594.3,y1],top-.15,top,'Stairs','floor','conditional')
rect('Stair / lower continuation cut',[494.9,764.3,594.3,865.3],-2.40,-2.25,'Stairs','floor','conditional')
rod('Stair / handrail',pxy(481,539.1,1),pxy(481,764.3,2.65),.022,'Stairs')
for i in range(6):
    t=i/5;y=539.1+(764.3-539.1)*t;z=1.65*t
    rod('Stair / post',pxy(481,y,z),pxy(481,y,z+1),.018,'Stairs')

prism('Exterior / upper platform',DATA['exterior_platform_png'],-1.21,-.01,'Exterior','floor','project_elevation')
for i in range(6):
    y0=217+(356.7-217)*i/6;y1=217+(356.7-217)*(i+1)/6
    top=-.01-(i+1)*.15
    rect(f'Exterior / tread {i+1}',[759.5,y0,852.8,y1],-1.21,top,'Exterior','floor','derived_dimension')
rect('Exterior / lower approach',[633.8,356.7,1050,620],-1.21,-1.06,'Exterior','ground','project_elevation')
# The equipment footprint is deliberately labelled as a proxy, never a specification.
rect('Proxy / lift platform',[872.1,217,965.4,310.3],-.01,.06,'Proxies','proxy','conditional')
for x,y in [(880,222),(958,222),(958,303),(880,303)]:
    rod('Proxy / lift post',pxy(x,y,-.01),pxy(x,y,.92),.023,'Proxies')
rod('Proxy / lift top back',pxy(958,222,.92),pxy(958,303,.92),.023,'Proxies')
rod('Proxy / lift top side',pxy(880,222,.92),pxy(958,222,.92),.023,'Proxies')
for start,end in [((987,76),(987,217)),((859,217),(859,356.7))]:
    a=pxy(*start,-.01);b=pxy(*end,-.01)
    # On stairs the handrail follows the rise.
    if start[0]==859: b.z=-1.06
    rod('Conditional / railing top',a+Vector((0,0,1)),b+Vector((0,0,1)))
    for t in [0,.5,1]:
        p=a.lerp(b,t);rod('Conditional / railing post',p,p+Vector((0,0,1)))
rect('Conditional / canopy',[735,60,975,207],2.7,2.86,'Exterior','wall','conditional')
rect('Context / facade north',[987,26.7,1300,56.3],-1.2,4.2,'Context','wall','conditional')
rect('Context / facade south',[594.3,894.9,633.8,1080],-1.2,4.2,'Context','wall','conditional')
rect('Context / ground',[630,56.3,1420,900],-1.24,-1.075,'Context','ground','conditional')

# One recognisable, neutral stroller. No implied parking capacity.
s=DATA['stroller']; cx,cy=s['center_png']; center=pxy(cx,cy,0)
box('Proxy / stroller basin',center+Vector((0,0,.57)),(.78,.48,.22),'Proxies','stroller','conditional')
box('Proxy / stroller hood',center+Vector((-.24,0,.85)),(.31,.5,.32),'Proxies','stroller','conditional')
for dx in [-.36,.36]:
    for dy in [-.25,.25]:
        p=center+Vector((dx,dy,.11))
        rod('Proxy / wheel',p-Vector((0,.035,0)),p+Vector((0,.035,0)),.105,'Proxies','frame')
        rod('Proxy / stroller chassis',p,center+Vector((-dx*.5,dy,.61)),.016,'Proxies')
for dy in [-.23,.23]:
    rod('Proxy / stroller handle support',center+Vector((-.28,dy,.5)),center+Vector((-.50,dy,1.02)),.016,'Proxies')
rod('Proxy / stroller handle',center+Vector((-.50,-.23,1.02)),center+Vector((-.50,.23,1.02)),.022,'Proxies')

scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='METERS';scene.unit_settings.scale_length=1
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.cycles.max_bounces=8;scene.cycles.transparent_max_bounces=16
scene.render.resolution_x=1440;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.82,.86,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.18
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.render.film_transparent=False
def light(name,loc,energy,size,target=None):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy*.25;d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);COLS['Lights'].objects.link(o);o.location=loc
    if target is not None:o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o
for x,y,e,size in [(350,185,450,3),(665,160,180,1.3),(115,255,130,1),(220,430,280,2),(110,740,170,1.4),(110,1060,170,1.4)]:
    light('Review / area light',pxy(x,y,2.85),e,size)
light('Review / exterior softbox',pxy(1150,280,7),1600,8,pxy(780,220,0))
light('Review / overhead fill',pxy(400,600,12),1300,10,pxy(400,600,0))

CAMERAS=[]
for c in DATA['cameras']:
    d=bpy.data.cameras.new(c['name']);d.lens=c['lens'];d.clip_start=.04;d.clip_end=200;d.sensor_width=36
    o=bpy.data.objects.new(c['name'],d);COLS['Cameras'].objects.link(o)
    o.location=pxy(*c['position_png'],c['height']);target=pxy(*c['target_png'],c['target_height'])
    o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();o['label']=c['label'];CAMERAS.append(o)
img=bpy.data.images.load(str(PNG));img.pack();W,H=img.size
ref=bpy.data.objects.new('Approved PNG / locked reference',None);ref.empty_display_type='IMAGE';ref.data=img
ref.empty_display_size=W*SX;ref.location=(W*SX/2,-H*SY/2,-.3);ref.hide_render=True;ref.hide_viewport=True
ref['sha256']=CAL['png_sha256'];COLS['Reference'].objects.link(ref)
d=bpy.data.cameras.new('05-top');d.type='ORTHO';d.ortho_scale=W*SX;d.sensor_fit='HORIZONTAL'
top=bpy.data.objects.new('05-top',d);COLS['Cameras'].objects.link(top);top.location=(W*SX/2,-H*SY/2,25)
top.rotation_euler=(0,0,0)

bpy.context.view_layer.update()
# Independent spatial checks against the actual wall meshes, not just JSON records.
trees=[]
for ob in COLS['Walls'].objects:
    verts=[ob.matrix_world@v.co for v in ob.data.vertices]
    trees.append((ob.name,BVHTree.FromPolygons(verts,[list(p.vertices) for p in ob.data.polygons],all_triangles=False)))
def obstruction(a,b):
    delta=Vector(b)-Vector(a);length=delta.length
    return [name for name,t in trees if t.ray_cast(Vector(a),delta.normalized(),length)[0] is not None]
checks=[]
for oid,o in PORTALS.items():
    r=o['rect'];z=o['base']+min(o['height']/2,1)
    bad=[]
    for t in [.08,.25,.5,.75,.92]:
        if o['vertical']:
            y=r[1]+(r[3]-r[1])*t;a=pxy(r[0]-1,y,z);b=pxy(r[2]+1,y,z)
        else:
            x=r[0]+(r[2]-r[0])*t;a=pxy(x,r[1]-1,z);b=pxy(x,r[3]+1,z)
        bad+=obstruction(a,b)
    checks.append({'name':'clear_wall_opening/'+oid,'pass':not bad,'obstructions':sorted(set(bad))})
routes=[[(980,130),(690,130),(520,130),(460,220),(220,220),(110,220),(110,450),(278,450),(278,510)],[(460,220),(440,300),(440,380)],[(460,220),(410,175),(310,175),(310,145)],[(110,450),(110,1120)]]
for i,route in enumerate(routes):
    bad=[]
    for a,b in zip(route,route[1:]):bad+=obstruction(pxy(*a,1),pxy(*b,1))
    checks.append({'name':f'route_wall_clearance/{i+1}','pass':not bad,'obstructions':sorted(set(bad))})
checks.append({'name':'stroller_inside_open_zone','pass':179.8*SX<center.x-.5 and center.x+.5<389.4*SX and -157.4*SY<center.y-.31 and center.y+.31<-56.3*SY})
checks.append({'name':'source_png_sha256','pass':hashlib.sha256(PNG.read_bytes()).hexdigest()==CAL['png_sha256']})

# A real mesh section at 1.2m for the source overlay.
segments=[]
for ob in COLS['Walls'].objects:
    verts=[ob.matrix_world@v.co for v in ob.data.vertices]
    for face in ob.data.polygons:
        hits=[];ids=list(face.vertices)
        for ia,ib in zip(ids,ids[1:]+ids[:1]):
            a,b=verts[ia],verts[ib]
            if (a.z-1.2)*(b.z-1.2)<0:
                p=a.lerp(b,(1.2-a.z)/(b.z-a.z));hits.append([p.x/SX,-p.y/SY])
        if len(hits)==2:segments.append({'object':ob.name,'points':hits})
(HERE/'scene-section.json').write_text(json.dumps({'cut_height_m':1.2,'segments':segments,'portals':PORTALS,'routes':routes},ensure_ascii=False,indent=2),encoding='utf-8')
report={'blender':bpy.app.version_string,'checks':checks,'all_pass':all(c['pass'] for c in checks),'object_count':len(bpy.data.objects),'assumptions':DATA['assumptions'],'levels_m':{'floor':0,'outside_upper':-.01,'outside_lower':-1.06,'stair_lower_entry':-1.05},'exterior_risers':7,'exterior_treads':6,'exterior_rise_m':.15,'source_png_sha256':CAL['png_sha256']}
(HERE/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
scene['purpose']='Stage 2 conceptual geometry / unapproved for final rendering'
scene['source_of_truth']='Approved PNG; stage-1 calibration and measurements'
scene['assumptions_json']=json.dumps(DATA['assumptions'],ensure_ascii=False)
scene.camera=CAMERAS[1]
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_distance=22
        area.spaces.active.region_3d.view_location=(6,-7,0)
        area.spaces.active.clip_end=300
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'section-1-geometry.blend'))
print('VALIDATION',report['all_pass'],'checks',len(checks),'objects',len(bpy.data.objects))
if not report['all_pass']:raise RuntimeError('Geometry checks failed; inspect validation.json')
if '--render' in sys.argv:
    if '--draft' in sys.argv:
        scene.render.resolution_x=960;scene.render.resolution_y=640;scene.cycles.samples=16
    for cam in CAMERAS:
        scene.camera=cam;scene.render.filepath=str(PREVIEW/(cam.name+'.png'))
        bpy.ops.render.render(write_still=True)
    COLS['Ceilings'].hide_render=True;COLS['Context'].hide_render=True
    bpy.data.objects['Conditional / canopy'].hide_render=True
    # Cut only the architecture above 1.2m so door openings are readable in plan.
    for cname in ['Walls','Doors','Windows']:
        for ob in COLS[cname].objects:
            if ob.type!='MESH': continue
            if min((ob.matrix_world@v.co).z for v in ob.data.vertices)>=1.2:
                ob.hide_render=True
            else:
                ob.data=ob.data.copy()
                for v in ob.data.vertices:
                    v.co.z=min(v.co.z,1.2-ob.location.z)
    scene.camera=top;scene.render.resolution_x=W;scene.render.resolution_y=H
    scene.render.pixel_aspect_x=SX/SY;scene.render.pixel_aspect_y=1
    scene.render.filepath=str(PREVIEW/'05-top.png');bpy.ops.render.render(write_still=True)
