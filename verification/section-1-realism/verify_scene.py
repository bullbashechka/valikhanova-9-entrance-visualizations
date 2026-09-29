"""Reopen the pilot, protect approved geometry, test new physical details."""
import bpy
import hashlib
import json
import sys
from pathlib import Path
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CFG = json.loads((HERE/'settings.json').read_text(encoding='utf-8'))
BASE = ROOT/'models/section-1/section-1-revised.blend'
OUT = ROOT/'models/section-1/section-1-realism.blend'
checks = []


def check(name, passed, **extra):
    checks.append(dict(name=name, passed=bool(passed), **extra))
    print('CHECK', name, bool(passed), flush=True)


def fingerprint(o):
    return dict(vertices=[[round(x, 6) for x in o.matrix_world@v.co] for v in o.data.vertices],
                faces=[list(p.vertices) for p in o.data.polygons],
                opening_id=o.get('opening_id'), leaf_index=o.get('leaf_index'),
                hinge=list(o['hinge_world']) if 'hinge_world' in o else None,
                open_angle=o.get('open_angle'))


bpy.ops.wm.open_mainfile(filepath=str(BASE))
bpy.context.view_layer.update()
source = {o.name: fingerprint(o) for o in bpy.data.objects if o.type == 'MESH'}
geometry = bpy.context.scene['geometry_data_json']
base_routes = json.loads(geometry)
bpy.ops.wm.open_mainfile(filepath=str(OUT))
bpy.context.view_layer.update()
scene = bpy.context.scene
check('approved input unchanged', hashlib.sha256(BASE.read_bytes()).hexdigest() == CFG['source_sha256'])
check('all approved walls openings and heights retained', scene['geometry_data_json'] == geometry)
changed = []
for name, before in source.items():
    o = bpy.data.objects.get(name)
    if o is None or fingerprint(o) != before:
        changed.append(name)
allowed = {oid+'/handle' for oid in CFG['wood_doors']}
allowed |= {f'{oid}/leaf-{idx}-{part}' for oid in CFG['glass_doors'] for idx in (0, 1) for part in ('handle', 'glass')}
check('geometry changes confined to handles and glazing thickness', set(changed) <= allowed, changed=changed)
check('settings embedded in scene match file', json.loads(scene['realism_settings_json']) == CFG)

for oid in CFG['wood_doors']:
    leaf = bpy.data.objects[oid+'/closed-leaf']
    check('leaf envelope and hinge unchanged / '+oid, fingerprint(leaf) == source[leaf.name])
    panel = bpy.data.objects[oid+'/R-overpanel']
    check('fixed upper panel / '+oid, 'leaf_index' not in panel and panel.get('fixed_part') and panel.location.z+panel.dimensions.z/2 <= 3)
    check('wood texture and physical UV / '+oid, leaf.active_material.name == 'R / scanned brown veneer' and 'Veneer metres' in leaf.data.uv_layers and leaf.data.uv_layers['Veneer metres'].active_render)
    check('upper panel UV matches leaf orientation / '+oid, panel.data.uv_layers['Veneer metres'].active_render and panel.get('veneer_group') == leaf.get('veneer_group'))

for oid in CFG['glass_doors']:
    for idx in (0, 1):
        pane = bpy.data.objects[f'{oid}/leaf-{idx}-glass']
        dims = sorted(pane.dimensions)
        bs = pane.active_material.node_tree.nodes.get('Principled BSDF')
        check(f'clear solid glazing / {oid}-{idx}', abs(dims[0]-.008) < .00001 and bs.inputs['Transmission Weight'].default_value == 1 and bs.inputs['Roughness'].default_value < .03)

for o in bpy.data.collections['Realism / Door details'].objects:
    check_ok = all(k in o for k in ('opening_id', 'hinge_world', 'leaf_index', 'open_angle'))
    if not check_ok:
        check('moving detail metadata / '+o.name, False)
check('all moving details have opening metadata', all(all(k in o for k in ('opening_id','hinge_world','leaf_index','open_angle')) for o in bpy.data.collections['Realism / Door details'].objects))
check('all fixed panels have no moving leaf metadata', all('leaf_index' not in o for o in bpy.data.collections['Realism / Fixed panels'].objects))
for name, c in CFG['cameras'].items():
    o = bpy.data.objects[name]
    check('camera settings / '+name, (o.location-Vector(c['position'])).length < .00001 and o.data.lens == c['lens'])
    enclosing = []
    for wall in bpy.data.collections['Walls'].objects:
        if wall.type != 'MESH':
            continue
        vertices = [wall.matrix_world@v.co for v in wall.data.vertices]
        if all(min(v[i] for v in vertices)+.001 < o.location[i] < max(v[i] for v in vertices)-.001 for i in range(3)):
            enclosing.append(wall.name)
    check('camera outside wall solids / '+name, not enclosing, walls=enclosing)
check('overview camera horizontal', abs((scene.objects['pilot-overview'].matrix_world.to_quaternion()@Vector((0,0,-1))).z) < .0001)
check('textures packed', all(i.packed_file or i.source in ('GENERATED', 'VIEWER') for i in bpy.data.images))
check('fonts packed', all(f.packed_file or f.filepath == '<builtin>' for f in bpy.data.fonts))
check('native render dimensions', scene.render.resolution_x == 3200 and scene.render.resolution_y == 2133)
check('no ceiling cut saved', all(not o.hide_render for o in bpy.data.collections['Ceilings'].objects))

# The original route checker includes all physical meshes. Its sweep checker
# filters collections, so add new fixed and moving pieces to Proxies temporarily.
sys.path.insert(0, str(ROOT/'verification/stage-2'))
from audit_routes import audit_routes, audit_door_sweeps, tree
cal = json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
sx, sy = cal['mm_per_png_pixel_x']/1000, cal['mm_per_png_pixel_y']/1000
linked = []
for cname in ('Finish', 'Fixtures', 'Stroller', 'Equipment', 'Realism / Door details', 'Realism / Fixed panels'):
    for o in bpy.data.collections[cname].objects:
        if o.type == 'MESH' and o.name not in bpy.data.collections['Proxies'].objects:
            bpy.data.collections['Proxies'].objects.link(o)
            linked.append(o)
checks.extend(audit_routes(bpy, base_routes, sx, sy))
checks.extend(audit_door_sweeps(bpy))
for o in linked:
    bpy.data.collections['Proxies'].objects.unlink(o)

# The historical sweep test skips a door's own frame. Check its newly added
# stationary returns separately, so that skip cannot hide a new collision.
for oid in CFG['wood_doors']:
    fixed = [(o.name, tree(o)) for o in bpy.data.collections['Realism / Fixed panels'].objects if o.get('opening_id') == oid]
    moving = [o for o in bpy.data.objects if o.get('opening_id') == oid and 'leaf_index' in o]
    saved = {o.name: o.matrix_world.copy() for o in moving}
    contacts = set()
    for fraction in (0, .25, .5, .75, 1):
        for o in moving:
            pivot = Vector(o['hinge_world'])
            o.matrix_world = Matrix.Translation(pivot)@Matrix.Rotation(o['open_angle']*fraction, 4, 'Z')@Matrix.Translation(-pivot)@saved[o.name]
        bpy.context.view_layer.update()
        for o in moving:
            t = tree(o)
            for fixed_name, fixed_tree in fixed:
                if t.overlap(fixed_tree):
                    contacts.add((fraction, o.name, fixed_name))
    for o in moving:
        o.matrix_world = saved[o.name]
    bpy.context.view_layer.update()
    check('new panels clear own door motion / '+oid, not contacts, contacts=sorted(contacts))

# Reuse the existing geometric lift travel and approach tests, excluding old
# style-specific assertions. The source code hash makes this dependency explicit.
lift_source = ROOT/'verification/section-1-revision/verify_revision.py'
code = lift_source.read_text(encoding='utf-8')
lift_checks = code[code.index('# Evaluate actual solid meshes'):code.index("check('native render defaults")]
exec(compile(lift_checks, str(lift_source), 'exec'))

report = dict(all_pass=all(c['passed'] for c in checks), checks=checks,
              blend_sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),
              source_sha256=CFG['source_sha256'],
              lift_check_source_sha256=hashlib.sha256(lift_source.read_bytes()).hexdigest(),
              limitation='Route and lift envelopes are conceptual checks, not site measurements or regulatory certification.')
(HERE/'validation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print('REALISM_VALIDATION', report['all_pass'], len(checks), flush=True)
for c in checks:
    if not c['passed']:
        print('FAILED', json.dumps(c, ensure_ascii=True), flush=True)
assert report['all_pass'], 'See validation.json'
