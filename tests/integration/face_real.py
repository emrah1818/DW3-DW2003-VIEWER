"""Face/eye animation with a real disc image: for several Digimon, forces the eyes to each of the game's three
frames and checks that the drawn picture changes exactly in the face, that the motion rule of face.c holds
(motions 4-11 closed, 2 half) and that random blinking happens while open.
  python tests/integration/face_real.py IMAGE OUTDIR"""
import subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops

image, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
srv = subprocess.Popen([sys.executable, '-m', 'dw3viewer', '--serve', f'--data={tempfile.mkdtemp()}'], cwd=root, stdout=subprocess.PIPE, text=True)
url = srv.stdout.readline().strip()
fails = 0
def check(what, ok, detail=''):
    global fails; fails += not ok
    print(('PASS ' if ok else 'FAIL ') + what + (f' | {detail}' if detail != '' else ''), flush=True)
NAMES = ['Guilmon', 'Agumon', 'Kumamon', 'WarGreymon', 'Veemon', 'Renamon']
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = b.new_context(viewport={'width': 1300, 'height': 900}).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(url); pg.wait_for_function('window.__viewer && window.__viewer.info')
        pg.evaluate('p => window.__viewer.openDisc(p)', image); pg.wait_for_function('window.__viewer.state.catalog.length > 0', timeout=120000)
        for name in NAMES:
            ident = pg.evaluate('n => (window.__viewer.state.catalog.find(m => m.name === n) || {}).id', name)
            if ident is None:
                check(f'{name} im Katalog', False); continue
            pg.evaluate('i => window.__viewer.select(i)', ident)
            pg.wait_for_function('n => window.__viewer.state.meta && window.__viewer.state.meta.name === n && !document.querySelector("#busy:not(.hidden)")', arg=name, timeout=120000)
            parts = pg.evaluate('window.__viewer.state.meta.face.parts.filter(p => p.targets.length).length')
            if not parts:
                print(f'INFO {name}: keine Gesichtsteile in den Daten'); continue
            pg.evaluate('() => { const v = window.__viewer.view; v.faceOn = false; v.pause(true); v.seekFrame(0); }')
            shots = []
            for f in (0, 1, 2):
                pg.evaluate('f => { const fa = window.__viewer.view.a.face; for (const p of fa.parts) fa.want(p.index, p.kind === "eyes" ? f : 0); }', f)
                pg.wait_for_timeout(250)
                path = out / f'{name}_eyes{f}.png'; pg.locator('#c').screenshot(path=str(path)); shots.append(Image.open(path).convert('RGB'))
            d01 = ImageChops.difference(shots[0], shots[1]).getbbox(); d02 = ImageChops.difference(shots[0], shots[2]).getbbox()
            check(f'{name}: Augen halb/zu ändern das Bild', d01 is not None and d02 is not None, (d01, d02))
            if d02:
                w, h = shots[0].size; area = (d02[2] - d02[0]) * (d02[3] - d02[1]) / (w * h)
                check(f'{name}: Änderung nur im Gesicht (< 6 % des Bildes)', area < 0.06, round(area, 4))
            # back to open restores the first picture exactly (no leftover texels, no flicker)
            pg.evaluate('() => { const fa = window.__viewer.view.a.face; for (const p of fa.parts) fa.want(p.index, 0); }'); pg.wait_for_timeout(250)
            pg.locator('#c').screenshot(path=str(out / 'tmp.png'))
            check(f'{name}: zurück auf offen = Ausgangsbild', ImageChops.difference(shots[0], Image.open(out / 'tmp.png').convert('RGB')).getbbox() is None)
            # motion rule
            r = pg.evaluate('''() => { const fa = window.__viewer.view.a.face; return [1, 2, 4, 7, 11, 12, 13].map(m => fa.eyesFor(m)); }''')
            check(f'{name}: Augenregel face.c', r == [0, 1, 2, 2, 2, 0, 0], r)
        # blinking: simulated game time, count closed frames while open
        pg.evaluate('''() => { const fa = window.__viewer.view.a.face; fa.motion = 1; window.__seen = new Set(); for (let i = 0; i < 2000; i++) { fa.step(1 / 60); window.__seen.add(fa.frames[0]); } }''')
        seen = pg.evaluate('[...window.__seen]')
        check('Blinzeln: offen, halb und zu kommen vor', sorted(seen) == [0, 1, 2], seen)
        check('keine JS-Fehler', not errs, errs)
        b.close()
finally:
    srv.terminate()
print('FAILS', fails); sys.exit(1 if fails else 0)
