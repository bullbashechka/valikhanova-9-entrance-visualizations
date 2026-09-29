"""Build the realism pilot from the last delivered scene, never from old geometry.

Run in a fresh Blender process. Every new physical door part keeps its opening,
hinge and leaf metadata so it participates in the existing collision audits.
"""
from pathlib import Path
import bpy
import hashlib
import json
import math
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = ROOT / 'models/section-1/section-1-revised.blend'
OUT = ROOT / 'models/section-1/section-1-realism.blend'
CFG = json.loads((HERE / 'settings.json').read_text(encoding='utf-8'))
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == CFG['source_sha256']
bpy.ops.wm.open_mainfile(filepath=str(BASE))
scene = bpy.context.scene
PORTALS = json.loads((ROOT / 'verification/stage-2/scene-section.json').read_text())['portals']
CAL = json.loads((ROOT / 'verification/stage-1/calibration.json').read_text())['1']
SX, SY = CAL['mm_per_png_pixel_x']/1000, CAL['mm_per_png_pixel_y']/1000


def col(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


DETAIL = col('Realism / Door details')
PANELS = col('Realism / Fixed panels')
LIGHT = col('Realism / Daylight')


def rgb(code):
    s = [int(code[i:i+2], 16)/255 for i in (1, 3, 5)]
    return tuple(x/12.92 if x <= .04045 else ((x+.055)/1.055)**2.4 for x in s)


def material(name, color, rough=.5, metal=0):
    m = bpy.data.materials.new(name)
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*rgb(color), 1)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    return m


def assign(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)


def bounds(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    return [(min(v[i] for v in pts), max(v[i] for v in pts)) for i in range(3)]


def props(o, source=None, oid=None, fixed=False):
    if source:
        for k in ('opening_id', 'leaf_index', 'hinge_world', 'open_angle'):
            if k in source:
                v = source[k]
                o[k] = list(v) if k == 'hinge_world' else v
    if oid:
        o['opening_id'] = oid
    o['realism_part'] = True
    o['fixed_part'] = fixed


def finish_object(o, name, m, collection):
    o.name = name
    for c in list(o.users_collection):
        c.objects.unlink(o)
    collection.objects.link(o)
    assign(o, m)
    return o


def box(name, location, dimensions, m, collection=DETAIL, radius=.001):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    o = bpy.context.object
    o.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    finish_object(o, name, m, collection)
    if radius:
        b = o.modifiers.new('Manufactured edge', 'BEVEL')
        b.width = radius
        b.segments = 3
        o.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    return o


def cylinder(name, a, b, radius, m, collection=DETAIL):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=(b-a).length, location=(a+b)/2)
    o = bpy.context.object
    o.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
    finish_object(o, name, m, collection)
    bevel = o.modifiers.new('Soft edge', 'BEVEL')
    bevel.width = .0008
    bevel.segments = 2
    for poly in o.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    o.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    return o


def micro_finish(m, scale, strength, distance, rough_low, rough_high):
    n, link = m.node_tree.nodes, m.node_tree.links.new
    bs = n.get('Principled BSDF')
    tex = n.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = scale
    tex.inputs['Detail'].default_value = 2
    geo = n.new('ShaderNodeNewGeometry')
    link(geo.outputs['Position'], tex.inputs['Vector'])
    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    link(tex.outputs['Fac'], bump.inputs['Height'])
    if bs.inputs['Normal'].is_linked:
        # Keep the tile-joint bump, applying surface grain before the joints.
        old = bs.inputs['Normal'].links[0].from_node
        link(bump.outputs['Normal'], old.inputs['Normal'])
    else:
        link(bump.outputs['Normal'], bs.inputs['Normal'])
    r = n.new('ShaderNodeMapRange')
    r.inputs['To Min'].default_value = rough_low
    r.inputs['To Max'].default_value = rough_high
    link(tex.outputs['Fac'], r.inputs['Value'])
    link(r.outputs['Result'], bs.inputs['Roughness'])


# Keep the original floor masks and source geometry; enrich the surface response.
for m in list(bpy.data.materials):
    if not m.node_tree:
        continue
    bs = m.node_tree.nodes.get('Principled BSDF')
    if not bs:
        continue
    if m.name.startswith('M01 /'):
        # Original base colour carries the dark skirting mask.
        for node in m.node_tree.nodes:
            if node.bl_idname == 'ShaderNodeMixRGB':
                node.inputs[1].default_value = (*rgb('#E8E6E0'), 1)
                node.inputs[2].default_value = (*rgb('#373833'), 1)
        micro_finish(m, 380, .18, .00018, .77, .86)
    elif m.name.startswith('M02 /'):
        bs.inputs['Base Color'].default_value = (*rgb('#ECEAE4'), 1)
        micro_finish(m, 420, .10, .00012, .78, .87)
    elif m.name.startswith(('M03', 'M04', 'M05', 'M07')):
        micro_finish(m, 190, .20, .0003, .39, .59)
        # Additional low-contrast mineral variation, independent of grout masks.
        n, link = m.node_tree.nodes, m.node_tree.links.new
        old = bs.inputs['Base Color'].links[0].from_socket if bs.inputs['Base Color'].is_linked else None
        if old:
            noise = n.new('ShaderNodeTexNoise')
            noise.inputs['Scale'].default_value = 32
            noise.inputs['Detail'].default_value = 4
            geo = n.new('ShaderNodeNewGeometry')
            link(geo.outputs['Position'], noise.inputs['Vector'])
            ramp = n.new('ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].color = (.65, .65, .65, 1)
            ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
            link(noise.outputs['Fac'], ramp.inputs[0])
            mix = n.new('ShaderNodeMixRGB')
            mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = .33
            link(old, mix.inputs[1])
            link(ramp.outputs[0], mix.inputs[2])
            link(mix.outputs[0], bs.inputs['Base Color'])
    elif m.name.startswith('M06 /'):
        bs.inputs['Base Color'].default_value = (*rgb('#202321'), 1)
        bs.inputs['Metallic'].default_value = .05
        bs.inputs['Specular IOR Level'].default_value = .35
        micro_finish(m, 600, .10, .00006, .30, .41)
    elif m.name.startswith('M09 /'):
        bs.inputs['Base Color'].default_value = (*rgb('#666764'), 1)
        bs.inputs['Metallic'].default_value = .85
        micro_finish(m, 550, .12, .00007, .26, .37)
    elif m.name.startswith('M10 /'):
        bs.inputs['Base Color'].default_value = (.985, .993, 1, 1)
        bs.inputs['Roughness'].default_value = .018
        bs.inputs['IOR'].default_value = 1.5
        bs.inputs['Transmission Weight'].default_value = 1
        # Architectural clear glass: preserve camera/reflection refraction, but
        # transmit direct-light shadow rays through consecutive glazed doors.
        # This deliberately omits refractive shadow caustics, documented in README.
        n, link = m.node_tree.nodes, m.node_tree.links.new
        path = n.new('ShaderNodeLightPath')
        transparent = n.new('ShaderNodeBsdfTransparent')
        transparent.inputs['Color'].default_value = (.96, .97, .98, 1)
        shadow_mix = n.new('ShaderNodeMixShader')
        link(path.outputs['Is Shadow Ray'], shadow_mix.inputs[0])
        link(bs.outputs[0], shadow_mix.inputs[1])
        link(transparent.outputs[0], shadow_mix.inputs[2])
        link(shadow_mix.outputs[0], n.get('Material Output').inputs['Surface'])

wood = material('R / scanned brown veneer', '#604A35', .47)
n, link = wood.node_tree.nodes, wood.node_tree.links.new
bs = n.get('Principled BSDF')
uv = n.new('ShaderNodeUVMap')
uv.uv_map = 'Veneer metres'
texs = {}
for suffix, color_space in [('diff', 'sRGB'), ('rough', 'Non-Color'), ('nor_gl', 'Non-Color')]:
    t = n.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(str(HERE / 'textures' / f'oak_veneer_01_{suffix}_4k.jpg'), check_existing=True)
    t.image.colorspace_settings.name = color_space
    t.extension = 'REPEAT'
    link(uv.outputs['UV'], t.inputs['Vector'])
    texs[suffix] = t
hue = n.new('ShaderNodeHueSaturation')
hue.inputs['Saturation'].default_value = .85
link(texs['diff'].outputs['Color'], hue.inputs['Color'])
tint = n.new('ShaderNodeMixRGB')
tint.blend_type = 'MULTIPLY'
tint.inputs[0].default_value = 1
tint.inputs[2].default_value = (.25, .24, .23, 1)
link(hue.outputs[0], tint.inputs[1])
link(tint.outputs[0], bs.inputs['Base Color'])
r = n.new('ShaderNodeMapRange')
r.inputs['To Min'].default_value = .40
r.inputs['To Max'].default_value = .60
bs.inputs['Specular IOR Level'].default_value = .30
link(texs['rough'].outputs[0], r.inputs['Value'])
link(r.outputs[0], bs.inputs['Roughness'])
normal = n.new('ShaderNodeNormalMap')
normal.inputs['Strength'].default_value = .16
link(texs['nor_gl'].outputs[0], normal.inputs['Color'])
link(normal.outputs[0], bs.inputs['Normal'])


def wood_uv(o, group, across_axis=None):
    b = bounds(o)
    if across_axis is None:
        across_axis = 0 if b[0][1]-b[0][0] >= b[1][1]-b[1][0] else 1
    offset = int(hashlib.sha256(group.encode()).hexdigest()[:6], 16)/0xffffff
    uv_layer = o.data.uv_layers.get('Veneer metres') or o.data.uv_layers.new(name='Veneer metres')
    o.data.uv_layers.active = uv_layer
    uv_layer.active_render = True
    for face in o.data.polygons:
        for li in face.loop_indices:
            v = o.matrix_world @ o.data.vertices[o.data.loops[li].vertex_index].co
            # This veneer scan is vertically grained, with a documented 1.8 m width.
            uv_layer.data[li].uv = (v[across_axis]/1.8 + offset, v.z/1.8 + offset*.67)
    o['veneer_group'] = group


for o in bpy.data.objects:
    if o.type == 'MESH' and any(m and m.name.startswith('M08 /') for m in o.data.materials):
        assign(o, wood)
        wood_uv(o, o.get('opening_id') or 'accent-' + o.name)

dark = bpy.data.materials['M06 / graphite powder coat']
glass = bpy.data.materials['M10 / clear glazing']
rubber = material('R / glazing gasket', '#171918', .78)
ribmat = material('R / dark fluted door insert', '#302C25', .43)
lock = material('R / lock satin steel', '#646965', .29, .82)


def coordinate(across_axis, across, depth, z):
    return (across, depth, z) if across_axis == 0 else (depth, across, z)


def doorbox(name, ax, a, d, z, width, thickness, height, mat, source=None, oid=None, fixed=False):
    dims = (width, thickness, height) if ax == 0 else (thickness, width, height)
    o = box(name, coordinate(ax, a, d, z), dims, mat, PANELS if fixed else DETAIL)
    props(o, source, oid, fixed)
    return o


def doorcyl(name, ax, a1, d1, z1, a2, d2, z2, radius, mat, source=None):
    o = cylinder(name, coordinate(ax, a1, d1, z1), coordinate(ax, a2, d2, z2), radius, mat)
    props(o, source)
    return o


for oid in CFG['wood_doors']:
    leaf = bpy.data.objects[oid + '/closed-leaf']
    b = bounds(leaf)
    ax = 0 if b[0][1]-b[0][0] > b[1][1]-b[1][0] else 1
    dep = 1-ax
    alo, ahi = b[ax]
    dlo, dhi = b[dep]
    zlo, zhi = b[2]
    centre = (alo+ahi)/2
    sign = 1 if oid in ('S1-18', 'S1-21', 'S1-22') else -1
    face = dhi if sign > 0 else dlo
    assign(leaf, wood)
    wood_uv(leaf, oid, ax)
    # Preserve its base mesh, hinge and envelope; bevel is evaluated on render only.
    for mod in leaf.modifiers:
        if mod.type == 'BEVEL':
            mod.width = .0015
            mod.segments = 4
    handle = bpy.data.objects[oid+'/handle']
    hb = bounds(handle)
    h_a = sum(hb[ax])/2
    h_z = sum(hb[2])/2
    hinge_a = list(leaf['hinge_world'])[ax]
    direction = 1 if hinge_a > centre else -1
    bpy.data.objects.remove(handle, do_unlink=True)
    for side in (-1, 1):
        f = dhi if side > 0 else dlo
        rose_a = h_a - direction*.043
        doorbox(f'{oid}/R-rose-{side}', ax, rose_a, f+side*.004, h_z,
                .045, .008, .045, dark, leaf)
        doorcyl(f'{oid}/R-spindle-{side}', ax, rose_a, f, h_z,
                rose_a, f+side*.033, h_z, .010, dark, leaf)
        doorcyl(f'{oid}/R-lever-{side}', ax, rose_a, f+side*.033, h_z,
                rose_a+direction*.112, f+side*.033, h_z, .0075, dark, leaf)
        doorbox(f'{oid}/R-lock-plate-{side}', ax, rose_a, f+side*.004, h_z-.14,
                .030, .007, .042, dark, leaf)
        doorbox(f'{oid}/R-lock-slot-{side}', ax, rose_a, f+side*.008, h_z-.14,
                .002, .001, .015, lock, leaf)
    # Reference-inspired dark vertical fluting, restrained to the centre of the leaf.
    strip_w = min(.30, (ahi-alo)*.28)
    count = max(1, round(strip_w/.008))
    step = strip_w/count
    for i in range(count):
        a = centre-strip_w/2+(i+.5)*step
        o = doorbox(f'{oid}/R-flute-{i:02d}', ax, a, face+sign*.0008, (zlo+zhi)/2,
                    step-.0015, .0016, zhi-zlo-.018, ribmat, leaf)
    # A fixed upper wood panel sits on the existing room-side wall face.
    portal = PORTALS[oid]
    rct = portal['rect']
    if ax == 0:
        wall_face = -rct[1 if sign > 0 else 3]*SY
    else:
        wall_face = rct[2 if sign > 0 else 0]*SX
    panel_depth = wall_face+sign*.010
    panel = doorbox(f'{oid}/R-overpanel', ax, centre, panel_depth, 2.551,
                    ahi-alo+.09, .018, .882, wood, oid=oid, fixed=True)
    wood_uv(panel, oid, ax)
    # Continuous slim framing visually joins the door and its fixed upper panel.
    for a in (alo-.057, ahi+.057):
        doorbox(f'{oid}/R-portal-upright-{a:.3f}', ax, a, panel_depth, 1.5,
                .018, .022, 2.99, dark, oid=oid, fixed=True)
    doorbox(f'{oid}/R-portal-top', ax, centre, panel_depth, 2.99,
            ahi-alo+.13, .022, .018, dark, oid=oid, fixed=True)
    # Dark returns cover the existing plaster recess without moving the leaf.
    inner_reveal_edge = face+sign*.004
    reveal_length = abs(wall_face-inner_reveal_edge)
    if reveal_length > .025:
        reveal_mid = (wall_face+inner_reveal_edge)/2
        for a in (alo-.041, ahi+.041):
            doorbox(f'{oid}/R-reveal-{a:.3f}', ax, a, reveal_mid, 1.043,
                    .010, reveal_length, 2.086, dark, oid=oid, fixed=True)
        doorbox(f'{oid}/R-reveal-head', ax, centre, reveal_mid, 2.076,
                ahi-alo+.06, reveal_length, .025, dark, oid=oid, fixed=True)
    # Hinge knuckles are part of the moving leaf, on the true hinge axis.
    hinge_d = list(leaf['hinge_world'])[dep]
    for z in (.24, 1.03, 1.81):
        doorcyl(f'{oid}/R-hinge-{z}', ax, hinge_a, hinge_d, z,
                hinge_a, hinge_d, z+.09, .010, dark, leaf)

# Place the staircase label over its new fixed panel, without covering the door.
label = bpy.data.objects['N / stair label']
label.location.y = -PORTALS['S1-18']['rect'][1]*SY+.024
label.location.z = 2.46
label.data.size = .066
assign(label, bpy.data.materials['N / ivory lettering'])

for oid in CFG['glass_doors']:
    for idx in (0, 1):
        pane = bpy.data.objects[f'{oid}/leaf-{idx}-glass']
        b = bounds(pane)
        ax = 0 if b[0][1]-b[0][0] > b[1][1]-b[1][0] else 1
        dep = 1-ax
        mid_d = sum(b[dep])/2
        # Eight-millimetre solid glazing, centred on the original pane plane.
        old_thickness = b[dep][1]-b[dep][0]
        for v in pane.data.vertices:
            p = pane.matrix_world @ v.co
            p[dep] = mid_d+(p[dep]-mid_d)*.008/old_thickness
            v.co = pane.matrix_world.inverted() @ p
        for mod in pane.modifiers:
            if mod.type == 'BEVEL':
                mod.width = .0006
        assign(pane, glass)
        alo, ahi = b[ax]
        zlo, zhi = b[2]
        for side in (-1, 1):
            d = mid_d+side*.012
            for a in (alo+.008, ahi-.008):
                doorbox(f'{oid}/R-bead-{idx}-{side}-{a:.3f}', ax, a, d, (zlo+zhi)/2,
                        .010, .006, zhi-zlo, dark, pane)
            for z in (zlo+.006, zhi-.006):
                doorbox(f'{oid}/R-bead-{idx}-{side}-{z:.3f}', ax, (alo+ahi)/2, d, z,
                        ahi-alo, .006, .010, dark, pane)
        old_handle = bpy.data.objects[f'{oid}/leaf-{idx}-handle']
        hb = bounds(old_handle)
        h_a = sum(hb[ax])/2
        bpy.data.objects.remove(old_handle, do_unlink=True)
        for side in (-1, 1):
            d = mid_d+side*.052
            doorcyl(f'{oid}/R-pull-{idx}-{side}', ax, h_a, d, .85, h_a, d, 1.19, .012, dark, pane)
            for z in (.90, 1.14):
                doorcyl(f'{oid}/R-pull-mount-{idx}-{side}-{z}', ax, h_a, mid_d+side*.028, z,
                        h_a, d, z, .009, dark, pane)
        hinge = list(pane['hinge_world'])
        for z in (.24, zhi-.25):
            doorcyl(f'{oid}/R-hinge-{idx}-{z}', ax, hinge[ax], hinge[dep], z,
                    hinge[ax], hinge[dep], z+.09, .010, dark, pane)

# The pilot contains no replacement prop model; it is explicitly an architecture sample.
bpy.data.collections['Stroller'].hide_render = True
scene['pilot_props_deferred'] = 'Detailed stroller and floor-standing bicycle follow pilot acceptance.'

# Preserve physical fixture positions, remove obsolete exterior helper lights.
for o in list(bpy.data.objects):
    if o.type == 'LIGHT' and o.name.startswith('Daylight /'):
        bpy.data.objects.remove(o, do_unlink=True)
    elif o.type == 'LIGHT':
        o['pilot_base_energy'] = o.data.energy*1.4
        o.data.energy = o['pilot_base_energy']
        o.data.color = (1.0, .87, .69)
diffuser = bpy.data.materials['L / 3000K diffuser'].node_tree.nodes.get('Principled BSDF')
diffuser.inputs['Emission Color'].default_value = (1, .87, .69, 1)
diffuser.inputs['Emission Strength'].default_value = 6
data = bpy.data.lights.new('R / entrance daylight', 'AREA')
data.shape = 'RECTANGLE'
data.size = 4.5
data.size_y = 3.8
data.energy = CFG['modes']['day']['entrance_watts']
data.color = (.89, .94, 1)
sun = bpy.data.objects.new(data.name, data)
LIGHT.objects.link(sun)
sun.location = (13.5, -.15, 4.6)
sun.rotation_euler = (Vector((8, -1.7, 1.3))-sun.location).to_track_quat('-Z', 'Y').to_euler()

for name, cfg in CFG['cameras'].items():
    camera = bpy.data.cameras.new(name)
    o = bpy.data.objects.new(name, camera)
    scene.collection.objects.link(o)
    o.location = cfg['position']
    o.rotation_euler = (Vector(cfg['target'])-o.location).to_track_quat('-Z', 'Y').to_euler()
    camera.lens = cfg['lens']
    camera.sensor_width = 36
    camera.shift_y = cfg['shift_y']
    camera.clip_start = .025
    camera.dof.use_dof = False
scene.camera = bpy.data.objects['pilot-overview']
scene.render.engine = 'CYCLES'
scene.cycles.samples = CFG['render']['samples']
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = CFG['render']['noise_threshold']
scene.cycles.adaptive_min_samples = CFG['render']['min_samples']
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 12
scene.cycles.diffuse_bounces = 6
scene.cycles.glossy_bounces = 6
scene.cycles.transmission_bounces = 12
scene.cycles.transparent_max_bounces = 16
scene.cycles.sample_clamp_indirect = 10
scene.render.resolution_x = CFG['render']['width']
scene.render.resolution_y = CFG['render']['height']
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.filepath = '//section-1-realism-preview.png'
scene['realism_settings_json'] = json.dumps(CFG, ensure_ascii=False, sort_keys=True)
scene['realism_source_sha256'] = CFG['source_sha256']
scene['realism_stage'] = 'pilot_pending_user_review'

# Bake only the default lighting state; render variants are applied from settings.
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.78, .85, 1, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = CFG['modes']['day']['world_strength']
scene.view_settings.exposure = CFG['modes']['day']['exposure']
bpy.context.view_layer.update()
bpy.ops.file.pack_all()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == CFG['source_sha256']
(HERE/'build-report.json').write_text(json.dumps({
    'source': str(BASE.relative_to(ROOT)), 'source_sha256': CFG['source_sha256'],
    'output': str(OUT.relative_to(ROOT)), 'output_sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(),
    'objects': len(scene.objects), 'new_door_parts': len(DETAIL.objects),
    'fixed_parts': len(PANELS.objects), 'blender': bpy.app.version_string,
    'settings_sha256': hashlib.sha256((HERE/'settings.json').read_bytes()).hexdigest(),
    'stage': 'pilot_pending_user_review'
}, indent=2), encoding='utf-8')
print('REALISM_SCENE_SAVED', OUT, flush=True)
