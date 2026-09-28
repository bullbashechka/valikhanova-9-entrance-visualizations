"""Geometry-based route checks on a reopened scene; dimensions are review proxies, not code compliance."""
import math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

def tree(ob):
    return BVHTree.FromPolygons([ob.matrix_world@v.co for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons])

def audit_routes(bpy, data, sx, sy):
    bodies=[]; supports=[]
    support_collections={'Floors','Stairs','Exterior','Context'}
    for ob in bpy.data.objects:
        if ob.type!='MESH':continue
        cols={c.name for c in ob.users_collection}
        if cols & {'Reference','Lights','Cameras'}:continue
        bodies.append((ob,tree(ob)))
        if (cols & support_collections and (ob.name.startswith(('Floor /','Stair /','Exterior /','Context / ground')) or ob.name.endswith('/threshold')) and not any(t in ob.name for t in ('handrail','post','guard'))):
            supports.append((ob,tree(ob)))
    result=[]
    def bounds(ob):
        v=[ob.matrix_world@Vector(c) for c in ob.bound_box]
        return [min(p[j] for p in v) for j in range(3)]+[max(p[j] for p in v) for j in range(3)]
    def surface(x,y,z):
        hits=[]
        for ob,t in supports:
            hit=t.ray_cast(Vector((x,y,z+.32)),Vector((0,0,-1)),.66)[0]
            if hit is not None:hits.append(hit.z)
        return max(hits) if hits else None
    for route in data['review_routes']:
        transforms={}
        for ob,_ in bodies:
            if ob.get('opening_id') in route['doors'] and 'leaf_index' in ob:
                transforms[ob.name]=ob.matrix_world.copy()
                pivot=Vector(ob['hinge_world'])
                ob.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(ob['open_angle'],4,'Z')@Matrix.Translation(-pivot)@ob.matrix_world
        bpy.context.view_layer.update()
        obstacles=[(ob.name,tree(ob) if ob.name in transforms else t,bounds(ob)) for ob,t in bodies]
        failures=[];count=0;last_z=None
        pts=[Vector((x*sx,-y*sy,z)) for x,y,z in route['points']]
        for a,b in zip(pts,pts[1:]):
            n=max(1,math.ceil((b-a).length/.04))
            for i in range(n+1):
                q=a.lerp(b,i/n);z=surface(q.x,q.y,q.z);count+=1
                if z is None:
                    failures.append({'kind':'no_support','at':[round(v,3) for v in q]});continue
                if last_z is not None and abs(z-last_z)>.151:
                    failures.append({'kind':'vertical_discontinuity','delta':round(z-last_z,4),'at':[round(v,3) for v in q]})
                last_z=z
                nearby=[(name,t) for name,t,r in obstacles if r[0]<=q.x+.301 and r[3]>=q.x-.301 and r[1]<=q.y+.301 and r[4]>=q.y-.301 and r[2]<=z+2.001 and r[5]>=z+.30]
                offsets=[Vector((0,0,0))]+[Vector((.30*math.cos(k*math.pi/4),.30*math.sin(k*math.pi/4),0)) for k in range(8)]
                for off in offsets:
                    floor=surface(q.x+off.x,q.y+off.y,z)
                    if floor is None or abs(floor-z)>.301:
                        failures.append({'kind':'unsupported_footprint','at':[round(q.x+off.x,3),round(q.y+off.y,3),round(z,3)]})
                    origin=Vector((q.x+off.x,q.y+off.y,z+.31))
                    for name,t in nearby:
                        hit=t.ray_cast(origin,Vector((0,0,1)),1.69)[0]
                        if hit is not None:
                            failures.append({'kind':'headroom','object':name,'height':round(hit.z-z,3)})
                for h in (.31,.7,1.2,1.7,1.99):
                    origin=Vector((q.x,q.y,z+h))
                    for k in range(8):
                        direction=Vector((math.cos(k*math.pi/4),math.sin(k*math.pi/4),0))
                        for name,t in nearby:
                            if t.ray_cast(origin,direction,.30)[0] is not None:
                                failures.append({'kind':'body_collision','object':name,'at':[round(v,3) for v in origin]})
        for name,m in transforms.items():bpy.data.objects[name].matrix_world=m
        bpy.context.view_layer.update()
        # Deduplicate repeated collisions while retaining the total incidence count.
        unique=[];seen=set()
        for f in failures:
            key=(f['kind'],f.get('object'),str(f.get('at')))
            if key not in seen:unique.append(f);seen.add(key)
        result.append({'name':'walkable_route/'+route['id'],'passed':not failures,'samples':count,'width_m':.60,'height_m':2.0,'failures':unique[:25],'failure_count':len(failures),'doors_opened':route['doors']})
    return result

def audit_door_sweeps(bpy):
    static=[]
    for ob in bpy.data.objects:
        if ob.type!='MESH':continue
        if not ({c.name for c in ob.users_collection} & {'Walls','UpperWalls','Ceilings','UpperCeilings','Stairs','Proxies','Exterior','Doors','Windows','UpperWindows'}):continue
        static.append((ob.name,tree(ob),ob.get('opening_id')))
    groups={}
    for ob in bpy.data.objects:
        if 'leaf_index' in ob:groups.setdefault(ob['opening_id'],[]).append(ob)
    checks=[]
    for oid,objects in groups.items():
        original={ob.name:ob.matrix_world.copy() for ob in objects};bad=set()
        for step in range(10):
            for ob in objects:
                pivot=Vector(ob['hinge_world'])
                ob.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(ob['open_angle']*step/9,4,'Z')@Matrix.Translation(-pivot)@original[ob.name]
            bpy.context.view_layer.update()
            for ob in objects:
                t=tree(ob)
                for name,other,opening_id in static:
                    if opening_id==oid:continue
                    if t.overlap(other):bad.add((round(abs(math.degrees(ob['open_angle']))*step/9,2),name))
        for ob in objects:ob.matrix_world=original[ob.name]
        bpy.context.view_layer.update()
        checks.append({'name':'door_sweep/'+oid,'passed':not bad,'max_angle_degrees':round(abs(math.degrees(objects[0]['open_angle'])),2),'samples':10,'collisions':[{'angle':a,'object':n} for a,n in sorted(bad)]})
    return checks
