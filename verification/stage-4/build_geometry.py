"""Blender 5.2: --background --python build_scene.py -- [--render] [--draft]."""
import bpy, csv, json, math, hashlib, sys
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / 'models' / 'section-2'
OUT.mkdir(parents=True, exist_ok=True)
PREVIEW = HERE / 'previews'
PREVIEW.mkdir(exist_ok=True)
DATA = json.loads((HERE/'geometry.json').read_text(encoding='utf-8'))
CAL = json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['2']
SX, SY = CAL['mm_per_png_pixel_x']/1000, CAL['mm_per_png_pixel_y']/1000
with (ROOT/'verification/stage-1/measurements.csv').open(encoding='utf-8-sig', newline='') as f:
    MEAS = {r['id']:r for r in csv.DictReader(f) if r['section']=='2'}
FLOORS = [r for r in json.loads((ROOT/'verification/stage-1/floor-contours.json').read_text(encoding='utf-8')) if r['section']==2]
PNG = ROOT/'plans/section-2-common-areas.png'
assert hashlib.sha256(PNG.read_bytes()).hexdigest()==CAL['png_sha256'], 'Source PNG changed'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection': bpy.data.collections.remove(c)
COLS = {}
for name in ['Walls','Floors','Ceilings','Doors','Windows','Stairs','Exterior','Proxies','Context','Cameras','Lights','Reference','UpperWalls','UpperCeilings','UpperWindows']:
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

def link(obj, collection, mat=None, status='graphical_estimate', source='PNG section 2'):
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
LEVELS=DATA['levels_m']
upper=DATA['upper_context']
all_walls=DATA['walls']+[dict(w,base=w.get('base',upper['base_m']),top=upper['top_m'],collection='UpperWalls') for w in upper['walls']]
for w in all_walls:
    r=w['rect']; vertical=(r[3]-r[1])>(r[2]-r[0]); axis=1 if vertical else 0
    lo,hi=r[axis],r[axis+2]; cursor=lo; zmin=w.get('base',0); zmax=w.get('top',DATA['height_m']); wall_collection=w.get('collection','Walls')
    cuts=[]
    for oid in w.get('openings',[]):
        o=DATA['openings'][oid]
        if 'range_png' in o: a,b=sorted(o['range_png'])
        else:
            m=MEAS[oid]
            a,b=sorted((float(m['y1' if vertical else 'x1']),float(m['y2' if vertical else 'x2'])))
        cuts.append((a,b,oid,o))
    for a,b,oid,o in sorted(cuts):
        assert lo<=a<b<=hi,(w['id'],oid)
        def part(start,end,bottom,top,suffix):
            if end-start>.0001 and top-bottom>.0001:
                q=r.copy();q[axis]=start;q[axis+2]=end
                ob=rect(w['id']+'/'+suffix,q,bottom,top,wall_collection); ob['wall_id']=w['id']; ob['expected_top_m']=top
        part(cursor,a,zmin,zmax,'solid-'+oid)
        part(a,b,zmin,o['base'],'sill-'+oid)
        part(a,b,o['base']+o['height'],zmax,'lintel-'+oid)
        q=r.copy();q[axis]=a;q[axis+2]=b
        PORTALS[oid]={'rect':q,'vertical':vertical,**o}
        cursor=b
    if cursor<hi:
        q=r.copy();q[axis]=cursor
        ob=rect(w['id']+'/solid',q,zmin,zmax,wall_collection); ob['wall_id']=w['id']; ob['expected_top_m']=zmax

for oid,o in PORTALS.items():
    r=o['rect']; vertical=o['vertical']; z=o['base']; h=o['height']
    if o['kind']=='open':
        rect(oid+'/threshold',r,z-.15,z,'Floors','floor'); continue
    a=pxy((r[0]+r[2])/2,r[1],z) if vertical else pxy(r[0],(r[1]+r[3])/2,z)
    b=pxy((r[0]+r[2])/2,r[3],z) if vertical else pxy(r[2],(r[1]+r[3])/2,z)
    u=(b-a).normalized(); length=(b-a).length; angle=math.atan2(u.y,u.x)
    collection=('UpperWindows' if oid.startswith('S2-U2') else 'Windows') if o['kind']=='window' else 'Doors'
    moving_leaf=None
    def leaf(index,offset,sign):
        pivot=a+u*(length-fw if offset else fw)
        return {'leaf_index':index,'hinge_world':list(pivot),'open_angle':sign*o.get('swing',1)*(1 if vertical else -1)*math.radians(o.get('open_angle_degrees',90))}
    def slab(s,e,base,top,mat,name,depth=.055):
        c=a+u*((s+e)/2);c.z=(base+top)/2
        ob=box(oid+'/'+name,c,(e-s,depth,top-base),collection,mat,o['status'],angle)
        ob['opening_id']=oid
        if moving_leaf is not None:
            for key,value in moving_leaf.items(): ob[key]=value
        return ob
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
        ranges=[(fw,split),(split,length-fw)] if o['leaf_count']==2 else [(fw,length-fw)]
        for j,(s,e) in enumerate(ranges):
            at_end=(j==1) if o['leaf_count']==2 else o.get('hinge')=='end'
            moving_leaf=leaf(j,length if at_end else 0,-1 if at_end else 1)
            slab(s,e,z+.012,z+.095,'frame',f'leaf-{j}-bottom')
            slab(s,e,z+h-.085,z+h-fw,'frame',f'leaf-{j}-top')
            slab(e-.04,e,z+.095,z+h-.085,'frame',f'leaf-{j}-edge')
            slab(s,s+.04,z+.095,z+h-.085,'frame',f'leaf-{j}-hinge-edge')
            slab(s,e-.04,z+.095,z+h-.085,'glass',f'leaf-{j}-glass',.018)
            handle=(s+.09) if at_end else (e-.10)
            slab(handle,handle+.03,z+.85,z+1.15,'frame',f'leaf-{j}-handle',.12)
        moving_leaf=None
    else:
        if o['kind']=='lift':
            slab(fw,length/2-.007,z+.015,z+h-fw,'door','left-panel')
            slab(length/2+.007,length-fw,z+.015,z+h-fw,'door','right-panel')
        else:
            at_end=o.get('hinge')=='end'
            moving_leaf=leaf(0,length if at_end else 0,-1 if at_end else 1)
            slab(fw,length-fw,z+.015,z+h-fw,'door','closed-leaf')
            handle=fw+.06 if at_end else length-fw-.19
            slab(handle,handle+.13,z+.97,z+1.00,'frame','handle',.13)
            moving_leaf=None
    if o['kind']!='window': rect(oid+'/threshold',r,z-.15,z,'Floors','floor')
    empty=bpy.data.objects.new(oid+' / '+(MEAS[oid]['description'] if oid in MEAS else o['description']),None)
    COLS['Reference'].objects.link(empty);empty.location=(a+b)/2;empty.empty_display_size=.10
    empty['source_id']=oid;empty['width_m']=length;empty['height_m']=h;empty['status']=o['status']
    empty['leaf_count']=o['leaf_count']; empty['base_m']=z; empty['hinge']=o.get('hinge','none');empty['swing_side']=o.get('swing',0)

# Stair geometry is driven by level references and measured plan rectangles.
stairs=DATA['stairs']; rail_h=stairs['railing_height_m']; thickness=stairs['slab_thickness_m']
for landing in stairs['landings']:
    z=LEVELS[landing['level']]
    ob=rect('Stair / '+landing['id'],landing['rect'],z-landing.get('thickness_m',thickness),z,'Stairs','floor','derived_dimension')
    ob['level']=landing['level']; ob['source']='EP pages 17,20,23; user upper-door clarification'

def tread_wedge(name,x0,x1,y0,y1,top,bottom0,bottom1):
    # A sloping underside preserves clearance; no floor-to-tread solid blocks.
    verts=[tuple(pxy(x,y,z)) for x,y,z in [(x0,y0,bottom0),(x1,y0,bottom0),(x1,y1,bottom1),(x0,y1,bottom1),(x0,y0,top),(x1,y0,top),(x1,y1,top),(x0,y1,top)]]
    faces=[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    if y1<y0:faces=[tuple(reversed(face)) for face in faces]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);return link(ob,'Stairs','floor','conditional','EP page 23; equal risers and thickness assumed')

for flight in stairs['flights']:
    x0,yn,x1,ys=flight['rect']; start,end=(yn,ys) if flight['direction']==1 else (ys,yn)
    z0,z1=LEVELS[flight['from']],LEVELS[flight['to']]; rise=(z1-z0)/flight['risers']; count=flight['risers']-1
    for i in range(count):
        a=start+(end-start)*i/count;b=start+(end-start)*(i+1)/count
        bottom=z0+i*rise-thickness+min(rise,0)
        ob=tread_wedge(f"Stair / {flight['id']} tread {i+1}",x0,x1,a,b,z0+(i+1)*rise,bottom,bottom+rise)
        ob['flight_id']=flight['id'];ob['tread_index']=i+1
    railx=flight['rail_x']
    rod('Stair / '+flight['id']+' handrail',pxy(railx,start,z0+rail_h),pxy(railx,end,z1+rail_h),.022,'Stairs')
    for i in range(6):
        t=i/5;y=start+(end-start)*t
        # Place posts on actual tread heights, not an interpolated line through risers.
        z=z0 if i==0 else z1 if i==5 else z0+(int(t*count)+1)*rise
        rod('Stair / '+flight['id']+' post',pxy(railx,y,z),pxy(railx,y,z0+(z1-z0)*t+rail_h),.018,'Stairs')
for guard in stairs['guards']:
    z=LEVELS[guard['level']];a=pxy(*guard['a'],z);b=pxy(*guard['b'],z)
    rod('Stair / guard '+guard['id'],a+Vector((0,0,rail_h)),b+Vector((0,0,rail_h)),.022,'Stairs')
    for t in (0,.5,1):
        q=a.lerp(b,t);rod('Stair / guard post '+guard['id'],q,q+Vector((0,0,rail_h)),.018,'Stairs')
for i,r in enumerate(upper['ceilings']):
    rect('U2 / ceiling '+str(i),r,upper['top_m'],upper['top_m']+.30,'UpperCeilings','ceiling','conditional')


# Section 2 exterior: X-directed stair, independent of section 1 coordinates.
prism('Exterior / upper platform',DATA['exterior_platform_png'],-1.21,-.01,'Exterior','floor','project_elevation')
for i in range(6):
    a=487.6+(605.9-487.6)*i/6;b=487.6+(605.9-487.6)*(i+1)/6
    rect(f'Exterior / tread {i+1}',[a,137.6,b,216.4],-1.21,-.01-(i+1)*.15,'Exterior','floor','derived_dimension')
rect('Exterior / lower approach',[605.9,110,740,245],-1.21,-1.06,'Exterior','ground','project_elevation')
rect('Proxy / lift platform',[567.8,232.7,646.6,311.5],-.01,.06,'Proxies','proxy','conditional')
for x,y in [(571,237),(643,237),(643,308),(571,308)]:
    rod('Proxy / lift post',pxy(x,y,.06),pxy(x,y,.98),.025,'Proxies')
rod('Proxy / lift top side',pxy(571,237,.98),pxy(643,237,.98),.025,'Proxies')
rod('Proxy / lift guide',pxy(643,307,-1.06),pxy(643,307,1.3),.035,'Proxies')
for a,b,z0,z1 in [((395,137.6),(487.6,137.6),-.01,-.01),((487.6,137.6),(605.9,137.6),-.01,-1.06),((567.8,315),(567.8,367),-.01,-.01)]:
    rod('Conditional / railing top',pxy(*a,z0+1),pxy(*b,z1+1))
    for t in [0,.5,1]:
        x=a[0]+(b[0]-a[0])*t;y=a[1]+(b[1]-a[1])*t;z=z0+(z1-z0)*t
        rod('Conditional / railing post',pxy(x,y,z),pxy(x,y,z+1))
rect('Conditional / canopy',[395,122,568,320],2.7,2.85,'Exterior','wall','conditional')
rect('Context / ground',[370,-140,1150,430],-1.24,-1.075,'Context','ground','conditional')
# Non-designed facades close the cropped source at the edge of the entrance view.
rect('Context / facade north',[3.1,106,395,114.3],-1.2,6.3,'Context','wall','conditional')
rect('Context / facade east',[590,374.7,1030,410],3,6.3,'Context','wall','conditional')
# Closed service access panels face the stair approach; no service-room interiors.
for i,(a,b) in enumerate(((165,215),(230,285),(300,360))):
    rect('Context / utility panel '+str(i),[a,501,b,502],.18,2.1,'Doors','door','conditional')
scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='METERS';scene.unit_settings.scale_length=1
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.cycles.max_bounces=10;scene.cycles.transparent_max_bounces=16
scene.render.resolution_x=1920;scene.render.resolution_y=1280;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
for cfg in DATA['cameras']:
    d=bpy.data.cameras.new(cfg['name']);d.lens=cfg['lens'];d.clip_start=.03;d.clip_end=200
    o=bpy.data.objects.new(cfg['name'],d);COLS['Cameras'].objects.link(o)
    o.location=pxy(*cfg['position_png'],cfg['height'])
    o.rotation_euler=(pxy(*cfg['target_png'],cfg['target_height'])-o.location).to_track_quat('-Z','Y').to_euler()
    o['label']=cfg['label']
d=bpy.data.cameras.new('05-top');d.type='ORTHO';d.ortho_scale=690*SX;d.sensor_fit='HORIZONTAL'
o=bpy.data.objects.new('05-top',d);COLS['Cameras'].objects.link(o);o.location=pxy(345,505,26)
img=bpy.data.images.load(str(PNG));img.pack()
o=bpy.data.objects.new('Approved PNG / locked reference',None);COLS['Reference'].objects.link(o)
o.empty_display_type='IMAGE';o.data=img;o.hide_render=True;o.hide_viewport=True;o['sha256']=CAL['png_sha256']
scene['geometry_data_json']=json.dumps(DATA,ensure_ascii=False)
scene['purpose']='Stage 4 / section 2 / concept geometry'
scene['assumptions_json']=json.dumps(DATA['assumptions'],ensure_ascii=False)
scene.camera=bpy.data.objects['02-lobby']
bpy.ops.file.pack_all();bpy.context.view_layer.update()
# Export actual mesh sections; the S2-17 exception is documented, never hidden in source PNG.
segments=[]
for ob in COLS['Walls'].objects:
    verts=[ob.matrix_world@v.co for v in ob.data.vertices]
    for face in ob.data.polygons:
        hits=[];ids=list(face.vertices)
        for ia,ib in zip(ids,ids[1:]+ids[:1]):
            a,b=verts[ia],verts[ib]
            if (a.z-1.2)*(b.z-1.2)<0:
                q=a.lerp(b,(1.2-a.z)/(b.z-a.z));hits.append([q.x/SX,-q.y/SY])
        if len(hits)==2:segments.append({'object':ob.name,'points':hits})
(HERE/'scene-section.json').write_text(json.dumps({'cut_height_m':1.2,'segments':segments,'portals':PORTALS,'upper_door_exception':'S2-17 at +3.300 by user instruction'},ensure_ascii=False,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'section-2-geometry.blend'))
print('GEOMETRY_SAVED',len(bpy.data.objects))
