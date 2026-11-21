"""HD textures: your own PNGs for a model's texture pages, kept per game version and model file.

A replacement is stored as it is (no colour reduction, no compression beyond PNG's lossless one) in
<user data>/hd/<version>/<model file>/texN.png and loaded again whenever that model is opened. The
model's UVs are fractions of the page, so a page of any size maps the same way (for example
2048 x 4096 for a 128 x 256 page)."""
from pathlib import Path
import re
import shutil
import struct

MAX_SIDE = 8192
NAME = re.compile(r'^tex\d{1,2}\.png$')


def folder(root, version, model_file):
    stem = Path(model_file).stem.upper()
    if not re.fullmatch(r'[A-Z0-9_]{1,20}', stem):
        raise ValueError('Ungültiger Modellname')
    return Path(root) / 'hd' / version / stem


def png_size(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        raise ValueError('Bitte eine PNG-Datei wählen.')
    return struct.unpack('>II', data[16:24])


def import_png(root, version, model_file, texture, source):
    if not NAME.fullmatch(texture):
        raise ValueError('Unbekannte Texturseite')
    data = Path(source).read_bytes()
    w, h = png_size(data)
    if not (1 <= w <= MAX_SIDE and 1 <= h <= MAX_SIDE):
        raise ValueError(f'PNG {w}×{h}: höchstens {MAX_SIDE} Pixel je Seite.')
    dest = folder(root, version, model_file)
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / (texture + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(dest / texture)
    return {'texture': texture, 'width': w, 'height': h}


def remove(root, version, model_file, texture):
    if not NAME.fullmatch(texture):
        raise ValueError('Unbekannte Texturseite')
    p = folder(root, version, model_file) / texture
    if p.is_file():
        p.unlink()
    return True


def listing(root, version, model_file):
    d = folder(root, version, model_file)
    out = {}
    if d.is_dir():
        for p in sorted(d.glob('tex*.png')):
            if NAME.fullmatch(p.name):
                w, h = png_size(p.read_bytes()[:24])
                out[p.name] = {'width': w, 'height': h, 'mtime': p.stat().st_mtime_ns}
    return out


def export_all(root, version, model_file, dest):
    d = folder(root, version, model_file)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(d.glob('tex*.png')) if d.is_dir() else []:
        shutil.copy2(p, dest / ('hd_' + p.name))
        out.append(dest / ('hd_' + p.name))
    return out
