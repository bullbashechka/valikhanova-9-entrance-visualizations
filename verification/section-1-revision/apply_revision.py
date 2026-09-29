"""Approved section-1 deltas, executed in the finish builder namespace."""
# The two inserts surround the apartment door in the internal wall W23.
for oid in ('S1-32','S1-33'):
    for ob in list(bpy.data.objects):
        if ob.get('opening_id')==oid or ob.get('source_id')==oid:
            bpy.data.objects.remove(ob,do_unlink=True)
    opening=PORTALS[oid]
    ob=rect('Revision / wall infill '+oid,opening['rect'],.9,2.4,wall,bpy.data.collections['Walls'])
    ob['wall_id']='W23';ob['revision_closed_opening']=oid
    # Continuous interior baseboard already exists below the former sill.
data=json.loads(scene['geometry_data_json'])
for oid in ('S1-32','S1-33'):data['openings'].pop(oid)
for w in data['walls']:
    if w['id']=='W23':w['openings']=['S1-24']
scene['geometry_data_json']=json.dumps(data,ensure_ascii=False)

# One metal door leaf with an actual small frosted opening, preserving its hinge.
frost=material('Revision / frosted door glazing','#D5D9D5',.48)
bs=frost.node_tree.nodes.get('Principled BSDF');bs.inputs['Transmission Weight'].default_value=1;bs.inputs['IOR'].default_value=1.45
old=[o for o in bpy.data.objects if o.get('opening_id')=='S1-19' and 'leaf_index' in o]
props={k:(list(old[0][k]) if k=='hinge_world' else old[0][k]) for k in ('opening_id','leaf_index','hinge_world','open_angle')}
coords=[o.matrix_world@v.co for o in old for v in o.data.vertices]
xc=(594.3+633.8)/2*SX;ya=-468.9*SY+.045;yb=-387.1*SY-.045
base=-1.05;top=base+2.4-.045
for ob in old:bpy.data.objects.remove(ob,do_unlink=True)
yc=(ya+yb)/2;wa=yc-.19;wb=yc+.19;z0=base+1.78;z1=z0+.28
DOORS=bpy.data.collections['Doors']
def doorpart(name,a,b,low,high,mat,depth=.055):
    ob=box('S1-19/revised-'+name,(xc,(a+b)/2,(low+high)/2),(depth,b-a,high-low),mat,DOORS,.0015)
    for k,v in props.items():ob[k]=v
    return ob
for name,a,b,lo,hi in [('bottom',ya,yb,base+.015,z0),('top',ya,yb,z1,top),('side-a',ya,wa,z0,z1),('side-b',wb,yb,z0,z1)]:doorpart(name,a,b,lo,hi,dark)
doorpart('frosted-pane',wa,wb,z0,z1,frost,.018)
for name,a,b,lo,hi in [('window-bottom',wa-.012,wb+.012,z0-.012,z0+.012),('window-top',wa-.012,wb+.012,z1-.012,z1+.012),('window-a',wa-.012,wa+.012,z0,z1),('window-b',wb-.012,wb+.012,z0,z1)]:doorpart(name,a,b,lo,hi,metal,.063)
handle=doorpart('handle',yb-.21,yb-.08,base+.98,base+1.005,metal,.13)

# A readable directional sign on the vestibule side of W13, before the route choice.
# From the entry camera this wall is between the stair and corridor doors.
text('N / lift direction','ЛИФТ  →',p(330,316.3,1.63),(math.pi/2,0,math.pi),.145,dark)

# Replace the proxy with a platform, mesh guards, guide tower and three controls.
for ob in list(bpy.data.objects):
    if ob.name.startswith('Proxy / lift'):bpy.data.objects.remove(ob,do_unlink=True)
EQUIP=newcol('Equipment')
steel=material('Equipment / graphite powder coat','#383D3E',.5,.5)
deckmat=material('Equipment / textured aluminium','#8B9190',.46,.65)
red=material('Equipment / emergency red','#B32822',.55)
white=material('Equipment / button face','#D6D9D6',.5)
# Remove the block below the platform: the upper landing outline is otherwise unchanged.
def cut(ob,x0,y0,x1,y1,z0,z1):
    cutter=rect('Temporary lift clearance',[x0,y0,x1,y1],z0,z1,dark,EQUIP)
    bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new('Lift travel pocket','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
cut(bpy.data.objects['Exterior / upper platform'],865,217,995.1,356.8,-1.3,.2)
cut(bpy.data.objects['Context / ground'],865,217,995.1,356.8,-1.3,-1.06)
rect('Equipment / well floor',[865,217,995,356.7],-1.21,-1.13,deckmat,EQUIP)
platform=rect('Equipment / moving deck',[868,220,966,356.5],-.08,-.01,deckmat,EQUIP)
platform['lift_moving']=True
# Raised platform flush with the landing; a short upper bridge covers the clearance.
rect('Equipment / upper bridge',[868,217,966,220],-.055,-.01,deckmat,EQUIP)
rect('Equipment / guide tower',[972,251,991,282],-1.13,1.60,steel,EQUIP)
rect('Equipment / guide rail',[969.5,255,972,278],-1.1,1.52,metal,EQUIP)

# Solid wire geometry grouped into one mesh per panel keeps the scene editable.
def guard(name,x0,y0,x1,y1,zbase,moving=True):
    a=p(x0,y0,zbase);b=p(x1,y1,zbase);u=(b-a).normalized();length=(b-a).length;angle=math.atan2(u.y,u.x)
    parts=[]
    def bar(label,start,end,lo,hi,width):
        c=a+u*((start+end)/2);c.z=(lo+hi)/2
        ob=box('Equipment / '+name+' / '+label,c,(end-start,width,hi-lo),steel,EQUIP,.001)
        ob.rotation_euler.z=angle;parts.append(ob)
    bar('bottom',0,length,zbase+.07,zbase+.105,.035);bar('top',0,length,zbase+1.04,zbase+1.08,.04)
    bar('post-a',0,.035,zbase,zbase+1.08,.04);bar('post-b',length-.035,length,zbase,zbase+1.08,.04)
    for i in range(1,int(length/.045)):
        s=i*.045;bar('mesh-v',s,s+.004,zbase+.105,zbase+1.04,.006)
    for i in range(1,21):
        z=zbase+.105+i*.044;bar('mesh-h',.035,length-.035,z,z+.004,.006)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in parts:ob.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join()
    ob=parts[0];ob.name='Equipment / '+name;ob['lift_moving']=moving
    return ob
for name,coords in [('west guard',(870,222,870,350)),('east guard',(964,222,964,350))]:guard(name,*coords,-.01)
# The southern gate travels with the platform; the upper gate stays at landing level.
lowgate=guard('lower gate',870,354,964,354,-.01)
uppergate=guard('upper landing gate',868,217.8,966,217.8,-.01,False)
lowgate['gate_role']='lower';uppergate['gate_role']='upper'
lowgate['gate_hinge']=list(p(870,354,-.01));lowgate['gate_angle']=-math.pi/2
uppergate['gate_hinge']=list(p(868,217.8,-.01));uppergate['gate_angle']=math.pi/2
rect('Equipment / moving control housing',[953,264,964,291],.43,.99,steel,EQUIP)['lift_moving']=True

def controls(name,loc,rot=0,moving=False):
    center=Vector(loc)
    ob=box('Equipment / '+name+' panel',center,(.13,.038,.25),steel,EQUIP,.009);ob.rotation_euler.z=rot;ob['lift_moving']=moving
    # Buttons face along local -Y. Markings distinguish call, motion and stop.
    from mathutils import Matrix
    rotm=Matrix.Rotation(rot,3,'Z')
    for i,(label,mat) in enumerate([('up',white),('down',white),('stop',red)]):
        c=center+rotm@Vector((0,-.026,.074-i*.074))
        o=box('Equipment / '+name+' '+label,c,(.030,.016,.030),mat,EQUIP,.006);o.rotation_euler.z=rot;o['lift_moving']=moving
    return ob
controls('onboard',p(952.5,277,.81),-math.pi/2,True)
# Approach-side pedestal sits beside, rather than in, the lower gate opening.
rect('Equipment / lower call post',[986,360,991,365],-1.06,.07,steel,EQUIP)
controls('lower call',p(988.5,365,-.04))
# Upper call panel is reachable before the upper gate on the landing side.
rect('Equipment / upper call post',[986,207,991,212],-.01,1.12,steel,EQUIP)
controls('upper call',p(988.5,207,1.01),math.pi)
# Subtle tread lines make the deck legible without a decorative floor pattern.
for i in range(1,15):
    ob=rect('Equipment / deck groove '+str(i),[870,222+i*8.5,964,222.5+i*8.5],-.010,-.009,steel,EQUIP);ob['lift_moving']=True
scene['revision_json']=json.dumps({'closed_openings':['S1-32','S1-33'],'apartment_door':'S1-24','basement_door':'S1-19','lift_travel_m':1.05,'lift_deck_rect_png':[868,220,966,356.5],'platform_state':'upper','equipment':'generic visual concept, not a product specification'},ensure_ascii=False)
# Small, ordinary luminaire for the visible basement landing; no daylight effect.
box('LB1 / wall-mounted body',p(593.1,500,.75),(.03,.24,.16),dark,FIX,.008)
box('LB1 / wall-mounted diffuser',p(591.85,500,.75),(.005,.21,.13),emission,FIX,.004)
area('LB1 / wall light',p(591.5,500,.75),12,.20,.12,(1,.78,.54),p(500,500,.75))
