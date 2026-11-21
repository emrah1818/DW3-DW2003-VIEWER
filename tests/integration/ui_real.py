"""Interface test with a real disc image (not part of CI: needs your own game data).
  python tests/integration/ui_real.py IMAGE OUTDIR
Opens the image, loads several models, plays motions, steps frames, toggles every display option,
compares two motions, exports every format and writes screenshots to OUTDIR."""
import json, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

image, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
data = tempfile.mkdtemp(prefix='dw3v-ui-')
root = Path(__file__).resolve().parents[2]
srv = subprocess.Popen([sys.executable, '-m', 'dw3viewer', '--serve', f'--data={data}'], cwd=root, stdout=subprocess.PIPE, text=True)
url = srv.stdout.readline().strip()
fails = 0
def check(what, ok, detail=''):
    global fails; fails += not ok
    print(('PASS ' if ok else 'FAIL ') + what + (f' | {detail}' if detail != '' else ''), flush=True)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        pg = b.new_context(viewport={'width': 1500, 'height': 920}, locale='de-DE').new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(url); pg.wait_for_function('window.__viewer && window.__viewer.info', timeout=30000)
        pg.evaluate('p => window.__viewer.openDisc(p)', image)
        pg.wait_for_function('window.__viewer.state.catalog.length > 0', timeout=120000)
        n = pg.evaluate('window.__viewer.state.catalog.length'); check('Katalog', n > 200, n)
        pg.fill('#q', 'Guilmon'); pg.wait_for_timeout(200)
        names = pg.evaluate('[...document.querySelectorAll("#list .n")].map(e => e.textContent)'); check('Suche Guilmon', 'Guilmon' in names, names)
        for name in ('Guilmon', 'WarGreymon', 'Imperialdramon-F', 'Agumon'):
            pg.fill('#q', name); pg.wait_for_timeout(150)
            pg.locator('#list .item').first.click()
            pg.wait_for_function('n => window.__viewer.state.meta && window.__viewer.state.meta.name === n && !document.querySelector("#busy:not(.hidden)")', arg=name, timeout=120000)
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(out / f'{name}_idle.png'))
            m = pg.evaluate('window.__viewer.state.meta.counts'); check(f'{name} geladen', m['triangles_gpu'] > 0, m)
        # animation controls
        mot = pg.evaluate('window.__viewer.state.meta.motions.filter(m => m.gltf).map(m => m.id)')
        pg.evaluate('id => window.__viewer.playMotion(id)', mot[min(5, len(mot) - 1)])
        pg.wait_for_timeout(700)
        f1 = pg.evaluate('window.__viewer.view.frameIndex()'); check('Wiedergabe läuft', f1 > 0, f1)
        pg.click('#t-play'); f2 = pg.evaluate('window.__viewer.view.frameIndex()'); pg.wait_for_timeout(400)
        check('Pause hält', pg.evaluate('window.__viewer.view.frameIndex()') == f2)
        pg.click('#t-next'); check('Bild vor', pg.evaluate('window.__viewer.view.frameIndex()') == f2 + 1)
        pg.click('#t-prev'); pg.click('#t-prev'); check('Bild zurück', pg.evaluate('window.__viewer.view.frameIndex()') == f2 - 1)
        txt = pg.inner_text('#t-frame'); check('Bildanzeige', '/' in txt, txt)
        for sel in ('#o-wire', '#o-cull', '#o-skel', '#o-grid', '#o-nearest'):
            pg.click(sel)
        pg.wait_for_timeout(300); pg.screenshot(path=str(out / 'options.png'))
        for sel in ('#o-wire', '#o-cull', '#o-skel', '#o-grid', '#o-nearest'):
            pg.click(sel)
        # compare
        pg.click('.tabs button[data-tab=anim]'); pg.check('#cmp'); pg.wait_for_timeout(1500)
        check('Vergleich: zwei Modelle', pg.evaluate('!!window.__viewer.view.b'))
        pg.screenshot(path=str(out / 'compare.png'))
        pg.uncheck('#cmp'); pg.wait_for_timeout(500)
        # exports
        exp = Path(tempfile.mkdtemp(prefix='dw3v-exp-'))
        mid = pg.evaluate('window.__viewer.state.meta.id')
        for kind, dest in (('glb', exp / 'a.glb'), ('obj', exp), ('png', exp), ('motions', exp / 'a.motions.json'), ('json', exp / 'a.json')):
            files = pg.evaluate('([i, k, d]) => window.__viewer.api("export", i, k, d)', [mid, kind, str(dest)])
            check(f'Export {kind}', bool(files) and all(Path(f).is_file() and Path(f).stat().st_size > 0 for f in files), files)
        # HD texture: a 2048x4096 PNG made from the page itself, scaled with nearest
        from PIL import Image
        meta = pg.evaluate('window.__viewer.state.meta')
        base = Path(data) / 'cache' / pg.evaluate('window.__viewer.state.base').split('/')[1] / f"model_{mid:04d}"
        big = exp / 'big.png'; Image.open(base / 'tex0.png').resize((2048, 4096), Image.NEAREST).save(big)
        r = pg.evaluate('([i, f]) => window.__viewer.api("hd_import", i, "tex0.png", f)', [mid, str(big)])
        check('HD-Import 2048×4096', r.get('tex0.png', {}).get('width') == 2048, r)
        pg.evaluate('id => { window.__viewer.state.sel = -1; return window.__viewer.select(id); }', mid); pg.wait_for_timeout(1500)
        pg.click('#mode button[data-v=hd]'); pg.wait_for_timeout(500)
        check('HD nach erneutem Öffnen geladen', pg.evaluate('window.__viewer.view.a.hdMaps.size') == 1)
        pg.screenshot(path=str(out / 'hd.png'))
        pg.click('#mode button[data-v=orig]')
        bad = pg.evaluate('window.__viewer.api("model", window.__viewer.state.catalog.find(m => m.file === "M500WAVE.BIN").id).then(() => "ok", e => e.message)')
        check('Unlesbare Datei: Fehlermeldung statt Absturz', bad != 'ok', bad)
        # game-hidden parts, PS1 blend modes, debug view (WarGreymon: flames hidden in idle, additive blending)
        wg = pg.evaluate('window.__viewer.state.catalog.find(m => m.file === "M213WGRE.BIN").id')
        pg.evaluate('i => { window.__viewer.state.sel = -1; return window.__viewer.select(i); }', wg)
        pg.wait_for_function('i => window.__viewer.state.meta && window.__viewer.state.meta.id === i', arg=wg, timeout=120000)
        pg.evaluate('window.__viewer.playMotion(1)'); pg.wait_for_timeout(1500)
        hid = pg.evaluate('Array.from(window.__viewer.view.a.hidden).filter(x => x > 0).length')
        check('Vom Spiel ausgeblendete Teile (WarGreymon Idle)', hid > 0, hid)
        blend = pg.evaluate('''(() => { const a = window.__viewer.view.a; const r = [];
            a.root.traverse(o => { if (o.isMesh && o.renderOrder === 1) r.push([o.material.blendEquation, o.material.blendSrc, o.material.blendDst, o.material.transparent]); });
            return { modes: [...a.semiModes], twins: r.length, sample: r[0] }; })()''')
        check('PS1-Mischmodus: halbtransparenter Durchgang angelegt', blend['twins'] > 0 and len(blend['modes']) > 0, blend)
        if 1 in blend['modes']:
            check('Modus 1 = B + F (One, One, Add)', pg.evaluate('''(() => { let ok = false; window.__viewer.view.a.root.traverse(o => {
                if (o.isMesh && o.renderOrder === 1 && /_abr2/.test(o.material.name)) ok = o.material.blendSrc === 201 && o.material.blendDst === 201 && o.material.blendEquation === 100; }); return ok; })()'''))
        pg.click('.tabs button[data-tab=dbg]'); pg.wait_for_selector('#dbg-bones .bone', timeout=30000)
        nb = pg.evaluate('document.querySelectorAll("#dbg-bones .bone").length')
        b0 = pg.evaluate('window.__viewer.state.meta.bones[0]')
        check('Debug: Knochenbaum (alle Knochen außer Ursprung 0)', nb == len(pg.evaluate('window.__viewer.state.meta.bones')) - 1 and b0['vertices'] == 0, [nb, b0['vertices']])
        pg.click('#dbg-bones .bone:nth-child(3)'); pg.wait_for_timeout(400)
        info = pg.inner_text('#dbg-info'); check('Debug: Auswahl + Werte', pg.evaluate('window.__viewer.view.a.sel.value') >= 0 and len(info) > 20, info[:80].replace('\n', ' '))
        uv = pg.evaluate('(() => { const c = document.getElementById("dbg-uv"); const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) n += d[i] > 0; return n; })()')
        check('Debug: UV-Ansicht gezeichnet', uv > 1000, uv)
        pg.locator('#dbg-bones [data-vis]').nth(2).uncheck(); pg.wait_for_timeout(200)
        check('Debug: Teil ausgeblendet', pg.evaluate('window.__viewer.view.a.userHidden.size') == 1)
        pg.click('#dbg-only'); pg.wait_for_timeout(200)
        check('Debug: Nur Auswahl', pg.evaluate('window.__viewer.view.a.userHidden.size') == nb - 1)
        pg.click('#dbg-all'); check('Debug: Alle zeigen', pg.evaluate('window.__viewer.view.a.userHidden.size') == 0)
        files = pg.evaluate('([i, d]) => window.__viewer.api("export", i, "debug", d)', [wg, str(exp / 'wg.debug.json')])
        dj = json.loads(Path(files[0]).read_text()) if files else {}
        check('Debug-Export', len(dj.get('bones', [])) == nb + 1, len(dj.get('bones', [])))
        pg.click('[data-look=side]'); side = pg.evaluate('(() => { const c = window.__viewer.view.camera.position, t = window.__viewer.view.controls.target; return [c.x - t.x, c.z - t.z]; })()')
        check('Kamera Seite', abs(side[0]) > 5 * abs(side[1]), side)
        # stability: 40 model changes (Digimon and effects) with motion switches in between; GPU memory must not grow
        ids = pg.evaluate('(() => { const c = window.__viewer.state.catalog.filter(m => !m.unsupported); return [0, 20, 60, 100, 147, 200, 260, 300, 350, 420].map(i => c[i % c.length].id); })()')
        mem = []
        for k in range(4):
            for i in ids:
                pg.evaluate('i => { window.__viewer.state.sel = -1; return window.__viewer.select(i); }', i)
                pg.wait_for_function('i => window.__viewer.state.meta && window.__viewer.state.meta.id === i && !document.querySelector("#busy:not(.hidden)")', arg=i, timeout=120000)
                for mid in pg.evaluate('window.__viewer.state.meta.motions.filter(m => m.gltf).slice(0, 6).map(m => m.id)'):
                    pg.evaluate('id => window.__viewer.playMotion(id)', mid)
                pg.wait_for_timeout(60)
            mem.append(pg.evaluate('(() => { const m = window.__viewer.view.renderer.info.memory; return [m.geometries, m.textures]; })()'))
        check('Speicher stabil nach 40 Modellwechseln', mem[-1][0] <= mem[0][0] + 2 and mem[-1][1] <= mem[0][1] + 4, mem)
        check('Vorschaubilder in der Liste', pg.evaluate('document.querySelectorAll("#list img.th").length') > 0)
        pg.click('[data-look=side]'); pg.click('[data-look=top]'); pg.click('[data-look=front]')
        check('keine JS-Fehler', not errs, errs)
        b.close()
finally:
    srv.terminate()
print('FAILS', fails); sys.exit(1 if fails else 0)
