"""Normalize native render defaults; retain exact rendered source and record metadata-only change."""
import bpy,json,hashlib,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OUT=ROOT/'models/section-1/section-1-revised.blend'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((HERE/'render-manifest.json').read_text())
assert h(OUT)==manifest['blend_sha256']
shutil.copy2(OUT,HERE/'render-source.blend')
source_hash=h(OUT)
bpy.ops.wm.open_mainfile(filepath=str(OUT));scene=bpy.context.scene
# No visual datablocks are edited. Compare actual scene objects before and after save/reopen.
def visual_state():
    out=[]
    for ob in sorted(bpy.data.objects,key=lambda o:o.name):
        row=[ob.name,ob.type,[[round(v,6) for v in a] for a in ob.matrix_world],ob.hide_render]
        if ob.type=='MESH':row += [[[round(x,6) for x in v.co] for v in ob.data.vertices],[list(p.vertices) for p in ob.data.polygons],[m.name if m else None for m in ob.data.materials]]
        elif ob.type=='FONT':row += [ob.data.body,ob.data.size]
        elif ob.type=='LIGHT':row += [ob.data.type,ob.data.energy,list(ob.data.color)]
        elif ob.type=='CAMERA':row += [ob.data.type,ob.data.lens,ob.data.ortho_scale]
        out.append(row)
    return hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest()
before=visual_state()
scene.render.resolution_x=2560;scene.render.resolution_y=1707;scene.render.resolution_percentage=100
scene.cycles.samples=128;scene.render.filepath='//section-1-render.png'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
bpy.ops.wm.open_mainfile(filepath=str(OUT))
assert visual_state()==before
manifest['render_source_blend_sha256']=source_hash
manifest['render_source_snapshot']='render-source.blend'
manifest['blend_sha256']=h(OUT)
manifest['post_render_metadata_update']={'native_resolution':[2560,1707],'native_samples':128,'native_output':'//section-1-render.png','visual_object_fingerprint_unchanged':before,'reason':'Native defaults now match the render script and use a portable output location; visual datablocks unchanged.'}
(HERE/'render-manifest.json').write_text(json.dumps(manifest,indent=2))
print('DELIVERY_DEFAULTS_NORMALIZED',manifest['blend_sha256'])
