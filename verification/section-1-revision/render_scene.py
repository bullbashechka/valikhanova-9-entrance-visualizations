"""Render the saved scene without saving any camera-specific visibility changes."""
import bpy, sys, json, math, hashlib
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
style=json.loads((HERE/'style.json').read_text());scene=bpy.context.scene
assert json.loads(scene['stage3_style_json'])==style,'Rebuild scene after style changes'
draft='--draft' in sys.argv
device='CPU'
if '--cpu' not in sys.argv:
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='METAL';prefs.get_devices()
        if any(d.type=='METAL' for d in prefs.devices):
            for d in prefs.devices:d.use=d.type=='METAL'
            scene.cycles.device='GPU';device='METAL'
    except (TypeError,RuntimeError):pass
out=HERE/('drafts' if draft else 'previews');out.mkdir(exist_ok=True)
selected=sys.argv[sys.argv.index('--cameras')+1].split(',') if '--cameras' in sys.argv else ['01-entry','02-lobby','03-lift','04-exterior','05-top']
scene.render.resolution_x=960 if draft else 2560;scene.render.resolution_y=640 if draft else 1707
scene.cycles.samples=24 if draft else 128
scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
for name in selected:
    if name=='05-top':continue
    print('RENDER_START',name,'device',device,flush=True)
    scene.camera=bpy.data.objects[name];scene.render.filepath=str(out/(name+'.png'))
    bpy.ops.render.render(write_still=True)
if '05-top' in selected:
    for name in ('Ceilings','UpperWalls','UpperWindows','UpperCeilings','Context','Fixtures','Navigation','RenderFix'):
        bpy.data.collections[name].hide_render=True
    bpy.data.objects['Conditional / canopy'].hide_render=True
    for ob in bpy.data.collections['Stairs'].objects:
        if ob.get('level')=='second_floor' or 'upper void' in ob.name:ob.hide_render=True
    for cname in ('Walls','Doors','Windows','Finish','Equipment'):
        for ob in bpy.data.collections[cname].objects:
            if ob.type!='MESH':continue
            coords=[ob.matrix_world@v.co for v in ob.data.vertices]
            if min(v.z for v in coords)>=1.2:ob.hide_render=True;continue
            ob.data=ob.data.copy();inv=ob.matrix_world.inverted()
            for v in ob.data.vertices:
                q=ob.matrix_world@v.co;q.z=min(q.z,1.2);v.co=inv@q
    cal=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
    sx,sy=cal['mm_per_png_pixel_x']/1000,cal['mm_per_png_pixel_y']/1000
    camera=bpy.data.objects['05-top'];camera.location=(510*sx,-606*sy,26);camera.rotation_euler=(0,0,0)
    width=1040*sx;height=1220*sy;camera.data.ortho_scale=width;camera.data.sensor_fit='HORIZONTAL'
    scene.render.resolution_y=1440 if draft else 2560;scene.render.resolution_x=round(scene.render.resolution_y*width/height)
    scene.camera=camera
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.65
    d=bpy.data.lights.new('Temporary overview light','AREA');d.energy=2200;d.shape='DISK';d.size=18
    o=bpy.data.objects.new('Temporary overview light',d);scene.collection.objects.link(o);o.location=(5,-7,13)
    scene.render.filepath=str(out/'05-top.png');bpy.ops.render.render(write_still=True)
if not draft:
    blend_sha=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
    style_sha=hashlib.sha256((HERE/'style.json').read_bytes()).hexdigest()
    old=json.loads((HERE/'render-manifest.json').read_text()) if (HERE/'render-manifest.json').exists() else {}
    # Partial renders may retain only images proven to belong to this exact scene.
    images=dict(old.get('images',{})) if old.get('blend_sha256')==blend_sha and old.get('style_sha256')==style_sha else {}
    for name in selected:
        path=out/(name+'.png');images[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={'device':device,'blend_sha256':blend_sha,'style_sha256':style_sha,'images':images}
    (HERE/'render-manifest.json').write_text(json.dumps(manifest,indent=2))
print('RENDER_COMPLETE',selected)
