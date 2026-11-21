"""Game version, the executable's file table and the battle's fighters table.

Everything here is read from the disc and checked; nothing is guessed. Sources (dw3_decomp, MIT,
https://github.com/ReGame-Labs/dw3_decomp, a byte-matching decompilation of all three versions):

- config/{us,eu,jp}/symbols.txt: FILE_SECTORS (s32 first sector per file number) and
  FILE_SECTOR_COUNTS (u16 sector count per file number), different addresses per version.
- include/battle/battle_mode/model.h: FILE_FIGHTERS = 0x1BE (USA, Japan), 0x1CC (Europe);
  FightersFile, FighterEntry {u16 id, u8 index, u8 kind}, FighterInfo (partner 0xC4 bytes) and
  FighterInfoEnemy (0x48 bytes); model / motions / effects = (file number << 16) | archive entry.
- include/engine/file.h: the European disc numbers its files differently and keeps every text file
  once per language; the Japanese disc numbers like the USA one.
"""
from pathlib import Path
import struct

# executable name -> facts of that version
VERSIONS = {
    'SLUS_014.36': {'id': 'us', 'title': 'Digimon World 3', 'region': 'NTSC-U (USA)',
                    'file_sectors': 0x80044B78, 'file_counts': 0x80046DD4, 'fighters': 0x1BE},
    'SLES_039.36': {'id': 'eu', 'title': 'Digimon World 2003', 'region': 'PAL (Europa)',
                    'file_sectors': 0x80044F6C, 'file_counts': 0x800474A4, 'fighters': 0x1CC},
    'SLPS_034.46': {'id': 'jp', 'title': 'Digimon World 3: Aratanaru Bouken no Tobira', 'region': 'NTSC-J (Japan)',
                    'file_sectors': 0x80044D98, 'file_counts': 0x80047284, 'fighters': 0x1BE},
}


def find_executable(disc):
    """(name, bytes) of the game's executable on DISC; ValueError for any other disc."""
    for e in disc.entries:
        name = Path(e.path).name.upper().split(';')[0]
        if name in VERSIONS and not e.directory:
            return name, disc.read(e.lba, e.size)
    raise ValueError('Kein Digimon World 3 / 2003: SLUS_014.36, SLES_039.36 oder SLPS_034.46 fehlt im Abbild.')


def detect(disc):
    """Facts about the version of DISC, including the executable's own load address check."""
    name, exe = find_executable(disc)
    if exe[:8] != b'PS-X EXE':
        raise ValueError(f'{name} ist kein PS-X EXE.')
    info = dict(VERSIONS[name], executable=name, volume=disc.volume)
    info['text_start'] = struct.unpack_from('<I', exe, 0x18)[0]
    return info, exe


def file_table(disc):
    """(version facts, {file number: (first sector, sector count)}) from the executable's table."""
    info, exe = detect(disc)
    text = info['text_start']
    count = (info['file_counts'] - info['file_sectors']) // 4

    def offset(addr):
        o = addr - text + 0x800
        if not 0x800 <= o < len(exe):
            raise ValueError('Dateitabelle liegt außerhalb des Programms.')
        return o
    starts = struct.unpack_from(f'<{count}i', exe, offset(info['file_sectors']))
    lengths = struct.unpack_from(f'<{count}H', exe, offset(info['file_counts']))
    table = {fid: (lba, n) for fid, (lba, n) in enumerate(zip(starts, lengths)) if lba > 0 and n > 0}
    if len(table) < 100 or any(lba + n > disc.sector_count for lba, n in table.values()):
        raise ValueError('Dateitabelle des Programms passt nicht zum Abbild (beschädigt oder andere Version).')
    return info, table


def _face(data, at):
    """FighterInfo.face: up to 16 FaceRects of 10 bytes (x, y, w, h in VRAM halfwords relative to the
    model's texture origin; three source frames open / half / closed), ended by an x of 0xFF.
    Rects 0 and 1 are the eyes (getEyesFrame), the others cycle (FIGHTSTG_updateFace)."""
    rects = []
    for i in range(16):
        p = at + i * 10
        if not 0 <= p <= len(data) - 10 or data[p] == 0xFF:
            break
        x, y, w, h, *uv = data[p:p + 10]
        rects.append({'x': x, 'y': y, 'w': w, 'h': h, 'frames': [(uv[0], uv[1]), (uv[2], uv[3]), (uv[4], uv[5])]})
    return rects


def fighters(disc, info=None, table=None):
    """Every entry of the fighters' file: id, kind, enemy, model / motions / effects (file, entry), face."""
    if table is None:
        info, table = file_table(disc)
    fid = info['fighters']
    if fid not in table:
        raise ValueError('Kämpferdatei fehlt in der Dateitabelle.')
    lba, sectors = table[fid]
    data = disc.read(lba, sectors * 2048)
    base, entries, partners, enemies = struct.unpack_from('<4I', data, 0)
    out = []
    at = entries
    while at + 4 <= len(data):
        ident, index, kind = struct.unpack_from('<HBB', data, at)
        if ident == 0:
            break
        enemy = kind >= 0x3A
        rec = enemies + index * 0x48 if enemy else partners + index * 0xC4
        if rec + 16 > len(data):
            raise ValueError('Kämpfertabelle ist abgeschnitten.')
        model, motions, effects, face_ptr = struct.unpack_from('<4I', data, rec)
        out.append({'id': ident, 'kind': kind, 'enemy': enemy,
                    'model': (model >> 16, model & 0xFFFF), 'motions': (motions >> 16, motions & 0xFFFF),
                    'effects': (effects >> 16, effects & 0xFFFF), 'face': _face(data, face_ptr - base)})
        at += 4
    if not out:
        raise ValueError('Kämpfertabelle ist leer.')
    return out
