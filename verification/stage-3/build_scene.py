"""Build a separate finish concept from the immutable, approved stage-2 blend.
Blender --background --python-exit-code 1 --python verification/stage-3/build_scene.py
Rendering and validation are deliberately separate fresh-process operations.
"""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent
STYLE=json.loads((HERE/'style.json').read_text())
BASE=ROOT/'models/section-1/section-1-geometry.blend'
OUT=ROOT/'models/section-1/section-1-finish.blend'
assert hashlib.sha256(BASE.read_bytes()).hexdigest()==STYLE['source_blend_sha256']
bpy.ops.wm.open_mainfile(filepath=str(BASE))
scene=bpy.context.scene
CAL=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
SX,SY=CAL['mm_per_png_pixel_x']/1000,CAL['mm_per_png_pixel_y']/1000
PORTALS=json.loads((ROOT/'verification/stage-2/scene-section.json').read_text())['portals']

def p(x,y,z): return Vector((x*SX,-y*SY,z))
def srgb(h):
    c=[int(h[i:i+2],16)/255 for i in (1,3,5)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)
def newcol(name):
    c=bpy.data.collections.new(name);scene.collection.children.link(c);return c
FIN=newcol('Finish');FIX=newcol('Fixtures');NAV=newcol('Navigation');STROLLER=newcol('Stroller')
def material(name,color,rough=.7,metallic=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*srgb(color),1)
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=m.diffuse_color
    bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metallic
    return m
def node(m,kind):return m.node_tree.nodes.new(kind)
def wire(m,a,b):m.node_tree.links.new(a,b)
def calc(m,op,a,b=None):
    n=node(m,'ShaderNodeMath');n.operation=op
    for i,v in enumerate((a,b)):
        if v is None:continue
        if isinstance(v,(float,int)):n.inputs[i].default_value=v
        else:wire(m,v,n.inputs[i])
    return n.outputs[0]
def axes(m):
    g=node(m,'ShaderNodeNewGeometry');n=node(m,'ShaderNodeSeparateXYZ');wire(m,g.outputs['Position'],n.inputs[0]);return n.outputs
def noise(m,vector,scale,detail=3):
    n=node(m,'ShaderNodeTexNoise');n.inputs['Scale'].default_value=scale;n.inputs['Detail'].default_value=detail
    wire(m,vector,n.inputs['Vector']);return n.outputs['Fac']
def ramp(m,fac,colors):
    r=node(m,'ShaderNodeValToRGB')
    for i,(pos,color) in enumerate(colors):
        e=r.color_ramp.elements[i] if i<2 else r.color_ramp.elements.new(pos)
        e.position=pos;e.color=(*srgb(color),1)
    wire(m,fac,r.inputs[0]);return r.outputs['Color']
def mix(m,f,a,b):
    n=node(m,'ShaderNodeMixRGB');wire(m,f,n.inputs[0])
    for i,v in ((1,a),(2,b)):
        if isinstance(v,str):n.inputs[i].default_value=(*srgb(v),1)
        else:wire(m,v,n.inputs[i])
    return n.outputs[0]
def range_mask(m,v,lo,hi):return calc(m,'MULTIPLY',calc(m,'GREATER_THAN',v,lo),calc(m,'LESS_THAN',v,hi))
def stone(name,color,grout=True,corridor=False):
    m=material(name,color,.64);bs=m.node_tree.nodes.get('Principled BSDF')
    xyz=axes(m);pos=node(m,'ShaderNodeCombineXYZ')
    for k in ('X','Y','Z'):wire(m,xyz[k],pos.inputs[k])
    fac=noise(m,pos.outputs[0],7,4)
    base=srgb(color)
    n=node(m,'ShaderNodeMixRGB');n.blend_type='MULTIPLY';n.inputs[0].default_value=.28
    n.inputs[1].default_value=(*base,1);wire(m,fac,n.inputs[2]);colorout=n.outputs[0]
    if corridor:
        border=None
        # Strips beside main walls; intentional breaks at doors and branch junctions.
        spans=[(54,54+.11/SX,56.3,340),(54,54+.11/SX,435,777),
               (54,54+.11/SX,872,1155.8),(170.3-.11/SX,170.3,56.3,150),
               (170.3-.11/SX,170.3,266,317.2),(170.3-.11/SX,170.3,545,765),
               (170.3-.11/SX,170.3,847,957),(170.3-.11/SX,170.3,1054,1155.8),
               (180,383.1,346.8,346.8+.11/SY),(180,230,509.9-.11/SY,509.9),
               (332,383.1,509.9-.11/SY,509.9)]
        for x0,x1,y0,y1 in spans:
            f=calc(m,'MULTIPLY',range_mask(m,xyz['X'],x0*SX,x1*SX),range_mask(m,xyz['Y'],-y1*SY,-y0*SY))
            border=f if border is None else calc(m,'MAXIMUM',border,f)
        colorout=mix(m,border,colorout,'#403C35')
    if grout:
        seam=None
        for ax in ('X','Y'):
            mod=calc(m,'PINGPONG',xyz[ax],STYLE['tile_module_m']/2)
            f=calc(m,'LESS_THAN',mod,STYLE['joint_width_m']/2)
            seam=f if seam is None else calc(m,'MAXIMUM',seam,f)
        colorout=mix(m,seam,colorout,'#817663')
        bump=node(m,'ShaderNodeBump');bump.inputs['Distance'].default_value=.0012;bump.inputs['Strength'].default_value=.35
        wire(m,calc(m,'SUBTRACT',1,seam),bump.inputs['Height']);wire(m,bump.outputs[0],bs.inputs['Normal'])
    wire(m,colorout,bs.inputs['Base Color']);return m

P=STYLE['palette']
wall=material('M01 / warm mineral white',P['wall'],.86)
wxyz=axes(wall);wire(wall,mix(wall,calc(wall,'LESS_THAN',wxyz['Z'],.12),P['wall'],P['charcoal']),wall.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
ceiling=material('M02 / warm white ceiling',P['ceiling'],.9)
wallplain=material('M01E / facade light return',P['wall'],.86)
floor=stone('M03 / beige stone 600 mm',P['floor'])
corridor=stone('M03C / beige stone with flush border',P['floor'],corridor=True)
entry=stone('M04 / darker tambour stone',P['entry_floor'])
outside=stone('M05 / outdoor rough stone',P['outdoor_floor'])
dark=material('M06 / graphite powder coat',P['charcoal'],.48,.25)
contact=stone('M07 / contact-zone stone',P['contact'],False)
wood=material('M08 / vertical warm wood',P['wood'],.56)
g=node(wood,'ShaderNodeNewGeometry');scale=node(wood,'ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(48,48,1.5);wire(wood,g.outputs['Position'],scale.inputs[0])
grain=noise(wood,scale.outputs[0],1,3)
wo=ramp(wood,grain,[(.20,'#644329'),(.78,'#8E6847'),(.47,'#785338')]);wire(wood,wo,wood.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
bum=node(wood,'ShaderNodeBump');bum.inputs['Strength'].default_value=.12;bum.inputs['Distance'].default_value=.001;wire(wood,grain,bum.inputs['Height']);wire(wood,bum.outputs[0],wood.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
metal=material('M09 / satin dark elevator steel','#625D55',.32,.78)
glass=material('M10 / clear glazing','#EEF5F4',.025)
bs=glass.node_tree.nodes.get('Principled BSDF');bs.inputs['Transmission Weight'].default_value=1;bs.inputs['IOR'].default_value=1.45

def brick(name,orient):
    m=material(name,P['facade_brick'],.86);xyz=axes(m);v=node(m,'ShaderNodeCombineXYZ')
    wire(m,xyz[orient],v.inputs['X']);wire(m,xyz['Z'],v.inputs['Y'])
    b=node(m,'ShaderNodeTexBrick');wire(m,v.outputs[0],b.inputs['Vector'])
    b.inputs['Scale'].default_value=1;b.inputs['Brick Width'].default_value=.25;b.inputs['Row Height'].default_value=.065
    b.inputs['Mortar Size'].default_value=.0025;b.inputs['Color1'].default_value=(*srgb('#8D7567'),1);b.inputs['Color2'].default_value=(*srgb('#A68D7B'),1);b.inputs['Mortar'].default_value=(*srgb('#655F56'),1)
    wire(m,b.outputs['Color'],m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    bump=node(m,'ShaderNodeBump');bump.inputs['Strength'].default_value=.25;bump.inputs['Distance'].default_value=.003;bump.invert=True;wire(m,b.outputs['Fac'],bump.inputs['Height']);wire(m,bump.outputs[0],m.node_tree.nodes.get('Principled BSDF').inputs['Normal']);return m
brickx=brick('M11 / EP facade brick, east face','Y');bricky=brick('M11 / EP facade brick, north return','X')
def assign(ob,m):ob.data.materials.clear();ob.data.materials.append(m)
for ob in list(bpy.data.objects):
    if ob.type!='MESH':continue
    cn={c.name for c in ob.users_collection}
    if 'Walls' in cn:assign(ob,wall)
    elif 'Ceilings' in cn:assign(ob,ceiling)
    elif 'Floors' in cn:assign(ob,entry if 'тамбур' in ob.name or ob.name.startswith('S1-17/') else corridor if 'коридор' in ob.name else floor)
    elif 'Doors' in cn or 'Windows' in cn:
        assign(ob,glass if ('glass' in ob.name or 'pane' in ob.name and 'panel' not in ob.name) else metal if ob.get('opening_id')=='S1-14' else dark)
    elif 'Exterior' in cn:assign(ob,dark if any(s in ob.name for s in ('railing','canopy')) else outside)
    elif 'Proxies' in cn and 'lift' in ob.name:assign(ob,metal)
    elif ob.name.startswith('Context / facade'):assign(ob,bricky if 'north' in ob.name else brickx)
    elif 'Stairs' in cn and not ('guard' in ob.name or 'rail' in ob.name or 'post' in ob.name):
        if max((ob.matrix_world@v.co).z for v in ob.data.vertices)<=1.651:assign(ob,floor)
    if ob.get('wall_id') in ('W12','W21'):
        ob.data.materials.append(brickx)
        for poly in ob.data.polygons:
            if poly.normal.x>.9:poly.material_index=1
    elif ob.get('wall_id')=='W04':
        ob.data.materials.append(bricky)
        for poly in ob.data.polygons:
            if poly.normal.y<-.9:poly.material_index=1
    elif ob.get('wall_id')=='W13' and min((ob.matrix_world@v.co).x for v in ob.data.vertices)>481*SX:
        ob.data.materials.append(wallplain)
        for poly in ob.data.polygons:
            if poly.normal.y<-.9:poly.material_index=1

def link(ob,col,mat):
    for c in list(ob.users_collection):c.objects.unlink(ob)
    col.objects.link(ob);ob['status']='stage3_concept';ob.data.materials.append(mat);return ob
def box(name,loc,dims,mat,col=FIN,bevel=.0015):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);link(o,col,mat)
    if bevel:
        mod=o.modifiers.new('Edge radius','BEVEL');mod.width=bevel;mod.segments=3
        o.modifiers.new('Corner normals','WEIGHTED_NORMAL')
    return o
def rect(name,r,z0,z1,mat,col=FIN):
    x0,y0,x1,y1=r;return box(name,p((x0+x1)/2,(y0+y1)/2,(z0+z1)/2),((x1-x0)*SX,(y1-y0)*SY,z1-z0),mat,col)

# A single wood plane; joints divide it into replaceable panels. No boundary object closes the niche.
for i in range(5):
    a=181.5+(386-181.5)*i/5;b=181.5+(386-181.5)*(i+1)/5-.15
    rect(f'F / stroller wood panel {i+1}',[a,56.3,b,57.3],.78,3,wood)
rect('F / stroller contact panel',[181.5,56.3,386,57.35],.12,.778,contact)
# Lift jamb finishes stop at the source clear opening.
for a,b in ((215,237),(325.5,348)):
    rect('F / lift wood',[a,508.9,b,509.9],.12,2.72,wood)
rect('F / lift overpanel',[237,509.0,325.5,509.9],2.102,2.72,dark)
rect('F / lift reveal L',[236.4,510,238.4,523.5],0,2.1,dark)
rect('F / lift reveal R',[324.1,510,326.1,523.5],0,2.1,dark)
box('F / lift call plate',p(365,508.8,1.08),(.085,.012,.19),metal,FIN,.009)
box('F / lift call button',p(365,508.15,1.08),(.027,.004,.027),dark,FIN,.006)
# Door thresholds remain at their original height; decorative floor lines are shader masks.

# Dark portal around the principal entrance, with unobstructed original opening.
rect('F / entrance portal north',[740.2,72,741.5,86.4],-.01,2.55,dark)
rect('F / entrance portal south',[740.2,189,741.5,242],-.01,2.55,dark)
rect('F / entrance portal top',[740.2,72,741.5,242],2.405,2.55,dark)

for ob in list(bpy.data.collections['Lights'].objects):bpy.data.objects.remove(ob,do_unlink=True)
def area(name,loc,energy,w,h,color,target=None,col=FIX):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='RECTANGLE';d.size=w;d.size_y=h;d.color=color
    o=bpy.data.objects.new(name,d);col.objects.link(o);o.location=loc
    if target is not None:o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o
emission=material('L / 3000K diffuser','#FFF0D2',.4)
bs=emission.node_tree.nodes.get('Principled BSDF');bs.inputs['Emission Color'].default_value=(1,.70,.40,1);bs.inputs['Emission Strength'].default_value=5
def linear(name,x,y,along_y=True,power=35,z=2.98):
    l=.90;w=.065;dz=.032;center=p(x,y,z-dz/2)
    box(name+' / body',center,(w,l,dz) if along_y else (l,w,dz),dark,FIX,.003)
    box(name+' / diffuser',center+Vector((0,0,-dz/2-.001)),(.035,l-.04,.002) if along_y else (l-.04,.035,.002),emission,FIX,.001)
    o=area(name+' / source',center+Vector((0,0,-dz/2-.004)),power,w,l,(1,.78,.54))
    if not along_y:o.rotation_euler.z=math.pi/2

for i,(x,y,vertical,power) in enumerate([(292,108,False,28),(456,130,True,40),(423,266,False,40),(230,270,False,28),
    (660,130,True,28),(673,260,True,24),(112,150,True,25),(112,292,True,25),
    (112,465,True,30),(112,620,True,25),(112,790,True,25),(112,960,True,25),(112,1110,True,25),(287,430,False,32)]):
    linear(f'L{i+1:02d}',x,y,vertical,power)
linear('LE1',790,136,True,38,2.69)
linear('LS1',438,391,True,32,2.98)
# Soft daylight comes from outside openings; no invisible interior fill is used.
area('Daylight / west windows',p(-130,580,4.5),850,8,6,(.79,.87,1),p(120,580,1.2))
area('Daylight / entrance',p(1100,60,5),600,7,6,(.84,.9,1),p(720,135,1.4))
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.8,.92,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.3

font=bpy.data.fonts.load('/System/Library/Fonts/Supplemental/Arial.ttf')
signlight=material('N / ivory lettering','#EBE1CE',.6)
def text(name,body,loc,rot,size,mat=dark):
    d=bpy.data.curves.new(name,'FONT');d.body=body;d.font=font;d.size=size;d.extrude=.0007;d.space_character=1.12
    o=bpy.data.objects.new(name,d);NAV.objects.link(o);o.location=loc;o.rotation_euler=rot;d.materials.append(mat);return o
# Local text X follows world X, Y follows Z; the front faces into the room (-Y).
text('N / stroller label','КОЛЯСОЧНАЯ',p(214,57.7,1.80),(math.pi/2,0,0),.082,signlight)
text('N / floor number','1',p(377,508.4,1.60),(math.pi/2,0,math.pi),.29)
text('N / floor label','ЭТАЖ',p(375,508.4,1.47),(math.pi/2,0,math.pi),.045)
text('N / exterior number','1',p(742,229,1.62),(math.pi/2,0,math.pi/2),.36,signlight)
text('N / exterior label','СЕКЦИЯ',p(742,234,1.52),(math.pi/2,0,math.pi/2),.05,signlight)

def line(name,pts,r,mat,col=FIN):
    d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D';d.resolution_u=2;d.bevel_depth=r;d.bevel_resolution=3
    s=d.splines.new('POLY');s.points.add(len(pts)-1)
    for v,co in zip(s.points,pts):v.co=(*co,1)
    o=bpy.data.objects.new(name,d);col.objects.link(o);d.materials.append(mat);return o
def ring(name,c,ra,rb,mat,col=FIN,axis='Y',tube=.012):
    pts=[]
    for i in range(65):
        a=2*math.pi*i/64
        q=(ra*math.cos(a),0,rb*math.sin(a)) if axis=='Y' else (ra*math.cos(a),rb*math.sin(a),0)
        pts.append(Vector(c)+Vector(q))
    return line(name,pts,tube,mat,col)
# Clear line pictogram on the wood wall.
icon=p(282,57.8,2.02)
line('N / stroller icon', [icon+Vector(v) for v in [(-.15,0,.03),(-.11,0,-.10),(.13,0,-.10),(.18,0,.1),(.23,0,.1)]],.009,signlight,NAV)
line('N / stroller hood icon',[icon+Vector((-.14+.14*math.cos(t),0,.025+.14*math.sin(t))) for t in [math.pi*i/32 for i in range(33)]],.008,signlight,NAV)
for x in (-.085,.095):ring('N / stroller wheel icon',icon+Vector((x,0,-.175)),.035,.035,signlight,NAV,tube=.008)

# Only the old scale proxy is replaced. One model remains within the accepted 1.00 x 0.62 m envelope.
for ob in list(bpy.data.collections['Proxies'].objects):
    if ob.name.startswith(('Proxy / stroller','Proxy / wheel')):bpy.data.objects.remove(ob,do_unlink=True)
C=p(310,100,0)
rubber=material('S / rubber','#22211F',.83);frame=material('S / graphite frame','#383732',.3,.65)
fabric=material('S / woven sand textile','#998977',.9);liner=material('S / lining','#D3C6B3',.92)
ax=node(fabric,'ShaderNodeTexNoise');ax.inputs['Scale'].default_value=240;ax.inputs['Detail'].default_value=2
bu=node(fabric,'ShaderNodeBump');bu.inputs['Distance'].default_value=.0005;bu.inputs['Strength'].default_value=.22;wire(fabric,ax.outputs['Fac'],bu.inputs['Height']);wire(fabric,bu.outputs[0],fabric.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
for x,r in ((-.30,.115),(.30,.09)):
    for y in (-.255,.255):
        c=C+Vector((x,y,r));ring('S / tire',c,r-.022,r-.022,rubber,STROLLER,tube=.022)
        ring('S / rim',c,r*.59,r*.59,frame,STROLLER,tube=.01)
        for a in range(5):
            th=2*math.pi*a/5;line('S / spoke',[c,c+Vector((math.cos(th)*r*.59,0,math.sin(th)*r*.59))],.006,frame,STROLLER)
        line('S / cross chassis',[c,C+Vector((-x*.55,y*.85,.59))],.012,frame,STROLLER)
box('S / storage basket',C+Vector((0,0,.29)),(.48,.38,.13),fabric,STROLLER,.05)
box('S / bassinet',C+Vector((.015,0,.63)),(.74,.47,.24),fabric,STROLLER,.075)
box('S / inner cushion',C+Vector((.06,0,.755)),(.60,.385,.034),liner,STROLLER,.035)
# Curved hood: half cylinder across the width, stretching from the rear over the head end.
verts=[];faces=[];nx=8;na=32
for ix in range(nx+1):
    x=-.35+.32*ix/nx
    for ia in range(na+1):
        a=math.pi*ia/na;verts.append(tuple(C+Vector((x,.249*math.cos(a),.754+.278*math.sin(a)))))
for ix in range(nx):
    for ia in range(na):
        i=ix*(na+1)+ia;faces.append((i,i+1,i+na+2,i+na+1))
mesh=bpy.data.meshes.new('S / curved hood');mesh.from_pydata(verts,[],faces);mesh.update()
ob=bpy.data.objects.new('S / curved hood',mesh);STROLLER.objects.link(ob);mesh.materials.append(fabric)
sol=ob.modifiers.new('Textile thickness','SOLIDIFY');sol.thickness=.004
for f in mesh.polygons:f.use_smooth=True
for x in (-.35,-.19,-.03):line('S / hood seam',[C+Vector((x,.25*math.cos(a),.754+.28*math.sin(a))) for a in [math.pi*i/32 for i in range(33)]],.002,liner,STROLLER)
for y in (-.22,.22):line('S / handle',[C+Vector(v) for v in [(-.26,y,.52),(-.47,y,.96),(-.47,y,1.02)]],.012,frame,STROLLER)
line('S / handle grip',[C+Vector((-.47,-.22,1.02)),C+Vector((-.47,.22,1.02))],.018,rubber,STROLLER)

# Convert curves with physical volume to editable mesh for collision checks.
for col in (FIN,STROLLER):
    for ob in list(col.objects):
        if ob.type=='CURVE':
            bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH')

# The original upper slabs and ceiling overlap at exactly z=3. Rendering both
# coincident undersides produces black Cycles artifacts. Keep the source solids
# intact for geometry checks, use render copies with only duplicate faces omitted.
RF=newcol('RenderFix')
for name in ('Stair / second-floor landing','Stair / second-floor corridor'):
    original=bpy.data.objects[name]
    vertices=[original.matrix_world@v.co for v in original.data.vertices]
    faces=[list(face.vertices) for face in original.data.polygons
           if not all(abs(vertices[i].z-3)<1e-5 for i in face.vertices)]
    if name.endswith('landing'):
        start=len(vertices)
        vertices.extend([p(383.1,346.8,3),p(594.3,346.8,3),p(594.3,509.9,3),p(383.1,509.9,3)])
        faces.append(tuple(range(start,start+4)))
    mesh=bpy.data.meshes.new('Render / '+name);mesh.from_pydata(vertices,[],faces);mesh.update()
    ob=bpy.data.objects.new('Render / '+name,mesh);RF.objects.link(ob);mesh.materials.append(ceiling)
    original.hide_render=True;ob['source_object']=name;ob['purpose']='omit duplicate coplanar underside only'

top=bpy.data.objects['05-top'];top.location=(510*SX,-606*SY,26);top.rotation_euler=(0,0,0)
top.data.ortho_scale=1040*SX;top.data.sensor_fit='HORIZONTAL'
for cfg in STYLE['cameras']:
    o=bpy.data.objects[cfg['name']];o.location=p(*cfg['position_png'],cfg['height'])
    o.rotation_euler=(p(*cfg['target_png'],cfg['target_height'])-o.location).to_track_quat('-Z','Y').to_euler()
    o.data.lens=cfg['lens'];o['label']=cfg['label'];o.data.clip_start=.03
scene.render.engine='CYCLES';scene.cycles.samples=96;scene.cycles.use_denoising=True
scene.cycles.max_bounces=10;scene.cycles.transmission_bounces=8;scene.cycles.transparent_max_bounces=16
scene.render.resolution_x=1920;scene.render.resolution_y=1280;scene.render.resolution_percentage=100
scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=1
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=0
scene.camera=bpy.data.objects['02-lobby'];scene.render.filepath='//../../verification/stage-3/previews/02-lobby.png'
scene['purpose']='Stage 3 / section 1 / first review, not style approval'
scene['stage3_style_json']=json.dumps(STYLE,ensure_ascii=False)
scene['stage3_base_sha256']=STYLE['source_blend_sha256']
bpy.ops.file.pack_all()
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print('STAGE3_SCENE_SAVED',OUT)
