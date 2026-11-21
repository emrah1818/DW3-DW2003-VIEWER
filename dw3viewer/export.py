"""Exports of a converted model: GLB (with skeleton and every motion), OBJ + MTL + PNG (rest pose),
texture PNGs, motion samples and technical metadata as JSON. The game image is never touched."""
import json
import shutil
import struct
from pathlib import Path

from .library import read_glb

COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
FORMATS = {5126: ('f', 4), 5125: ('I', 4), 5123: ('H', 2), 5121: ('B', 1)}


def _accessor(doc, binary, index):
    acc = doc['accessors'][index]
    view = doc['bufferViews'][acc['bufferView']]
    fmt, size = FORMATS[acc['componentType']]
    n = COMPONENTS[acc['type']]
    stride = view.get('byteStride', size * n)
    base = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    return [struct.unpack_from(f'<{n}{fmt}', binary, base + i * stride) for i in range(acc['count'])]


def obj(folder, dest, name):
    """MODEL.obj + .mtl + the texture PNGs into DEST, in the bind (rest) pose of the skeleton.
    Returns the written paths."""
    folder, dest = Path(folder), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    doc, binary = read_glb(folder / 'model.glb')
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in name) or 'model'
    lines = [f'# {name}: exported by DW3/DW2003 Viewer from the game data (rest pose)', f'mtllib {safe}.mtl']
    mtl = []
    written = []
    images = doc.get('images', [])
    textures = doc.get('textures', [])
    base_v = base_t = 1
    for mi, mesh in enumerate(doc.get('meshes', [])):
        for pi, prim in enumerate(mesh['primitives']):
            pos = _accessor(doc, binary, prim['attributes']['POSITION'])
            uv = _accessor(doc, binary, prim['attributes']['TEXCOORD_0']) if 'TEXCOORD_0' in prim['attributes'] else []
            idx = [i[0] for i in _accessor(doc, binary, prim['indices'])] if 'indices' in prim else list(range(len(pos)))
            mat = doc['materials'][prim['material']] if 'material' in prim else {}
            mname = mat.get('name', f'mat{mi}_{pi}')
            lines.append(f'o part_{mi}_{pi}')
            lines.append(f'usemtl {mname}')
            lines += [f'v {x:.6f} {y:.6f} {z:.6f}' for x, y, z in pos]
            lines += [f'vt {u:.6f} {1 - v:.6f}' for u, v in uv]
            for k in range(0, len(idx) - 2, 3):
                a, b, c = (base_v + idx[k], base_v + idx[k + 1], base_v + idx[k + 2])
                if uv:
                    ta, tb, tc = (base_t + idx[k], base_t + idx[k + 1], base_t + idx[k + 2])
                    lines.append(f'f {a}/{ta} {b}/{tb} {c}/{tc}')
                else:
                    lines.append(f'f {a} {b} {c}')
            base_v += len(pos)
            base_t += len(uv)
            tex = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('index')
            mtl += [f'newmtl {mname}', 'Ka 1 1 1', 'Kd 1 1 1', 'Ks 0 0 0', 'illum 1']
            if mat.get('alphaMode') == 'BLEND':
                mtl.append('d 0.5')
            if tex is not None and tex < len(textures):
                img = images[textures[tex]['source']].get('uri') or f"tex{textures[tex]['source']}.png"
                mtl.append(f'map_Kd {img}')
            mtl.append('')
    for p in sorted(folder.glob('tex*.png')):
        shutil.copy2(p, dest / p.name)
        written.append(dest / p.name)
    (dest / f'{safe}.obj').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (dest / f'{safe}.mtl').write_text('\n'.join(mtl), encoding='utf-8')
    return [dest / f'{safe}.obj', dest / f'{safe}.mtl'] + written


def glb(folder, dest_file):
    dest_file = Path(dest_file)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(folder) / 'model.glb', dest_file)
    return [dest_file]


def textures(folder, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(Path(folder).glob('tex*.png')):
        shutil.copy2(p, dest / p.name)
        out.append(dest / p.name)
    return out


def metadata(meta, dest_file):
    dest_file = Path(dest_file)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    return [dest_file]


def motions(folder, meta, dest_file):
    """Every motion as 30-per-second bone matrices (the game's own keyframes and blends, sampled),
    with its name and how it ends: a format any tool can read without the game."""
    src = json.loads((Path(folder) / 'native_source.json').read_text(encoding='utf-8'))
    names = {m['id']: m for m in meta['motions']}
    out = {'format': 'dw3viewer-motions-1', 'fps': src['fps'], 'model': meta['file'],
           'bones': [{'index': i, 'parent': b['parent']} for i, b in enumerate(src['bones'])],
           'matrix_layout': '4x4 per bone and frame, 16 numbers, translation in elements 12-14, native game units (as native_source.json of the converter)',
           'motions': [{'id': m['id'], 'name': names.get(m['id'], {}).get('name'), 'end': m.get('end'),
                        'loop_key': m.get('loop_key'), 'frames': m.get('frames', [])} for m in src['motions']]}
    dest_file = Path(dest_file)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text(json.dumps(out), encoding='utf-8')
    return [dest_file]


def debug(folder, meta, dest_file):
    """Technical model data for inspection: every bone (parent, children, its mesh's vertices in model units,
    its polygons with texture page, semi-transparency mode and UVs in texels of the page), the texture pages and
    the motions' summary. Everything as the converter read it from the game file."""
    src = json.loads((Path(folder) / 'native_source.json').read_text(encoding='utf-8'))
    out = {'format': 'dw3viewer-model-debug-1', 'model': meta['file'], 'name': meta['name'], 'kind': meta.get('kind'),
           'counts': meta['counts'], 'textures': meta['textures'], 'tex_origin': src.get('tex_origin'),
           'face': meta.get('face'), 'motions': [{k: m[k] for k in ('id', 'name', 'frames', 'end', 'scripts')} for m in meta['motions']],
           'bones': []}
    for info, b in zip(meta['bones'], src['bones']):
        out['bones'].append(dict(info, vertex_positions=b['vertices'],
                                 polygons=[{'image': f['image'], 'abr': f['abr'], 'indices': f['indices'], 'uv': f['uv']} for f in b['faces']]))
    dest_file = Path(dest_file)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    return [dest_file]
