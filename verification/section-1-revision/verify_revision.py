from mathutils.bvhtree import BVHTree
from mathutils import Matrix
scene=bpy.context.scene
bpy.context.view_layer.update()
for oid in ('S1-21','S1-22','S1-23','S1-24'):
    leaf=bpy.data.objects[oid+'/closed-leaf']
    west=oid in ('S1-21','S1-22')
    inner_x=(54 if west else 170.3)*sx
    face=(max if west else min)((leaf.matrix_world@v.co).x for v in leaf.data.vertices)
    check('west door leaf flush with inner wall / '+oid,abs(face-inner_x)<.001)
    check('west door hinge follows leaf / '+oid,abs(leaf['hinge_world'][0]-leaf.location.x)<.001)
    check('west door frame and handle follow leaf / '+oid,all(abs(ob.location.x-leaf.location.x)<.001 for ob in bpy.data.objects if ob.get('opening_id')==oid))
for oid in ('S1-30','S1-31','S1-32','S1-33'):
    check('no old window geometry / '+oid,not any(o.get('opening_id')==oid for o in bpy.data.objects))
    ob=bpy.data.objects['Revision / wall infill '+oid]
    width=(54.0-24.4) if oid in ('S1-30','S1-31') else (189.8-170.3)
    check('solid full-depth wall / '+oid,abs(ob.dimensions.x-width*sx)<.001 and abs(ob.dimensions.z-1.5)<.001)
stair=bpy.data.objects['S1-18/closed-leaf']
check('stair door has nonmetal interior finish',stair.active_material.name=='M08 / vertical warm wood' and stair.active_material.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value==0)
label=bpy.data.objects['N / stair label']
check('stair sign identifies route',label.data.body=='ЛЕСТНИЦА' and label.data.align_x=='CENTER' and 2.1<label.location.z<2.4)
frost=bpy.data.materials['Revision / frosted door glazing'].node_tree.nodes.get('Principled BSDF')
check('small frosted insert in metal leaf',abs(bpy.data.objects['S1-19/revised-frosted-pane'].dimensions.y-.38)<.001 and frost.inputs['Roughness'].default_value>.4 and frost.inputs['Transmission Weight'].default_value==1)
sign=bpy.data.objects['N / lift direction'];cam=bpy.data.objects['01-entry']
check('sign faces arriving visitor', (sign.matrix_world.to_3x3()@Vector((0,0,1))).dot(cam.location-sign.location)>0 and sign.data.size>=.14)
check('sign text directs right',bpy.data.objects['N / lift direction'].data.body=='ЛИФТ  →')
check('three control stations present',all('Equipment / '+n+' panel' in bpy.data.objects for n in ('onboard','lower call','upper call')))
check('lift guide tower and gates present',all('Equipment / '+n in bpy.data.objects for n in ('guide tower','lower gate','upper landing gate')))
# Evaluate actual solid meshes across the full travel; touching support surfaces are excluded.
from audit_routes import tree
moving=[o for o in bpy.data.collections['Equipment'].objects if o.get('lift_moving') and o.type=='MESH']
static=[o for o in bpy.data.objects if o.type=='MESH' and not o.get('lift_moving') and ({c.name for c in o.users_collection}&{'Exterior','Context','Equipment','Walls','Doors'})]
static=[o for o in static if o.name not in ('Equipment / well floor','Equipment / upper bridge')]
obstacles=[(o.name,tree(o)) for o in static]
start={o.name:o.matrix_world.copy() for o in moving};collisions=[]
for fraction in (0,.25,.5,.75,1):
    for o in moving:o.matrix_world=Matrix.Translation((0,0,-1.05*fraction))@start[o.name]
    bpy.context.view_layer.update()
    for o in moving:
        t=tree(o)
        for n,bvh in obstacles:
            if t.overlap(bvh):collisions.append((fraction,o.name,n))
for o in moving:o.matrix_world=start[o.name]
bpy.context.view_layer.update()
check('platform travel clear of fixed geometry',not collisions,collisions=collisions[:20],states=5)
# Explicit conceptual wheelchair envelope, not an accessibility certification.
check('clear deck envelope for concept', (964-870)*sx-.04>=.70 and (354-222)*sy-.04>=1.20,width_m=(964-870)*sx-.04,length_m=(354-222)*sy-.04)
check('lower and upper deck levels',abs(bpy.data.objects['Equipment / moving deck'].location.z+.035+1.05-1.05-(-.01))<.001)
# Temporarily open the actual gates and test travel to/from a conceptual occupied deck.
for state,delta,start_y,end_y,gate_name in [('lower',-1.05,405,285,'lower gate'),('upper',0,285,165,'upper landing gate')]:
    for o in moving:o.matrix_world=Matrix.Translation((0,0,delta))@start[o.name]
    gate=bpy.data.objects['Equipment / '+gate_name];gate_matrix=gate.matrix_world.copy()
    pivot=Vector(gate['gate_hinge'])+Vector((0,0,delta if gate.get('lift_moving') else 0))
    gate.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(gate['gate_angle'],4,'Z')@Matrix.Translation(-pivot)@gate_matrix
    bpy.context.view_layer.update()
    objects=[(o,tree(o)) for o in bpy.data.objects if o.type=='MESH' and not ({c.name for c in o.users_collection}&{'Reference','Cameras','Lights'})]
    failures=[];level=-.01+delta
    for step in range(41):
        y=(start_y+(end_y-start_y)*step/40)*-sy;x=917*sx
        for dx in (-.35,0,.35):
            for dy in (-.60,0,.60):
                origin=Vector((x+dx,y+dy,level+.12));hits=[]
                for o,t in objects:
                    hit=t.ray_cast(origin,Vector((0,0,-1)),.30)[0]
                    if hit is not None:hits.append(hit.z)
                if not hits or abs(max(hits)-level)>.021:failures.append('support')
                origin.z=level+.08
                for o,t in objects:
                    if t.ray_cast(origin,Vector((0,0,1)),1.72)[0] is not None:failures.append(o.name)
    check('lift access with open gate / '+state,not failures,footprint_m=[.70,1.20],height_m=1.80,failures=sorted(set(failures)))
    gate.matrix_world=gate_matrix
    for o in moving:o.matrix_world=start[o.name]
    bpy.context.view_layer.update()
check('native render defaults ready for delivery',scene.render.resolution_x==2560 and scene.render.resolution_y==1707 and scene.render.filepath=='//section-1-render.png')
