"""Tests without game data (run in CI): text decoding, file table, motion names, OBJ export, HD
textures, server safety. Tests with your own disc image: tests/test_real_disc.py."""
import io, json, struct, threading, urllib.request
from pathlib import Path
import pytest

from dw3viewer import names, motions, game, hd, export
from dw3viewer.server import API, make_server


def test_decode_glyphs_icons_and_codes():
    # 4 + index into GLYPHS: 'A' is GLYPHS[10] (0x8260), 'g' GLYPHS[42] (0x8287); icon 1 = space
    raw = bytes([4 + 10, 4 + 42, 1, 1, 4 + 10, 0, 99])
    assert names.decode(raw) == 'Ag A'


def test_read_dignam_offsets():
    strings = [b'', bytes([4 + 10, 4 + 42, 4 + 56, 4 + 48, 4 + 50, 4 + 49, 0])]   # 'Agumon'
    head = 4 + 4 * len(strings)
    offs, body = [], b''
    for s in strings:
        offs.append(head + len(body) if s else 0)
        body += s
    data = struct.pack('<i', len(strings) - 1) + struct.pack(f'<{len(offs)}i', *offs) + body
    assert names.read_dignam(data)[1] == 'Agumon'


def test_read_dignam_rejects_garbage():
    with pytest.raises(ValueError):
        names.read_dignam(b'\xff\xff\xff\x7f' + b'\0' * 8)


class FakeDisc:
    """An image with one executable whose file table points at sectors that exist."""
    def __init__(self, exe_name, info, files):
        text = 0x80010000
        size = max(info['file_counts'] + 2 * (info['file_counts'] - info['file_sectors']) // 4, info['file_sectors'] + 4) - text + 0x800 + 16
        exe = bytearray(size)
        exe[:8] = b'PS-X EXE'
        struct.pack_into('<I', exe, 0x18, text)
        for fid, (lba, n) in files.items():
            struct.pack_into('<i', exe, info['file_sectors'] - text + 0x800 + 4 * fid, lba)
            struct.pack_into('<H', exe, info['file_counts'] - text + 0x800 + 2 * fid, n)
        from dw3viewer.disc import Entry
        self.entries = [Entry(exe_name, 30, len(exe), False)]
        self.exe = bytes(exe)
        self.sector_count = 100000
        self.volume = 'TEST'

    def read(self, lba, size):
        assert lba == 30
        return self.exe[:size]


@pytest.mark.parametrize('exe', list(game.VERSIONS))
def test_file_table_every_version(exe):
    info = game.VERSIONS[exe]
    files = {i: (1000 + i, 1 + i % 3) for i in range(150)}
    disc = FakeDisc(exe, info, files)
    got_info, table = game.file_table(disc)
    assert got_info['executable'] == exe and got_info['id'] == info['id']
    assert table == {i: v for i, v in files.items()}


def test_file_table_rejects_other_games():
    disc = FakeDisc('SLUS_011.93', game.VERSIONS['SLUS_014.36'], {})
    with pytest.raises(ValueError):
        game.file_table(disc)


def test_file_table_rejects_table_outside_image():
    info = game.VERSIONS['SLUS_014.36']
    disc = FakeDisc('SLUS_014.36', info, {i: (99990 + i, 5) for i in range(150)})
    with pytest.raises(ValueError):
        game.file_table(disc)


def test_motion_labels_only_from_code():
    scripts = [{'index': 0, 'motions': [1]}, {'index': 1, 'motions': [4]}, {'index': 2, 'motions': [5, 12]},
               {'index': 3, 'motions': [5, 11]}, {'index': 4, 'motions': [3]}, {'index': 7, 'motions': [27]},
               {'index': 16, 'motions': [45]}]
    assert motions.label(1, scripts)['de'].startswith('Idle')
    assert motions.label(2, scripts)['en'].startswith('Idle, weak')
    assert motions.label(13, scripts)['de'] == 'Sieg'
    assert motions.label(12, scripts)['de'] == 'Treffer'
    assert motions.label(11, scripts)['en'] == 'Knockout'
    assert motions.label(4, scripts)['de'] == 'Treffer (Zwischentreffer)'
    assert motions.label(3, scripts)['de'] == 'Ausweichen (verfehlt)'
    assert motions.label(5, scripts)['scripts'] == [2, 3] and motions.label(5, scripts)['de'] == 'Treffer / K. o.'
    assert motions.label(27, scripts)['de'] == 'Technik-Skript 7'
    assert motions.label(45, scripts)['de'] == 'Skript 16'
    assert motions.label(40, scripts)['de'] == 'Motion 40'


def _tiny_glb(path):
    pos = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    uv = struct.pack('<6f', 0, 0, 1, 0, 0, 1)
    binary = pos + uv
    doc = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': len(binary)}],
           'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 36}, {'buffer': 0, 'byteOffset': 36, 'byteLength': 24}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3'},
                         {'bufferView': 1, 'componentType': 5126, 'count': 3, 'type': 'VEC2'}],
           'images': [{'uri': 'tex0.png'}], 'textures': [{'source': 0}],
           'materials': [{'name': 'tex0_abr1', 'alphaMode': 'BLEND', 'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'TEXCOORD_0': 1}, 'material': 0}]}]}
    js = json.dumps(doc).encode(); js += b' ' * (-len(js) % 4)
    out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(binary))
    out += struct.pack('<I', len(js)) + b'JSON' + js + struct.pack('<I', len(binary)) + b'BIN\0' + binary
    Path(path).write_bytes(out)


def test_obj_export_keeps_geometry_uv_and_texture(tmp_path):
    src = tmp_path / 'm'; src.mkdir()
    _tiny_glb(src / 'model.glb')
    (src / 'tex0.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 30)
    files = export.obj(src, tmp_path / 'out', 'Agu mon')
    objtxt = (tmp_path / 'out' / 'Agu_mon.obj').read_text()
    assert objtxt.count('\nv ') == 3 and objtxt.count('\nvt ') == 3 and 'f 1/1 2/2 3/3' in objtxt
    assert 'vt 1.000000 1.000000' in objtxt          # glTF v=0 -> OBJ v=1
    mtl = (tmp_path / 'out' / 'Agu_mon.mtl').read_text()
    assert 'map_Kd tex0.png' in mtl and 'd 0.5' in mtl
    assert (tmp_path / 'out' / 'tex0.png').is_file() and len(files) == 3


def _png(path, w, h):
    import zlib
    raw = b''.join(b'\0' + b'\0\0\0' * w for _ in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def test_hd_texture_any_size_kept_as_is(tmp_path):
    _png(tmp_path / 'a.png', 2048, 4096)
    r = hd.import_png(tmp_path, 'us', 'M366GIRU.BIN', 'tex0.png', tmp_path / 'a.png')
    assert (r['width'], r['height']) == (2048, 4096)
    stored = tmp_path / 'hd' / 'us' / 'M366GIRU' / 'tex0.png'
    assert stored.read_bytes() == (tmp_path / 'a.png').read_bytes()
    assert hd.listing(tmp_path, 'us', 'M366GIRU.BIN')['tex0.png']['width'] == 2048
    hd.remove(tmp_path, 'us', 'M366GIRU.BIN', 'tex0.png')
    assert hd.listing(tmp_path, 'us', 'M366GIRU.BIN') == {}


@pytest.mark.parametrize('bad', ['../x.png', 'tex0.jpg', 'tex.png'])
def test_hd_rejects_bad_names(tmp_path, bad):
    _png(tmp_path / 'a.png', 4, 4)
    with pytest.raises(ValueError):
        hd.import_png(tmp_path, 'us', 'M366GIRU.BIN', bad, tmp_path / 'a.png')
    # a model file name only ever contributes its stem: the folder stays inside the data folder
    assert tmp_path / 'hd' in hd.folder(tmp_path, 'us', '../../etc').parents
    with pytest.raises(ValueError):
        hd.folder(tmp_path, 'us', 'a b.bin')


def test_server_token_methods_and_paths(tmp_path):
    srv = make_server(API(data_dir=tmp_path))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = srv.url
        assert b'DW3 / DW2003' in urllib.request.urlopen(base).read()
        def post(name, args):
            req = urllib.request.Request(base + 'api/' + name, json.dumps(args).encode(), {'Content-Type': 'application/json'})
            return json.loads(urllib.request.urlopen(req).read())
        assert post('app_info', [])['data']['desktop'] is False
        r = post('model', [0]); assert not r['ok'] and 'Abbild' in r['error']
        r = post('open', ['/does/not/exist.cue']); assert not r['ok']
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base.rsplit('/', 2)[0] + '/wrongtoken/index.html')
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + 'cache/../../etc/passwd')
        req = urllib.request.Request(base + 'api/__init__', b'[]')
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(req)
    finally:
        srv.shutdown()


def test_open_rejects_damaged_or_foreign_images(tmp_path):
    api = API(data_dir=tmp_path / 'd')
    junk = tmp_path / 'junk.bin'
    junk.write_bytes(bytes(range(256)) * 9408)            # 2352-byte sectors, but no ISO9660
    with pytest.raises(ValueError, match='CD-Abbild'):
        api.open(str(junk))
    cue = tmp_path / 'x.cue'
    cue.write_text('FILE "missing.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
    with pytest.raises(ValueError, match='nicht gefunden'):
        api.open(str(cue))
    odd = tmp_path / 'odd.iso'
    odd.write_bytes(b'x' * 1000)
    with pytest.raises(ValueError):
        api.open(str(odd))
    assert api.lib is None


def test_effect_table_matches_decomp_shape():
    from dw3viewer.effects import EFFECT_MODELS_US
    assert len(EFFECT_MODELS_US) == 130
    # the game's table has one exact duplicate (id 310), kept as in dw3_decomp; the catalog lists it once
    assert len(set(EFFECT_MODELS_US)) == 129
    assert [e for e in EFFECT_MODELS_US if EFFECT_MODELS_US.count(e) > 1] == [(310, 0x834000A, 0x8340000)] * 2
    for _id, file, motion in EFFECT_MODELS_US:
        assert file >> 16 > 0 and motion >> 16 > 0          # (file number << 16) | archive entry


def test_face_map_texel_units_and_pages():
    from dw3viewer.library import face_map
    # 4-bit page at tpage x=10 (640 halfwords): one VRAM halfword = 4 texels; 8-bit page: 2 texels
    src = {'tex_origin': [640, 0], 'pages': [(10, 0), (10 | 1 << 7, 0), (11, 0)]}
    rect = {'x': 2, 'y': 5, 'w': 3, 'h': 4, 'frames': [[2, 5], [6, 5], [10, 5]]}
    m = face_map([rect, {'x': 0, 'y': 0, 'w': 0, 'h': 0, 'frames': []}], src)
    assert len(m['parts']) == 1 and m['parts'][0]['kind'] == 'eyes'
    t4, t8 = m['parts'][0]['targets']
    assert t4 == {'image': 0, 'dst': [8, 5, 12, 4], 'src': [[8, 5], [24, 5], [40, 5]]}
    assert t8 == {'image': 1, 'dst': [4, 5, 6, 4], 'src': [[4, 5], [12, 5], [20, 5]]}
    # a source in another tpage is reported, not mapped
    far = dict(rect, frames=[[2, 5], [70, 5], [10, 5]])
    p = face_map([far], src)['parts'][0]
    assert p['targets'] == [] and p['note']


def test_motion_labels_scripts_and_neutral():
    from dw3viewer.motions import label
    assert label(13, [])['en'] == 'Victory'
    l = label(20, [{'index': 3, 'motions': [20]}, {'index': 99, 'motions': [20]}])
    assert l['scripts'] == [3, 99] and 'Script 99' in l['en'] and l['source']
    assert label(40, [{'index': 3, 'motions': [20]}])['en'] == 'Motion 40'


def test_graphics_falls_back_after_crash_while_drawing(tmp_path):
    from dw3viewer.gpu import Graphics, FALLBACK
    g = Graphics(tmp_path)
    assert g.backend == FALLBACK[0]
    g.mark('ready')
    g2 = Graphics(tmp_path)                       # unclean end before any model was drawn: no switch
    assert g2.backend == FALLBACK[0] and g2.switched_from is None
    g2.mark('drawing')                            # crash while drawing
    g3 = Graphics(tmp_path)
    assert g3.backend == FALLBACK[1] and g3.switched_from == FALLBACK[0]
    g3.mark('drawing'); g3.mark('drawn'); g3.clean_exit()
    assert Graphics(tmp_path).backend == FALLBACK[1]          # a working backend is kept
    Graphics(tmp_path).set_choice(FALLBACK[0])
    assert Graphics(tmp_path).backend == FALLBACK[0]
    assert Graphics(tmp_path, forced='swiftshader').backend == 'swiftshader'
