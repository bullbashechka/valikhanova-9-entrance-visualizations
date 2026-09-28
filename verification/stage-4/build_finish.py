"""Build a separate section-2 finish from verified stage-4 geometry.
Blender --background --python-exit-code 1 --python verification/stage-4/build_finish.py
Rendering and validation are deliberately separate fresh-process operations.
"""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent
STYLE=json.loads((HERE/'style.json').read_text())
BASE=ROOT/'models/section-2/section-2-geometry.blend'
OUT=ROOT/'models/section-2/section-2-finish.blend'
checked=json.loads((HERE/'geometry-validation.json').read_text())
assert checked['all_pass'] and checked['blend_sha256']==hashlib.sha256(BASE.read_bytes()).hexdigest(), 'Verify current geometry before finish'
STYLE['source_blend_sha256']=hashlib.sha256(BASE.read_bytes()).hexdigest()
(HERE/'style.json').write_text(json.dumps(STYLE,ensure_ascii=False,indent=2))
bpy.ops.wm.open_mainfile(filepath=str(BASE))
scene=bpy.context.scene
CAL=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['2']
SX,SY=CAL['mm_per_png_pixel_x']/1000,CAL['mm_per_png_pixel_y']/1000
PORTALS=json.loads((HERE/'scene-section.json').read_text())['portals']

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
        spans=STYLE['corridor_border_spans']
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
    elif 'Ceilings' in cn or 'UpperCeilings' in cn:assign(ob,ceiling)
    elif 'UpperWalls' in cn:assign(ob,brickx if ob.get('wall_id')=='U2-east' else wallplain)
    elif 'Floors' in cn:assign(ob,entry if 'тамбур' in ob.name else corridor if 'коридор' in ob.name else floor)
    elif 'Doors' in cn or 'Windows' in cn:
        assign(ob,glass if ('glass' in ob.name or 'pane' in ob.name and 'panel' not in ob.name) else metal if ob.get('opening_id')=='S2-12' else dark)
    elif 'Exterior' in cn:assign(ob,dark if any(t in ob.name for t in ('railing','canopy')) else outside)
    elif 'Proxies' in cn:assign(ob,metal)
    elif 'Stairs' in cn:assign(ob,dark if any(t in ob.name for t in ('handrail','post','guard')) else floor)
    elif ob.name.startswith('Context / facade'):assign(ob,bricky)
    if ob.get('wall_id') in ('W04','W07','W19'):
        ob.data.materials.append(brickx if ob.get('wall_id')=='W04' else bricky)
        for poly in ob.data.polygons:
            if (poly.normal.x>.9 if ob.get('wall_id')=='W04' else poly.normal.y>.9):poly.material_index=1
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

# Open stroller niche: shared floor, protected contact wall, wood above.
for i in range(4):
    a=21+(202-21)*i/4;b=21+(202-21)*(i+1)/4-.15
    rect(f'F / stroller wood panel {i+1}',[a,122.3,b,123.3],.78,3,wood)
rect('F / stroller contact panel',[21,122.3,202,123.4],.12,.778,contact)
for a,b in ((199,234.8),(321.2,358)):
    rect('F / lift wood',[a,704,b,705],.12,2.75,wood)
rect('F / lift overpanel',[234.8,704,321.2,705],2.102,2.75,dark)
box('F / lift call plate',p(362,705.2,1.08),(.08,.014,.19),metal,FIN,.008)
box('F / lift call button',p(362,705.8,1.08),(.025,.004,.025),dark,FIN,.006)
# Repeating accents in the long L-shaped corridor. All surfaces remain outside door sweeps.
for i,(a,b) in enumerate(((450,505),(592,647))):
    rect(f'F / corridor west accent {i+1}',[29.1,a,30.1,b],.12,2.8,wood)
for i,(a,b) in enumerate(((280,327),(446,493),(570,617))):
    rect(f'F / corridor south accent {i+1}',[a,858.5,b,859.5],.12,2.8,wood)
# Entrance portal on the street face.
for a,b in ((193,204),(291,307)):
    rect('F / entrance portal side',[395,a,396,b],0,2.55,dark)
rect('F / entrance portal head',[395,193,396,307],2.405,2.55,dark)
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

for i,(x,y,vertical,power) in enumerate([(294,194,True,38),(294,325,True,38),(110,174,False,38),(110,310,False,40),(90,461,True,30),(90,600,True,30),(90,742,True,32),(227,805,False,32),(382,820,False,32),(535,820,False,32),(322,452,False,30)]):
    linear(f'L{i+1:02d}',x,y,vertical,power)
linear('LE1',449,245,True,40,2.68)
linear('LS1',435,452,True,32,2.98)
area('Daylight / entry',p(690,90,5),700,8,6,(.84,.9,1),p(390,250,1.4))
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.8,.92,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.3
font=bpy.data.fonts.load('/System/Library/Fonts/Supplemental/Arial.ttf')
signlight=material('N / ivory lettering','#EBE1CE',.6)
def text(name,body,loc,rot,size,mat=dark):
    d=bpy.data.curves.new(name,'FONT');d.body=body;d.font=font;d.size=size;d.extrude=.0007;d.space_character=1.12
    o=bpy.data.objects.new(name,d);NAV.objects.link(o);o.location=loc;o.rotation_euler=rot;d.materials.append(mat);return o
text('N / stroller label','КОЛЯСОЧНАЯ',p(57,124,1.78),(math.pi/2,0,0),.075,signlight)
text('N / floor number','1',p(278,705.3,2.37),(math.pi/2,0,0),.27,signlight)
text('N / floor label','ЭТАЖ',p(278,705.3,2.26),(math.pi/2,0,0),.044,signlight)
text('N / exterior number','2',p(396.5,342,1.67),(math.pi/2,0,math.pi/2),.35,signlight)
text('N / exterior label','СЕКЦИЯ',p(396.5,350,1.53),(math.pi/2,0,math.pi/2),.05,signlight)
bpy.data.objects['N / floor number'].data.align_x='CENTER'
bpy.data.objects['N / floor label'].data.align_x='CENTER'
# On tambour side of vestibule door; arrow points to that doorway, not toward street.
text('N / lift direction','ЛИФТ  →',p(222.1,340,1.65),(math.pi/2,0,math.pi/2),.085)
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
icon=p(118,124,2.04)
line('N / stroller icon', [icon+Vector(v) for v in [(-.15,0,.03),(-.11,0,-.10),(.13,0,-.10),(.18,0,.1),(.23,0,.1)]],.009,signlight,NAV)
line('N / stroller hood icon',[icon+Vector((-.14+.14*math.cos(t),0,.025+.14*math.sin(t))) for t in [math.pi*i/32 for i in range(33)]],.008,signlight,NAV)
for x in (-.085,.095):ring('N / stroller wheel icon',icon+Vector((x,0,-.175)),.035,.035,signlight,NAV,tube=.008)

# Only the old scale proxy is replaced. One model remains within the accepted 1.00 x 0.62 m envelope.
for ob in list(bpy.data.collections['Proxies'].objects):
    if ob.name.startswith(('Proxy / stroller','Proxy / wheel')):bpy.data.objects.remove(ob,do_unlink=True)
C=p(89,162,0)
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

newcol('RenderFix')
# The upper destination floor sits above exterior only; no overlapping first-floor ceilings.
for cfg in STYLE['cameras']:
    o=bpy.data.objects[cfg['name']];o.location=p(*cfg['position_png'],cfg['height'])
    o.rotation_euler=(p(*cfg['target_png'],cfg['target_height'])-o.location).to_track_quat('-Z','Y').to_euler()
    o.data.lens=cfg['lens'];o['label']=cfg['label'];o.data.clip_start=.03
scene.render.engine='CYCLES';scene.cycles.samples=96;scene.cycles.use_denoising=True
scene.cycles.max_bounces=10;scene.cycles.transmission_bounces=8;scene.cycles.transparent_max_bounces=16
scene.render.resolution_x=1920;scene.render.resolution_y=1280;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=0
scene.camera=bpy.data.objects['02-lobby'];scene['purpose']='Stage 4 / section 2 / concept for common review'
scene['stage4_style_json']=json.dumps(STYLE,ensure_ascii=False)
bpy.ops.file.pack_all();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print('FINISH_SAVED',len(bpy.data.objects))
