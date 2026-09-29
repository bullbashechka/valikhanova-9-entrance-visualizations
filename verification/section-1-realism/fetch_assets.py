"""Download the CC0 wood scan and verify the publisher's checksums."""
from pathlib import Path
import hashlib
import json
import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / 'textures'
OUT.mkdir(exist_ok=True)
session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 Section1ArchitecturalReview/1.0'
response = session.get('https://api.polyhaven.com/files/oak_veneer_01', timeout=40)
response.raise_for_status()
catalog = response.json()
records = []
for channel in ('Diffuse', 'Rough', 'nor_gl'):
    item = catalog[channel]['4k']['jpg']
    path = OUT / item['url'].rsplit('/', 1)[-1]
    if not path.exists() or hashlib.md5(path.read_bytes()).hexdigest() != item['md5']:
        result = session.get(item['url'], timeout=120)
        result.raise_for_status()
        assert hashlib.md5(result.content).hexdigest() == item['md5'], channel
        path.write_bytes(result.content)
    records.append(dict(channel=channel, file=str(path.relative_to(HERE)),
                        url=item['url'], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        bytes=path.stat().st_size))
    print('ASSET_VERIFIED', path.name, path.stat().st_size, flush=True)
(HERE / 'asset-register.json').write_text(json.dumps({
    'asset': 'Oak Veneer 01', 'source': 'https://polyhaven.com/a/oak_veneer_01',
    'license': 'CC0', 'license_url': 'https://polyhaven.com/license',
    'authors': ['Jenelle van Heerden'],
    'physical_width_m': 1.8, 'files': records,
    'adaptation': 'Shader colour treatment; original downloaded maps preserved.'
}, indent=2), encoding='utf-8')
