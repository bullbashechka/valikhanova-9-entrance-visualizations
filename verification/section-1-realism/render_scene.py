"""Render a named pilot output with reproducible camera and lighting settings."""
import argparse
import bpy
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--shot', choices=['01-overview-day', '02-overview-evening', '03-door-detail'], required=True)
parser.add_argument('--draft', action='store_true')
parser.add_argument('--samples', type=int)
parser.add_argument('--cpu', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
settings_path = HERE/'settings.json'
cfg = json.loads(settings_path.read_text(encoding='utf-8'))
scene = bpy.context.scene
source_path = Path(bpy.data.filepath)
source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
assert json.loads(scene['realism_settings_json']) == cfg, 'Rebuild after changing settings'
shot = next(x for x in cfg['pilot_outputs'] if x['name'] == args.shot)
mode = cfg['modes'][shot['mode']]
scene.camera = bpy.data.objects[shot['camera']]
scene.world.node_tree.nodes['Background'].inputs[1].default_value = mode['world_strength']
bpy.data.objects['R / entrance daylight'].data.energy = mode['entrance_watts']
for o in scene.objects:
    if o.type == 'LIGHT' and 'pilot_base_energy' in o:
        o.data.energy = o['pilot_base_energy']*mode['fixture_multiplier']
scene.view_settings.exposure = mode['exposure']
device = 'CPU'
scene.cycles.device = 'CPU'
if not args.cpu:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            devices = [d for d in prefs.devices if d.type == backend]
            if devices:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = 'GPU'
                device = backend
                break
        except (TypeError, RuntimeError):
            continue
if args.draft:
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 800
    scene.cycles.samples = args.samples or 32
    scene.cycles.adaptive_threshold = .035
    scene.cycles.adaptive_min_samples = 8
else:
    scene.render.resolution_x = cfg['render']['width']
    scene.render.resolution_y = cfg['render']['height']
    scene.cycles.samples = args.samples or cfg['render']['samples']
assert 1 <= scene.cycles.samples <= 4096
output = HERE/('drafts' if args.draft else 'previews')
output.mkdir(exist_ok=True)
path = output/(args.shot+'.png')
scene.render.filepath = str(path)
start = time.time()
print('REALISM_RENDER_START', args.shot, device, scene.cycles.samples, flush=True)
def log_render_stats(*values):
    print('REALISM_RENDER_STATS', *[str(value) for value in values], flush=True)
bpy.app.handlers.render_stats.append(log_render_stats)
bpy.ops.render.render(write_still=True)
duration = time.time()-start
assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source_hash, 'Source scene changed during render'
result = dict(shot=shot, file=path.name, width=scene.render.resolution_x,
              height=scene.render.resolution_y, samples=scene.cycles.samples,
              noise_threshold=scene.cycles.adaptive_threshold,
              device=device, seconds=round(duration, 2),
              sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
              blend_sha256=source_hash,
              settings_sha256=hashlib.sha256(settings_path.read_bytes()).hexdigest(),
              camera_matrix=[list(row) for row in scene.camera.matrix_world],
              lens=scene.camera.data.lens, lighting=mode,
              source='Native Blender Cycles render; no generated-image replacement')
(output/(args.shot+'.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
print('REALISM_RENDER_COMPLETE', args.shot, round(duration, 2), flush=True)
