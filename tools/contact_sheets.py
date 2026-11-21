"""Renders every model of your own disc image to contact sheets for a visual check (not in CI).
    python tools/contact_sheets.py IMAGE OUTDIR   (needs Chrome + Playwright)"""
import subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw

image, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[1]
srv = subprocess.Popen([sys.executable, '-m', 'dw3viewer', '--serve', f'--data={sys.argv[3] if len(sys.argv) > 3 else tempfile.mkdtemp()}'],
                       cwd=root, stdout=subprocess.PIPE, text=True)
url = srv.stdout.readline().strip()
tiles, errs = [], []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = b.new_context(viewport={'width': 1100, 'height': 700}).new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(url); pg.wait_for_function('window.__viewer && window.__viewer.info')
        pg.evaluate('p => window.__viewer.openDisc(p)', image); pg.wait_for_function('window.__viewer.state.catalog.length > 0', timeout=120000)
        cat = pg.evaluate('window.__viewer.state.catalog.map(m => [m.id, m.name, m.file])')
        for ident, name, file in cat:
            ok = pg.evaluate('''async i => { try { window.__viewer.state.sel = -1; await window.__viewer.select(i);
                return window.__viewer.state.meta && window.__viewer.state.meta.id === i; } catch (e) { return false; } }''', ident)
            if ok:
                pg.evaluate('() => { const v = window.__viewer.view; v.pause(true); v.seekFrame(0); }')
                pg.wait_for_timeout(120)
                shot = Path(tempfile.mkstemp(suffix='.png')[1]); pg.locator('#c').screenshot(path=str(shot))
                im = Image.open(shot).convert('RGB'); shot.unlink()
                w, h = im.size; s = min(w, h); im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((220, 220))
            else:
                im = Image.new('RGB', (220, 220), (60, 20, 20))
            ImageDraw.Draw(im).text((4, 4), f'{ident} {name}'[:32], fill=(255, 255, 255))
            ImageDraw.Draw(im).text((4, 206), file, fill=(180, 180, 180))
            tiles.append(im)
        b.close()
finally:
    srv.terminate()
per = 48
for k in range(0, len(tiles), per):
    sheet = Image.new('RGB', (8 * 220, 6 * 220), (10, 10, 10))
    for i, t in enumerate(tiles[k:k + per]):
        sheet.paste(t, ((i % 8) * 220, (i // 8) * 220))
    sheet.save(out / f'sheet_{k // per:02d}.jpg', quality=80)
print(len(tiles), 'models', 'errors:', errs[:3])
