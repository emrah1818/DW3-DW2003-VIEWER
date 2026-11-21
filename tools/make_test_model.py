"""Writes www/test/model.glb: a small skinned, textured, animated model made up here (no game data), built like the
converter's output (material texN_abrM, semi-transparent texels with alpha 128, two joints, one animation).
The Windows smoke test draws it, so the graphics path that draws real models is tested on the build machine.
  python tools/make_test_model.py"""
import json
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'www' / 'test'


def png(w, h, rgba):
    raw = b''.join(b'\x00' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main():
    w = h = 64
    px = []
    for y in range(h):
        for x in range(w):
            on = (x // 8 + y // 8) % 2
            px += [240, 120, 40, 255] if on else ([40, 160, 240, 128] if y < 32 else [250, 250, 250, 255])
    image = png(w, h, px)
    # a box of two segments; lower half bound to joint 0, upper to joint 1
    pos, nrm, uv, jnt, wgt, idx = [], [], [], [], [], []
    for seg in range(2):
        y0, y1 = seg * 10.0, seg * 10.0 + 10.0
        faces = [((0, 0, 1), [(-4, y0, 4), (4, y0, 4), (4, y1, 4), (-4, y1, 4)]),
                 ((0, 0, -1), [(4, y0, -4), (-4, y0, -4), (-4, y1, -4), (4, y1, -4)]),
                 ((1, 0, 0), [(4, y0, 4), (4, y0, -4), (4, y1, -4), (4, y1, 4)]),
                 ((-1, 0, 0), [(-4, y0, -4), (-4, y0, 4), (-4, y1, 4), (-4, y1, -4)])]
        for n, quad in faces:
            b = len(pos)
            for k, p in enumerate(quad):
                pos.append(p); nrm.append(n); uv.append(((k in (1, 2)) * 1.0, (k >= 2) * 1.0))
                jnt.append((seg, 0, 0, 0)); wgt.append((1.0, 0.0, 0.0, 0.0))
            idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    times = [i / 10 for i in range(11)]
    rots = []
    for t in times:
        a = math.sin(t * math.pi * 2) * 0.5
        rots.append((0.0, 0.0, math.sin(a / 2), math.cos(a / 2)))
    ibm = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] + [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, -10, 0, 1]

    blob, views, accs = bytearray(), [], []

    def add(data, fmt, count, ctype, atype, target=None, minmax=None):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        blob.extend(struct.pack('<' + fmt * count, *data) if fmt != 'raw' else data)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(blob) - off}
        if target:
            v['target'] = target
        views.append(v)
        if atype is None:
            return len(views) - 1
        acc = {'bufferView': len(views) - 1, 'componentType': ctype, 'count': count, 'type': atype}
        if minmax:
            acc['min'], acc['max'] = minmax
        accs.append(acc)
        return len(accs) - 1

    flat = lambda rows: [c for r in rows for c in r]
    lo = [min(p[i] for p in pos) for i in range(3)]
    hi = [max(p[i] for p in pos) for i in range(3)]
    a_pos = add(flat(pos), 'f', len(pos) * 3, 5126, 'VEC3', 34962, (lo, hi))
    accs[a_pos]['count'] = len(pos)
    a_nrm = add(flat(nrm), 'f', len(nrm) * 3, 5126, 'VEC3', 34962); accs[a_nrm]['count'] = len(nrm)
    a_uv = add(flat(uv), 'f', len(uv) * 2, 5126, 'VEC2', 34962); accs[a_uv]['count'] = len(uv)
    a_j = add(flat(jnt), 'B', len(jnt) * 4, 5121, 'VEC4', 34962); accs[a_j]['count'] = len(jnt)
    a_w = add(flat(wgt), 'f', len(wgt) * 4, 5126, 'VEC4', 34962); accs[a_w]['count'] = len(wgt)
    a_i = add(idx, 'H', len(idx), 5123, 'SCALAR', 34963)
    a_ibm = add(ibm, 'f', 32, 5126, 'MAT4'); accs[a_ibm]['count'] = 2
    a_t = add(times, 'f', len(times), 5126, 'SCALAR', None, ([0.0], [1.0]))
    a_r = add(flat(rots), 'f', len(rots) * 4, 5126, 'VEC4'); accs[a_r]['count'] = len(rots)
    v_img = add(image, 'raw', 0, None, None)

    gltf = {
        'asset': {'version': '2.0', 'generator': 'dw3viewer make_test_model'},
        'scene': 0, 'scenes': [{'nodes': [0, 2]}],
        'nodes': [{'name': 'bone_0', 'children': [1]}, {'name': 'bone_1', 'translation': [0, 10, 0]},
                  {'name': 'mesh', 'mesh': 0, 'skin': 0}],
        'skins': [{'joints': [0, 1], 'inverseBindMatrices': a_ibm, 'skeleton': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': a_pos, 'NORMAL': a_nrm, 'TEXCOORD_0': a_uv,
                                                    'JOINTS_0': a_j, 'WEIGHTS_0': a_w}, 'indices': a_i, 'material': 0}]}],
        'materials': [{'name': 'tex0_abr2', 'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}, 'metallicFactor': 0,
                                                                      'roughnessFactor': 1}, 'alphaMode': 'BLEND', 'doubleSided': True}],
        'textures': [{'source': 0, 'sampler': 0}],
        'samplers': [{'magFilter': 9728, 'minFilter': 9728, 'wrapS': 33071, 'wrapT': 33071}],
        'images': [{'bufferView': v_img, 'mimeType': 'image/png'}],
        'animations': [{'name': 'motion_1', 'samplers': [{'input': a_t, 'output': a_r, 'interpolation': 'LINEAR'}],
                        'channels': [{'sampler': 0, 'target': {'node': 1, 'path': 'rotation'}}]}],
        'buffers': [{'byteLength': 0}], 'bufferViews': views, 'accessors': accs,
    }
    while len(blob) % 4:
        blob.append(0)
    gltf['buffers'][0]['byteLength'] = len(blob)
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    glb = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)) + struct.pack('<II', len(js), 0x4E4F534A) + js \
        + struct.pack('<II', len(blob), 0x004E4942) + bytes(blob)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'model.glb').write_bytes(glb)
    (OUT / 'tex0.png').write_bytes(image)
    print(OUT / 'model.glb', len(glb))


if __name__ == '__main__':
    main()
