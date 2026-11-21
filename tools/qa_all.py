"""Quality check of every model of your own disc image (not in CI: needs game data).

    python tools/qa_all.py IMAGE OUTDIR [--validator NODE_SCRIPT]

For every Digimon and effect model: conversion, geometry checks (NaN, UVs outside the page, degenerate triangles,
skin joints and weights), face rectangles (sources overwritten by another part?), hidden bones, and for the exports
an independent re-read: GLB with the Khronos glTF-Validator (node script, see docs/QA.md), OBJ with trimesh
(vertex, face and UV counts and bounds against the GLB), motions JSON (frames against the metadata).
Writes OUTDIR/qa.json and prints a summary. The image is only read."""
import json
import math
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dw3viewer.server import API  # noqa: E402
from dw3viewer import export  # noqa: E402
from dw3viewer.export import _accessor  # noqa: E402
from dw3viewer.library import read_glb  # noqa: E402


def geometry(folder):
    doc, binary = read_glb(folder / 'model.glb')
    joints = len(doc['skins'][0]['joints']) if doc.get('skins') else 0
    out = Counter()
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for prim in doc['meshes'][0]['primitives']:
        pos = _accessor(doc, binary, prim['attributes']['POSITION'])
        uv = _accessor(doc, binary, prim['attributes']['TEXCOORD_0'])
        jn = _accessor(doc, binary, prim['attributes']['JOINTS_0']) if 'JOINTS_0' in prim['attributes'] else []
        wt = _accessor(doc, binary, prim['attributes']['WEIGHTS_0']) if 'WEIGHTS_0' in prim['attributes'] else []
        for p in pos:
            if not all(math.isfinite(c) for c in p):
                out['nan_positions'] += 1
            for a in range(3):
                lo[a], hi[a] = min(lo[a], p[a]), max(hi[a], p[a])
        out['uv_outside'] += sum(1 for u, v in uv if not (-1e-6 <= u <= 1 + 1e-6 and -1e-6 <= v <= 1 + 1e-6))
        out['bad_joint'] += sum(1 for j in jn if j[0] >= joints)
        out['bad_weight'] += sum(1 for w in wt if abs(sum(w) - 1) > 1e-3)
        for k in range(0, len(pos) - 2, 3):
            a, b, c = pos[k], pos[k + 1], pos[k + 2]
            ab = [b[i] - a[i] for i in range(3)]
            ac = [c[i] - a[i] for i in range(3)]
            cr = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
            if sum(x * x for x in cr) < 1e-12:
                out['degenerate_triangles'] += 1
        out['triangles'] += len(pos) // 3
        out['vertices'] += len(pos)
    return dict(out), (lo, hi)


def face_overlaps(meta):
    parts = [p for p in meta['face']['parts'] if p['targets']]
    hits = 0
    for p in parts:
        for t in p['targets']:
            x, y, w, h = t['dst']
            for q in parts:
                for s in q['targets']:
                    if s['image'] != t['image']:
                        continue
                    for u, v in s['src']:
                        if u < x + w and x < u + s['dst'][2] and v < y + h and y < v + s['dst'][3]:
                            hits += 1
    return hits


def main():
    image, out = sys.argv[1], Path(sys.argv[2])
    validator = sys.argv[sys.argv.index('--validator') + 1] if '--validator' in sys.argv else None
    out.mkdir(parents=True, exist_ok=True)
    api = API(data_dir=out / 'data')
    cat = api.open(image)['catalog']
    import trimesh
    rows, glbs = [], []
    for m in cat:
        row = {'id': m['id'], 'kind': m['kind'], 'name': m['name'], 'file': m['file']}
        rows.append(row)
        try:
            meta = api.model(m['id'])['meta']
        except ValueError as e:
            row['error'] = str(e)
            continue
        folder = api.lib.folder(m['id'])
        row['motions'] = meta['motion_count']
        row['motions_gltf'] = sum(1 for x in meta['motions'] if x['gltf'])
        row['named_motions'] = sum(1 for x in meta['motions'] if not x['name'].startswith('Motion '))
        row['face_parts'] = sum(1 for p in meta['face']['parts'] if p['targets'])
        row['face_unmapped'] = sum(1 for p in meta['face']['parts'] if not p['targets'])
        row['face_overlaps'] = face_overlaps(meta)
        row['hidden_bones'] = len({b for x in meta['motions'] for b in x['hidden']})
        row['semi_modes'] = sorted({a - 1 for b in meta['bones'] for a in b['abr']})
        geo, (lo, hi) = geometry(folder)
        row.update(geo)
        glbs.append((m['id'], folder / 'model.glb'))
        with tempfile.TemporaryDirectory() as t:
            files = export.obj(folder, Path(t), 'm')
            mesh = trimesh.load(files[0], force='mesh', process=False, maintain_order=True)
            row['obj_faces'] = int(len(mesh.faces))
            row['obj_ok'] = (len(mesh.faces) == geo['triangles']
                             and all(abs(mesh.bounds[0][i] - lo[i]) < 1e-3 and abs(mesh.bounds[1][i] - hi[i]) < 1e-3 for i in range(3)))
            mj = json.loads(export.motions(folder, meta, Path(t) / 'm.json')[0].read_text())
            row['motions_json_ok'] = [len(x['frames']) for x in mj['motions']] == [x['frames'] for x in meta['motions']]
    if validator:
        proc = subprocess.run(['node', validator], input='\n'.join(str(p) for _, p in glbs), capture_output=True, text=True)
        by_file = {json.loads(l)['file']: json.loads(l) for l in proc.stdout.splitlines() if l.startswith('{')}
        for ident, p in glbs:
            v = by_file.get(str(p), {'crash': 'no result'})
            row = rows[ident]
            row['gltf_validator'] = {k: v.get(k) for k in ('errors', 'warnings', 'animations', 'crash', 'sample')}
    (out / 'qa.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = [r for r in rows if 'error' not in r]
    s = {
        'models': len(rows), 'digimon': sum(1 for r in rows if r['kind'] == 'digimon'), 'effects': sum(1 for r in rows if r['kind'] == 'effect'),
        'converted': len(ok), 'not_supported': [(r['file'], r['error'][:80]) for r in rows if 'error' in r],
        'nan_positions': sum(r.get('nan_positions', 0) for r in ok), 'uv_outside': sum(r.get('uv_outside', 0) for r in ok),
        'bad_joint': sum(r.get('bad_joint', 0) for r in ok), 'bad_weight': sum(r.get('bad_weight', 0) for r in ok),
        'degenerate_triangles': sum(r.get('degenerate_triangles', 0) for r in ok),
        'models_with_degenerate': sum(1 for r in ok if r.get('degenerate_triangles')),
        'obj_ok': sum(1 for r in ok if r.get('obj_ok')), 'motions_json_ok': sum(1 for r in ok if r.get('motions_json_ok')),
        'motions': sum(r['motions'] for r in ok), 'motions_playable': sum(r['motions_gltf'] for r in ok),
        'digimon_motions_named': sum(r['named_motions'] for r in ok if r['kind'] == 'digimon'),
        'digimon_motions': sum(r['motions'] for r in ok if r['kind'] == 'digimon'),
        'face_parts': sum(r['face_parts'] for r in ok), 'face_unmapped': sum(r['face_unmapped'] for r in ok),
        'face_overlaps': sum(r['face_overlaps'] for r in ok), 'models_with_hidden_bones': sum(1 for r in ok if r['hidden_bones']),
        'semi_modes': dict(Counter(m for r in ok for m in r['semi_modes'])),
    }
    if validator:
        s['gltf_validator_errors'] = sum((r.get('gltf_validator') or {}).get('errors') or 0 for r in ok)
        s['gltf_validator_warnings'] = sum((r.get('gltf_validator') or {}).get('warnings') or 0 for r in ok)
        s['gltf_validator_clean'] = sum(1 for r in ok if (r.get('gltf_validator') or {}).get('errors') == 0)
        s['gltf_validator_crash'] = [r['file'] for r in ok if (r.get('gltf_validator') or {}).get('crash')]
    (out / 'qa_summary.json').write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
