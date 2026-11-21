// 3D view: one battle model (glTF from the converter) with its own motions, optionally a second copy
// of the same model next to it to compare two motions. Textures are the game's pages; in the original
// mode they are drawn with nearest texels like the PlayStation, HD pages replace them 1:1 by UV.
import * as THREE from './lib/three.module.js';
import { OrbitControls } from './lib/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from './lib/examples/jsm/loaders/GLTFLoader.js';

const FPS = 30;

// The game's face task (dw3_decomp face.c): eyes 0 open / 1 half / 2 closed by the motion playing
// (FIGHTSTG_getEyesFrame: motions 4-11 closed, motion 2 half), blinking at random while open (blinkTimer
// = random 0..127 + 60 battle frames, then half, closed, half); the other parts cycle three frames, six battle
// frames each. Battle frames are 60 per second. A change copies the part's frame over it in the texture page
// (DR_MOVE in VRAM; here a texSubImage of the same texels, alpha kept exactly).
// exact RGBA bytes of a decoded image (no premultiplication): read back from a small WebGL2 context
let readGl = null;
function rgbaOf(bitmap) {
  if (!readGl) readGl = new OffscreenCanvas(1, 1).getContext('webgl2', { premultipliedAlpha: false });
  const gl = readGl, tex = gl.createTexture(), fb = gl.createFramebuffer();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, bitmap);
  gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  const out = new Uint8Array(bitmap.width * bitmap.height * 4);
  gl.readPixels(0, 0, bitmap.width, bitmap.height, gl.RGBA, gl.UNSIGNED_BYTE, out);
  gl.deleteFramebuffer(fb); gl.deleteTexture(tex);
  return out;
}

class Face {
  constructor(parts) {
    this.parts = (parts || []).filter(p => p.targets.length);
    this.sets = new Map();          // key ('orig' | 'hd') -> {tex, pages: Map(image -> {w, h, px}), frames}
    this.timer = 0; this.time = 0; this.motion = 1;
    this.frames = new Array(16).fill(0);
  }
  // Each page is kept as bytes and every face copy is done on them in the game's order, like the DR_MOVE copies
  // in VRAM (a later copy reads what an earlier one wrote, as for parts whose source and target overlap); the
  // changed rectangle is then uploaded to the GPU texture.
  async prepare(key, textures, urls, scale) {
    const set = { tex: textures, pages: new Map(), scale, frames: new Array(16).fill(0) };
    for (const p of this.parts) {
      for (const t of p.targets) {
        if (!textures.has(t.image) || set.pages.has(t.image)) continue;
        const blob = await (await fetch(urls.get(t.image))).blob();
        const bmp = await createImageBitmap(blob, { premultiplyAlpha: 'none', colorSpaceConversion: 'none', imageOrientation: 'none' });
        set.pages.set(t.image, { w: bmp.width, h: bmp.height, px: rgbaOf(bmp), initial: null });
        bmp.close?.();
      }
    }
    for (const pg of set.pages.values()) pg.initial = pg.px.slice();
    this.sets.set(key, set);
  }
  reset(key) {
    const set = this.sets.get(key);
    if (!set) return;
    set.frames.fill(0);
    for (const pg of set.pages.values()) pg.px.set(pg.initial);
  }
  eyesFor(motion) { return motion >= 4 && motion <= 11 ? 2 : motion === 2 ? 1 : 0; }
  step(dt) {
    const frames = Math.max(0, dt * 60);
    let eyes = this.eyesFor(this.motion);
    if (eyes === 0) {
      switch (Math.floor(this.timer) >> 1) {
        case 0: this.timer = Math.floor(Math.random() * 128) + 60; eyes = 0; break;
        case 1: case 2: case 5: case 6: eyes = 1; break;
        case 3: case 4: eyes = 2; break;
        default: eyes = 0;
      }
      this.timer = Math.max(0, this.timer - frames);
    } else this.timer = 0;
    this.time += frames;
    const cycle = Math.floor((this.time % 18) / 6);
    for (const p of this.parts) this.want(p.index, p.kind === 'eyes' ? eyes : cycle);
  }
  want(index, frame) { this.frames[index] = frame; }
  apply(renderer, key) {
    const set = this.sets.get(key);
    if (!set) return;
    for (const p of this.parts) {          // the game's order: parts 0 and 1 (eyes), then 2..15
      const f = this.frames[p.index];
      if (set.frames[p.index] === f) continue;
      set.frames[p.index] = f;
      for (const t of p.targets) {
        const pg = set.pages.get(t.image), dst = set.tex.get(t.image);
        if (!pg || !dst) continue;
        const [sx, sy] = set.scale.get(t.image) || [1, 1];
        const x = Math.round(t.dst[0] * sx), y = Math.round(t.dst[1] * sy);
        const w = Math.round(t.dst[2] * sx), h = Math.round(t.dst[3] * sy);
        const u = Math.round(t.src[f][0] * sx), v = Math.round(t.src[f][1] * sy);
        const px = pg.px, W = pg.w;
        for (let r = 0; r < h; r++) {
          for (let c = 0; c < w; c++) {
            const s = ((v + r) * W + u + c) * 4, d = ((y + r) * W + x + c) * 4;
            px[d] = px[s]; px[d + 1] = px[s + 1]; px[d + 2] = px[s + 2]; px[d + 3] = px[s + 3];
          }
        }
        const patch = new Uint8Array(w * h * 4);
        for (let r = 0; r < h; r++) patch.set(px.subarray(((y + r) * W + x) * 4, ((y + r) * W + x + w) * 4), r * w * 4);
        const tx = new THREE.DataTexture(patch, w, h, THREE.RGBAFormat);
        tx.flipY = false; tx.generateMipmaps = false;
        renderer.copyTextureToTexture(new THREE.Vector2(x, y), tx, dst);
        tx.dispose();
      }
    }
  }
  dispose() { this.sets.clear(); }
}

// PS1 semi-transparency (GPU "abr" of each polygon; the converter names such materials texN_abrM, M = abr + 1).
// Only texels with the STP bit are blended (alpha 128 in the converter's pages); the others of the same polygon
// are opaque. So a semi-transparent primitive is drawn twice: its opaque texels, then its STP texels with the
// PlayStation's equation: 0 B/2 + F/2, 1 B + F, 2 B - F, 3 B + F/4 (B = what is drawn, F = the texel).
const BLEND = [
  { eq: THREE.AddEquation, src: THREE.SrcAlphaFactor, dst: THREE.OneMinusSrcAlphaFactor },
  { eq: THREE.AddEquation, src: THREE.OneFactor, dst: THREE.OneFactor },
  { eq: THREE.ReverseSubtractEquation, src: THREE.OneFactor, dst: THREE.OneFactor },
  { eq: THREE.AddEquation, src: THREE.OneFactor, dst: THREE.OneFactor },
];
const MODE_NAMES = ['B/2 + F/2', 'B + F', 'B − F', 'B + F/4'];

function patchMaterial(m, hidden, pass, mode, sel) {
  m.userData.pass = pass; m.userData.mode = mode;
  m.onBeforeCompile = sh => {
    sh.uniforms.uHidden = { value: hidden };
    sh.uniforms.uSel = sel;
    // a vertex belongs wholly to one bone (JOINTS_0.x); its triangle collapses outside the view when that bone is
    // hidden in the current frame, as the game skips the bone's mesh
    sh.vertexShader = 'uniform vec4 uHidden[64];\nvarying float vBone;\n' + sh.vertexShader.replace('#include <project_vertex>',
      '#include <project_vertex>\nvBone = -1.0;\n#ifdef USE_SKINNING\nvBone = skinIndex.x;\n{ int hj = int(skinIndex.x); if (uHidden[hj / 4][hj - (hj / 4) * 4] > 0.5) gl_Position = vec4(0.0, 0.0, -2.0, 1.0); }\n#endif');
    // debug view: the selected bone's polygons tinted
    sh.fragmentShader = 'uniform float uSel;\nvarying float vBone;\n' + sh.fragmentShader.replace('#include <colorspace_fragment>',
      '#include <colorspace_fragment>\nif (uSel >= 0.0 && abs(vBone - uSel) < 0.5) gl_FragColor.rgb = mix(gl_FragColor.rgb, vec3(1.0, 0.35, 0.15), 0.55);');
    if (pass === 'opaque') {
      sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>', '#include <map_fragment>\nif (diffuseColor.a < 0.75) discard;');
    } else if (pass === 'semi') {
      sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>',
        '#include <map_fragment>\nif (diffuseColor.a > 0.75 || diffuseColor.a < 0.25) discard;\n' + (mode === 0 ? 'diffuseColor.a = 0.5;' : 'diffuseColor.a = 1.0;'))
        .replace('#include <colorspace_fragment>', '#include <colorspace_fragment>\n' + (mode === 3 ? 'gl_FragColor.rgb *= 0.25;' : ''));
    }
  };
  m.customProgramCacheKey = () => `dw3:${pass}:${mode}`;
  if (pass === 'semi') {
    const b = BLEND[mode] || BLEND[0];
    m.transparent = true; m.depthWrite = false; m.alphaTest = 0;
    m.blending = THREE.CustomBlending; m.blendEquation = b.eq; m.blendSrc = b.src; m.blendDst = b.dst;
  }
  m.needsUpdate = true;
}

class Instance {
  constructor(gltf) {
    this.root = gltf.scene;
    this.clips = new Map(gltf.animations.map(c => [c.name, c]));
    this.mixer = new THREE.AnimationMixer(this.root);
    this.mixer.addEventListener('finished', () => { if (this.onFinished) this.onFinished(this); });
    this.action = null;
    this.hiddenMasks = {};                // bone -> '0101…' per frame of the playing motion
    this.hidden = new Float32Array(256);  // per bone: 1 = the game does not draw its mesh in this frame
    this.materials = [];
    this.semiModes = new Set();
    this.userHidden = new Set();          // debug view: bones the user switched off
    this.sel = { value: -1 };             // debug view: selected bone
    const meshes = [];
    this.root.traverse(o => { if (o.isMesh) meshes.push(o); });
    for (const o of meshes) {
      o.frustumCulled = false;
      const m = o.material;
      m.userData.page = Number((m.name.match(/^tex(\d+)/) || [])[1] ?? -1);
      m.userData.originalMap = m.map;
      const abr = Number((m.name.match(/_abr(\d)/) || [])[1] ?? 0);
      if (abr > 0) {
        const mode = abr - 1;
        this.semiModes.add(mode);
        patchMaterial(m, this.hidden, 'opaque', mode, this.sel);
        const semi = m.clone();
        semi.userData = { ...m.userData };
        patchMaterial(semi, this.hidden, 'semi', mode, this.sel);
        const twin = o.clone();
        twin.material = semi;
        if (o.isSkinnedMesh) twin.bind(o.skeleton, o.bindMatrix);
        twin.renderOrder = 1;
        twin.frustumCulled = false;
        o.parent.add(twin);
        this.materials.push(m, semi);
      } else {
        patchMaterial(m, this.hidden, 'plain', -1, this.sel);
        this.materials.push(m);
      }
    }
  }
  pageTextures() {
    const m = new Map();
    for (const mat of this.materials) if (mat.userData.page >= 0 && mat.userData.originalMap) m.set(mat.userData.page, mat.userData.originalMap);
    return m;
  }
  setHidden(masks) { this.hiddenMasks = masks || {}; this.hidden.fill(0); this.updateHidden(); }
  updateHidden() {
    const f = this.action ? Math.round(this.action.time * FPS) : 0;
    this.hidden.fill(0);
    for (const [b, mask] of Object.entries(this.hiddenMasks)) {
      const i = Math.min(Math.max(0, f), mask.length - 1);
      if (mask[i] === '1') this.hidden[Number(b)] = 1;
    }
    for (const b of this.userHidden) this.hidden[b] = 1;
  }
  animHidden(b) {
    const mask = this.hiddenMasks[String(b)];
    if (!mask) return false;
    const f = this.action ? Math.round(this.action.time * FPS) : 0;
    return mask[Math.min(Math.max(0, f), mask.length - 1)] === '1';
  }
  bone(j) {
    let found = null;
    this.root.traverse(o => { if (!found && o.isSkinnedMesh) found = o.skeleton.bones[j]; });
    return found;
  }
  play(name, loop) {
    this.motionId = Number(String(name || '').replace('motion_', '')) || 1;
    const clip = this.clips.get(name);
    this.mixer.stopAllAction();
    this.action = null;
    if (!clip) return 0;
    this.action = this.mixer.clipAction(clip);
    this.action.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
    this.action.clampWhenFinished = true;
    this.action.play();
    return clip.duration;
  }
  dispose() {
    this.face?.dispose();
    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.root);
    const textures = new Set();
    const skeletons = new Set();
    this.root.traverse(o => { if (o.isMesh) { o.geometry.dispose(); if (o.skeleton) skeletons.add(o.skeleton); } });
    for (const sk of skeletons) sk.dispose();     // frees the bone texture
    for (const m of this.materials) { if (m.userData.originalMap) textures.add(m.userData.originalMap); if (m.map) textures.add(m.map); m.dispose(); }
    for (const t of this.hdMaps?.values() || []) textures.add(t);
    for (const t of textures) { t.image?.close?.(); t.dispose(); }
    this.hdMaps = new Map();
  }
}

export class View3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#20242c');
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 5000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.screenSpacePanning = true;
    this.grid = new THREE.GridHelper(60, 30, 0x5a6474, 0x384050);
    this.scene.add(this.grid);
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.0));
    this.loader = new GLTFLoader();
    this.a = null; this.b = null;            // main model, comparison copy
    this.hdUrls = {};
    this.opts = { filter: 'nearest', wireframe: false, cull: false, hd: false, skeleton: false };
    this.speed = 1; this.playing = false; this.loop = true; this.faceOn = true;
    this.clock = new THREE.Clock();
    this.onTick = null;
    this.resize();
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    this.renderer.setAnimationLoop(() => this.tick());
  }

  resize() {
    const p = this.canvas.parentElement, w = Math.max(1, p.clientWidth), h = Math.max(1, p.clientHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  tick() {
    const dt = this.clock.getDelta();
    if (this.playing) {
      for (const i of [this.a, this.b]) if (i) i.mixer.update(dt * this.speed);
    }
    for (const i of [this.a, this.b]) {
      if (!i) continue;
      i.updateHidden();
      if (i.face) {
        i.face.motion = i.motionId || 1;
        if (this.playing && this.faceOn) i.face.step(dt * this.speed);
        i.face.apply(this.renderer, 'orig');
        i.face.apply(this.renderer, 'hd');
      }
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    if (this.onTick) this.onTick();
  }

  async makeInstance(url, meta) {
    const inst = new Instance(await this.loader.loadAsync(url));
    const base = url.slice(0, url.lastIndexOf('/') + 1);
    inst.face = new Face(meta?.face?.parts);
    const urls = new Map((meta?.textures || []).map((t, k) => [k, base + t.file]));
    await inst.face.prepare('orig', inst.pageTextures(), urls, new Map());
    return inst;
  }

  async load(url, meta) {
    this.meta = meta; this.url = url;
    const inst = await this.makeInstance(url, meta);
    inst.onFinished = () => { if (this.onFinished) this.onFinished(); };
    this.clear();
    this.a = inst;
    this.scene.add(this.a.root);
    this.hdUrls = {};
    this.applyMaterials();
    this.measure();
    this.frame();
    return this.a;
  }

  async compare(url, on) {
    if (this.b) { this.scene.remove(this.b.root); this.b.dispose(); this.b = null; }
    if (on && url && this.a) {
      this.b = await this.makeInstance(url, this.meta);
      if (this.hdUrls) await this.loadHd(this.b);
      this.scene.add(this.b.root);
      this.applyMaterials();
    }
    this.layout();
    this.frame();
  }

  clear() {
    for (const k of ['a', 'b']) {
      if (this[k]) { this.scene.remove(this[k].root); this[k].dispose(); this[k] = null; }
    }
    if (this.skel) { this.scene.remove(this.skel); this.skel = null; }
  }

  // the model's size at rest, measured once when it loads (skinned bounding boxes are cached by three.js,
  // so the comparison layout and the camera work from this box)
  measure() {
    this.a.root.position.set(0, 0, 0);
    this.a.root.updateMatrixWorld(true);
    this.a.root.traverse(o => { if (o.isSkinnedMesh) o.skeleton.update(); });
    this.baseBox = new THREE.Box3().setFromObject(this.a.root, true);
    if (this.baseBox.isEmpty()) this.baseBox.set(new THREE.Vector3(-5, 0, -5), new THREE.Vector3(5, 10, 5));
  }

  box() {
    const b = this.baseBox.clone();
    if (this.b) {
      const dx = this.offset();
      const l = this.baseBox.clone().translate(new THREE.Vector3(-dx, 0, 0)), r = this.baseBox.clone().translate(new THREE.Vector3(dx, 0, 0));
      b.copy(l).union(r);
    }
    return b;
  }

  offset() { const s = this.baseBox.getSize(new THREE.Vector3()); return Math.max(s.x, s.z * 0.6, 1) * 0.8; }

  layout() {
    if (!this.a) return;
    this.a.root.position.set(this.b ? -this.offset() : 0, 0, 0);
    if (this.b) this.b.root.position.set(this.offset(), 0, 0);
  }

  frame() {
    if (!this.a) return;
    const b = this.box(), size = b.getSize(new THREE.Vector3()), c = b.getCenter(new THREE.Vector3());
    const r = Math.max(size.x, size.y, size.z, 1);
    this.controls.target.copy(c);
    this.camera.position.set(c.x + r * 0.35, c.y + r * 0.25, c.z + r * 1.9);
    this.camera.near = r / 200; this.camera.far = r * 200;
    this.camera.updateProjectionMatrix();
    this.grid.position.y = b.min.y;
    this.grid.scale.setScalar(r / 30);
  }

  // camera presets: front, side, top (the model looks along +Z in the converter's glTF)
  look(dir) {
    if (!this.a) return;
    const b = this.box(), size = b.getSize(new THREE.Vector3()), c = b.getCenter(new THREE.Vector3());
    const r = Math.max(size.x, size.y, size.z, 1) * 2.1;
    const d = { front: [0, 0, 1], back: [0, 0, -1], side: [1, 0, 0], top: [0, 1, 0.0001] }[dir] || [0, 0, 1];
    this.controls.target.copy(c);
    this.camera.position.set(c.x + d[0] * r, c.y + d[1] * r, c.z + d[2] * r);
    this.camera.updateProjectionMatrix();
  }

  thumbnail(size = 96) {
    this.renderer.render(this.scene, this.camera);
    const src = this.canvas, c = document.createElement('canvas');
    c.width = c.height = size;
    const s = Math.min(src.width, src.height);
    c.getContext('2d').drawImage(src, (src.width - s) / 2, (src.height - s) / 2, s, s, 0, 0, size, size);
    return c.toDataURL('image/png');
  }

  setBackground(hex) { this.scene.background = new THREE.Color(hex); }
  setGrid(on) { this.grid.visible = on; }

  setOption(k, v) { this.opts[k] = v; this.applyMaterials(); }

  setSkeleton(on) {
    this.opts.skeleton = on;
    if (this.skel) { this.scene.remove(this.skel); this.skel = null; }
    if (on && this.a) { this.skel = new THREE.SkeletonHelper(this.a.root); this.scene.add(this.skel); }
  }

  async setHd(maps) {
    // maps: {page: url}; every model copy gets its own textures, so each can blink on its own
    this.hdUrls = maps || {};
    for (const inst of [this.a, this.b]) {
      if (!inst) continue;
      for (const t of inst.hdMaps?.values() || []) t.dispose();
      await this.loadHd(inst);
    }
    this.applyMaterials();
  }

  async loadHd(inst) {
    const tl = new THREE.TextureLoader();
    inst.hdMaps = new Map();
    const urls = new Map(), scale = new Map();
    for (const [page, url] of Object.entries(this.hdUrls || {})) {
      const t = await tl.loadAsync(url);
      t.flipY = false;                     // glTF convention, as the converter's pages
      t.colorSpace = THREE.SRGBColorSpace;
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      const k = Number(page), orig = this.meta?.textures?.[k];
      inst.hdMaps.set(k, t); urls.set(k, url);
      scale.set(k, [t.image.width / (orig?.width || 256), t.image.height / (orig?.height || 256)]);
    }
    if (inst.face) await inst.face.prepare('hd', inst.hdMaps, urls, scale);
  }

  applyMaterials() {
    for (const inst of [this.a, this.b]) {
      if (!inst) continue;
      for (const m of inst.materials) {
        const hd = this.opts.hd ? inst.hdMaps?.get(m.userData.page) : null;
        m.map = hd || m.userData.originalMap;
        if (m.map) {
          const nearest = this.opts.filter === 'nearest' && !hd;
          m.map.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter;
          m.map.minFilter = nearest ? THREE.NearestFilter : THREE.LinearMipmapLinearFilter;
          m.map.anisotropy = nearest ? 1 : this.renderer.capabilities.getMaxAnisotropy();
          m.map.generateMipmaps = !nearest;
          m.map.needsUpdate = true;     // uploads the page again as loaded: the face starts from its first state
          inst.face?.reset(hd ? 'hd' : 'orig');
        }
        m.wireframe = this.opts.wireframe;
        m.side = this.opts.cull ? THREE.FrontSide : THREE.DoubleSide;
        m.needsUpdate = true;
      }
    }
  }

  // ---- animation
  play(nameA, nameB, hiddenA, hiddenB) {
    const d = this.a ? this.a.play(nameA, this.loop) : 0;
    if (this.a) this.a.setHidden(hiddenA);
    if (this.b) { this.b.play(nameB ?? nameA, this.loop); this.b.setHidden(nameB ? hiddenB : hiddenA); }
    this.playing = true;
    this.clock.getDelta();
    return d;
  }
  setLoop(on) {
    this.loop = on;
    for (const i of [this.a, this.b]) if (i?.action) i.action.setLoop(on ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
  }
  pause(on) { this.playing = !on; this.clock.getDelta(); }
  time() { return this.a?.action ? this.a.action.time : 0; }
  duration() { return this.a?.action ? this.a.action.getClip().duration : 0; }
  frames() { return Math.max(1, Math.round(this.duration() * FPS) + 1); }
  frameIndex() { return Math.round(this.time() * FPS); }
  seekFrame(f) {
    const d = this.duration();
    const t = Math.min(Math.max(0, f / FPS), d);
    for (const i of [this.a, this.b]) {
      if (!i?.action) continue;
      i.action.paused = false;
      i.action.enabled = true;
      i.action.time = Math.min(t, i.action.getClip().duration);
      i.mixer.update(0);
    }
  }
  step(n) { this.playing = false; this.seekFrame(this.frameIndex() + n); }

  snapshot() { this.renderer.render(this.scene, this.camera); return this.canvas.toDataURL('image/png'); }
  glInfo() {
    const gl = this.renderer.getContext();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    return { renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), webgl2: this.renderer.capabilities.isWebGL2 };
  }
}
