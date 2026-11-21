"""A DW3 / DW2003 disc image as a library of battle models: catalog, conversion, details.

The image is only read. Converted models (glTF binary, texture PNGs, native motion samples) go to a
cache folder per image; the original image is never written.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

from .disc import Disc, Entry
from .recovery import recover_entries
from . import game, names, motions
from .effects import EFFECT_MODELS_US

MODEL_NAME = re.compile(r'^M\d{3}[A-Z0-9_]{1,12}\.(?:BIN|PRO)$', re.I)
EFFECT_NAME = re.compile(r'^MEFT\d{4}\.BIN$', re.I)
CONVERTER_FORMAT = 'dw3-converter-9'   # bump when the converter's output changes


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def converter_path():
    exe = 'dw3_converter.exe' if os.name == 'nt' else 'dw3_converter'
    for p in (resource_root() / 'native' / 'bin' / exe, resource_root() / 'build' / exe):
        if p.is_file():
            return p
    raise ValueError('DW3-Konverter fehlt. Bitte "python tools/build_native.py" ausführen (C++17-Compiler).')


def _run(args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('kein PNG')
    return struct.unpack('>II', head[16:24])


def read_glb(path):
    data = Path(path).read_bytes()
    if data[:4] != b'glTF':
        raise ValueError('Keine GLB-Datei')
    n = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + n])
    rest = data[20 + n:]
    binary = b''
    if len(rest) >= 8 and rest[4:8] == b'BIN\0':
        binary = rest[8:8 + struct.unpack_from('<I', rest, 0)[0]]
    return doc, binary


def face_map(rects, src):
    """Where each face part's copies land in the decoded texture pages.

    The game copies VRAM rectangles (FIGHTSTG_moveFacePart, DR_MOVE; x, y, w, h in 16-bit VRAM units relative to
    the model's texture origin). A page image of the converter is one (tpage, CLUT) of VRAM decoded, so the same
    copy is a copy of texels inside each page image of that tpage: x * 4 texels for 4-bit pages, x * 2 for 8-bit.
    Only parts whose source and destination lie in one tpage are mapped (all 257 used parts of the USA disc do)."""
    ox, oy = src.get('tex_origin', [0, 0])
    parts = []
    for i, r in enumerate(rects):
        if not r['w'] or not r['h']:
            continue
        def page(x, y):
            return (ox + x) // 64, (oy + y) // 256
        dst = page(r['x'], r['y'])
        corners = [page(r['x'] + r['w'] - 1, r['y'] + r['h'] - 1)] + [page(fx, fy) for fx, fy in r['frames']] + \
                  [page(fx + r['w'] - 1, fy + r['h'] - 1) for fx, fy in r['frames']]
        part = {'index': i, 'kind': 'eyes' if i < 2 else 'cycle', 'targets': [], 'note': None}
        if any(c != dst for c in corners):
            part['note'] = 'Quelle und Ziel liegen in verschiedenen Texturseiten (nicht abgebildet)'
            parts.append(part)
            continue
        tp = dst[0] | dst[1] << 4
        for k, (tpage, _clut) in enumerate(src.get('pages', [])):
            if tpage is None or tpage < 0 or (tpage & 0x1F) != tp:
                continue
            mul = {0: 4, 1: 2, 2: 1}.get(tpage >> 7 & 3, 1)
            bx, by = dst[0] * 64, dst[1] * 256
            local = lambda x, y: [(ox + x - bx) * mul, oy + y - by]
            part['targets'].append({'image': k, 'dst': local(r['x'], r['y']) + [r['w'] * mul, r['h']],
                                    'src': [local(fx, fy) for fx, fy in r['frames']]})
        parts.append(part)
    return {'parts': parts, 'eyes_rule': 'face.c FIGHTSTG_getEyesFrame / FIGHTSTG_updateFace'}


class Library:
    def __init__(self, path, cache):
        disc = Disc(path)
        try:
            self.info, self.table = game.file_table(disc)
            self.path = disc.path.resolve()
            st = self.path.stat()
            self.stamp = (st.st_size, st.st_mtime_ns)
            self.key = hashlib.sha256(f'dw3viewer-v2:{self.path}:{self.stamp}'.encode()).hexdigest()[:24]
            self.cache = Path(cache) / self.key
            self.cache.mkdir(parents=True, exist_ok=True)
            self.entries = self._entries(disc)
            if not self.entries:
                raise ValueError('Keine Kampfmodelle (FIGHT/MODEL) im Abbild gefunden.')
            try:
                self.fighters = game.fighters(disc, self.info, self.table)
            except (ValueError, struct.error) as e:
                self.fighters, self.fighter_error = [], str(e)
            self.names = self._names(disc)
            self.effects = self._effects()
            self.all = self.entries + [e['entry'] for e in self.effects]
            self.rows = [dict(m, kind='digimon') for m in self.names['models']] + [e['row'] for e in self.effects]
            self.volume = disc.volume
            self.sector_size = disc.sector_size
        finally:
            disc.close()

    # ---------------------------------------------------------------- catalog
    def _entries(self, disc):
        index = self.cache / 'index.json'
        try:
            doc = json.loads(index.read_text(encoding='utf-8'))
            if doc.get('format') != 1:
                raise ValueError
            entries = [Entry(**e) for e in doc['entries']]
        except (OSError, ValueError, TypeError, KeyError):
            found = list(disc.entries) + recover_entries(self.path, disc.sector_size)
            entries = list({(Path(e.path).name, e.lba, e.size): e for e in found if not e.directory}.values())
            tmp = index.with_suffix('.tmp')
            tmp.write_text(json.dumps({'format': 1, 'entries': [asdict(e) for e in entries]}), encoding='utf-8')
            tmp.replace(index)
        self.index = [e for e in entries if e.lba + (e.size + 2047) // 2048 <= disc.sector_count]
        ok = [e for e in self.index if MODEL_NAME.fullmatch(Path(e.path).name.split(';')[0])]
        return sorted(ok, key=lambda e: Path(e.path).name)

    def _effects(self):
        """Effect models (MEFT####): those of the game's effect table (model and motion entry known), then the
        other MEFT files of the disc, which load with the first entry that reads as a bone list."""
        by_lba = {}
        for e in self.index:
            if EFFECT_NAME.fullmatch(Path(e.path).name.split(';')[0]):
                by_lba.setdefault(e.lba, e)
        out, used, seen = [], set(), set()
        table = EFFECT_MODELS_US if self.info['id'] in ('us', 'jp') else []
        for eid, file, motions in table:
            if (eid, file, motions) in seen:      # the game's table holds {310, 0x834000A, 0x8340000} twice
                continue
            seen.add((eid, file, motions))
            fid = file >> 16
            lba = self.table.get(fid, (None, 0))[0]
            e = by_lba.get(lba)
            if not e:
                continue
            used.add(e.lba)
            out.append({'entry': e, 'model_entry': file & 0xFFFF, 'motion_entry': motions & 0xFFFF, 'effect_id': eid,
                        'file_number': fid})
        for lba, e in sorted(by_lba.items(), key=lambda kv: Path(kv[1].path).name):
            if lba not in used:
                fid = next((f for f, (l, _) in self.table.items() if l == lba), None)
                out.append({'entry': e, 'model_entry': None, 'motion_entry': None, 'effect_id': None, 'file_number': fid})
        base = len(self.entries)
        for k, x in enumerate(out):
            stem = Path(x['entry'].path).name.split(';')[0].rsplit('.', 1)[0].upper()
            name = f"Effekt {x['effect_id']}" if x['effect_id'] is not None else f'Effektdatei {stem}'
            x['row'] = {'id': base + k, 'kind': 'effect', 'name': name, 'code': stem, 'file': Path(x['entry'].path).name.split(';')[0],
                        'path': x['entry'].path, 'aliases': [], 'variant': 'Effektmodell', 'status': 'effect',
                        'status_text': ('Effekttabelle FIGHTSTG_effectModels (effect_model.c)' if x['effect_id'] is not None
                                        else 'MEFT-Datei ohne Eintrag in der Effekttabelle'),
                        'fighter_ids': [], 'enemy': False, 'effect_id': x['effect_id'], 'file_number': x['file_number']}
        return out

    def _names(self, disc):
        path = self.cache / 'names.json'
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
            if doc.get('version') == 2 and [m['path'] for m in doc['models']] == [e.path for e in self.entries]:
                return doc
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            doc = names.build(disc, self.info, self.table, self.fighters, self.entries)
        except (ValueError, KeyError, struct.error) as e:
            doc = {'version': 2, 'note': f'Namen nicht lesbar: {e}',
                   'models': [{'id': i, 'name': Path(e.path).stem, 'code': Path(e.path).stem, 'file': Path(e.path).name,
                               'path': e.path, 'aliases': [], 'variant': '', 'status': 'unreadable',
                               'status_text': names.STATUS['unreadable'], 'fighter_ids': [], 'enemy': False}
                              for i, e in enumerate(self.entries)]}
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
        tmp.replace(path)
        return doc

    def summary(self):
        return {'game': self.info['title'], 'region': self.info['region'], 'version': self.info['id'],
                'executable': self.info['executable'], 'volume': self.volume, 'file': self.path.name,
                'sector_size': self.sector_size, 'models': len(self.entries), 'effects': len(self.effects),
                'effects_in_table': sum(1 for e in self.effects if e['effect_id'] is not None), 'files_in_table': len(self.table),
                'fighters': len(self.fighters), 'names_note': self.names.get('note'),
                'fighter_error': getattr(self, 'fighter_error', None)}

    def failures(self):
        try:
            return json.loads((self.cache / 'failed.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _failed(self, ident, reason):
        f = self.failures()
        f[str(ident)] = reason
        tmp = self.cache / 'failed.tmp'
        tmp.write_text(json.dumps(f, ensure_ascii=False), encoding='utf-8')
        tmp.replace(self.cache / 'failed.json')

    def catalog(self):
        out, failed = [], self.failures()
        for i, (e, m) in enumerate(zip(self.all, self.rows)):
            out.append({'id': i, 'kind': m['kind'], 'name': m['name'], 'code': m['code'], 'file': m['file'], 'size': e.size,
                        'enemy': m.get('enemy', False), 'variant': m.get('variant', ''), 'aliases': m.get('aliases', []),
                        'status': m['status'], 'fighter_ids': m.get('fighter_ids', []), 'effect_id': m.get('effect_id'),
                        'unsupported': failed.get(str(i)),
                        'thumb': f'cache/{self.key}/thumbs/{i}.png' if (self.cache / 'thumbs' / f'{i}.png').is_file() else None,
                        'converted': (self.cache / f'model_{i:04d}' / 'meta.json').is_file()})
        return out

    def _check(self, ident):
        if type(ident) is not int or not 0 <= ident < len(self.all):
            raise ValueError('Unbekanntes Modell')
        st = self.path.stat()
        if (st.st_size, st.st_mtime_ns) != self.stamp:
            raise ValueError('Das Abbild wurde verändert. Bitte erneut öffnen.')
        return self.all[ident]

    # ---------------------------------------------------------------- one model
    def folder(self, ident):
        return self.cache / f'model_{ident:04d}'

    def model(self, ident):
        """Convert model IDENT (once) and return its details (meta.json)."""
        entry = self._check(ident)
        target = self.folder(ident)
        meta_path = target / 'meta.json'
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            if meta.get('format') == CONVERTER_FORMAT:
                return meta
            shutil.rmtree(target, ignore_errors=True)
        exe = converter_path()
        with tempfile.TemporaryDirectory(prefix='conv-', dir=self.cache) as tmp:
            tmp = Path(tmp)
            disc = Disc(self.path)
            try:
                disc.extract(entry, tmp / 'source.bin')
            finally:
                disc.close()
            eff = self.effects[ident - len(self.entries)] if ident >= len(self.entries) else None
            args = [str(exe), str(tmp / 'source.bin'), str(tmp / 'out')]
            if eff and eff['model_entry'] is not None:
                args += [str(eff['model_entry']), str(eff['motion_entry'])]
            proc = _run(args)
            if proc.returncode != 0 or not (tmp / 'out' / 'model.glb').is_file():
                reason = 'Nicht unterstützt: ' + (proc.stderr.strip()[:800] or f'Code {proc.returncode}')
                if proc.returncode in (3, 4):
                    self._failed(ident, reason)
                raise ValueError(reason)
            if eff:
                scripts, script_error = [], 'Effektmodell: spielt einmal und endet (FIGHTSTG_updateEffectModel)'
            else:
                scripts, script_error = self._scripts(entry, tmp / 'source.bin')
            meta = self._meta(ident, entry, tmp / 'out', scripts, script_error)
            (tmp / 'out' / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
            if target.exists():
                shutil.rmtree(target)
            (tmp / 'out').rename(target)
        return meta

    def _scripts(self, entry, source):
        """The action scripts of the fighter that uses this file, or ([], reason)."""
        fids = [fid for fid, (lba, _) in self.table.items() if lba == entry.lba]
        if len(fids) != 1:
            return [], 'Datei nicht eindeutig in der Dateitabelle'
        own = [r for r in self.fighters if r['model'][0] == fids[0] and r['effects'][0] == fids[0]]
        if not own:
            return [], 'Kein Kämpfer mit eigenen Skripten in dieser Datei'
        archives = {r['effects'][1] for r in own}
        if len(archives) != 1:
            return [], 'Mehrere Skriptarchive für dieselbe Datei'
        proc = _run([str(converter_path()), '--scripts', str(source), str(archives.pop())], 60)
        if proc.returncode != 0:
            return [], 'Skripte nicht lesbar: ' + (proc.stderr.strip()[:300] or str(proc.returncode))
        return json.loads(proc.stdout)['scripts'], None

    def _meta(self, ident, entry, out, scripts, script_error):
        src = json.loads((out / 'native_source.json').read_text(encoding='utf-8'))
        doc, _ = read_glb(out / 'model.glb')
        prim = doc['meshes'][0]['primitives'] if doc.get('meshes') else []
        verts = sum(doc['accessors'][p['attributes']['POSITION']]['count'] for p in prim)
        tris = sum(doc['accessors'][p['indices'] if 'indices' in p else p['attributes']['POSITION']]['count'] // 3 for p in prim)
        native_verts = sum(len(b['vertices']) for b in src['bones'])
        children = {}
        for i, b in enumerate(src['bones']):
            if i:
                children.setdefault(b['parent'], []).append(i)
        bones = [{'index': i, 'parent': b['parent'], 'children': children.get(i, []), 'vertices': len(b['vertices']),
                  'faces': len(b['faces']), 'quads': sum(1 for f in b['faces'] if len(f['indices']) == 4),
                  'images': sorted({f['image'] for f in b['faces']}), 'abr': sorted({f['abr'] for f in b['faces'] if f['abr']})}
                 for i, b in enumerate(src['bones'])]
        faces = [f for b in src['bones'] for f in b['faces']]
        quads = sum(1 for f in faces if len(f['indices']) == 4)
        textures = []
        for i, name in enumerate(src['images']):
            w, h = png_size(out / name)
            page = src['pages'][i] if i < len(src['pages']) else [None, None]
            textures.append({'file': name, 'width': w, 'height': h, 'tpage': page[0], 'clut': page[1],
                             'depth': {0: '4 Bit (16 Farben)', 1: '8 Bit (256 Farben)', 2: '16 Bit'}.get((page[0] or 0) >> 7 & 3)})
        gl_anims = {a['name']: a for a in doc.get('animations', [])}
        mot = []
        for m in src['motions']:
            frames = len(m.get('frames', []))
            # bones whose mesh the game does not draw in a frame (scaled to 48 or less, FIGHTSTG_updateModel):
            # the converter writes them with a collapsed matrix; one character per frame, '1' = hidden
            hidden = {}
            for b in range(1, len(src['bones'])):
                mask = ''.join('1' if b < len(fr) and sum(v * v for v in fr[b][:3]) < 1e-12 else '0' for fr in m.get('frames', []))
                if '1' in mask:
                    hidden[str(b)] = mask
            lab = motions.label(m['id'], scripts)
            mot.append({'id': m['id'], 'name': lab['de'], 'name_en': lab['en'], 'name_source': lab['source'],
                        'scripts': lab['scripts'], 'frames': frames, 'seconds': round(frames / src['fps'], 3),
                        'keys': m.get('keys'), 'end': m.get('end'), 'loop_key': m.get('loop_key'),
                        'gltf': f"motion_{m['id']}" if f"motion_{m['id']}" in gl_anims else None, 'hidden': hidden})
        row = self.rows[ident]
        fids = [fid for fid, (lba, _) in self.table.items() if lba == entry.lba]
        users = [r for r in self.fighters if fids and r['model'][0] == fids[0]] if row['kind'] == 'digimon' else []
        face = face_map(users[0]['face'] if users else [], src)
        return {
            'format': CONVERTER_FORMAT, 'id': ident, 'kind': row['kind'], 'effect_id': row.get('effect_id'),
            'name': row['name'], 'code': row['code'], 'file': row['file'],
            'variant': row.get('variant', ''), 'name_status': row.get('status_text', ''),
            'data': {'path': entry.path, 'lba': entry.lba, 'size': entry.size, 'file_number': fids[0] if len(fids) == 1 else None,
                     'fighters': [{'id': r['id'], 'kind': r['kind'], 'enemy': r['enemy'], 'model': list(r['model']),
                                   'motions': list(r['motions']), 'effects': list(r['effects'])} for r in users],
                     'face_rects': users[0]['face'] if users else []},
            'counts': {'bones': len(src['bones']) - 1, 'vertices_native': native_verts, 'faces_native': len(faces),
                       'quads_native': quads, 'triangles_native': len(faces) - quads, 'vertices_gpu': verts,
                       'triangles_gpu': tris, 'materials': len(prim)},
            'textures': textures, 'fps': src['fps'], 'motions': mot, 'motion_count': len(mot),
            'face': face, 'bones': bones,
            'scripts': [{'index': s['index'], 'motions': s['motions'], 'hits': s.get('hits')} for s in scripts],
            'script_note': script_error,
            'files': {'glb': 'model.glb', 'native': 'native_source.json'},
        }
