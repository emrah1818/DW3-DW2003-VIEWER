// 3D view: one battle model (glTF from the converter) with its own motions, optionally a second copy
// of the same model next to it to compare two motions. Textures are the game's pages; in the original
// mode they are drawn with nearest texels like the PlayStation, HD pages replace them 1:1 by UV.
import * as THREE from './lib/three.module.js';
import { OrbitControls } from './lib/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from './lib/examples/jsm/loaders/GLTFLoader.js';

const FPS = 30;

class Instance {
  constructor(gltf) {
    this.root = gltf.scene;
    this.clips = new Map(gltf.animations.map(c => [c.name, c]));
    this.mixer = new THREE.AnimationMixer(this.root);
    this.action = null;
    this.hiddenMasks = {};                // bone -> '0101…' per frame of the playing motion
    this.hidden = new Float32Array(256);  // per bone: 1 = the game does not draw its mesh in this frame
    this.materials = [];
    this.root.traverse(o => {
      if (o.isMesh) {
        o.frustumCulled = false;
        for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
          if (!this.materials.includes(m)) this.materials.push(m);
        }
      }
    });
    for (const m of this.materials) {
      m.userData.page = Number((m.name.match(/^tex(\d+)/) || [])[1] ?? -1);
      m.userData.originalMap = m.map;
      m.userData.blend = m.transparent || m.alphaMode === 'BLEND' || /_abr/.test(m.name);
      const hidden = this.hidden;
      // a vertex belongs wholly to one bone (JOINTS_0.x); its triangle collapses outside the view when
      // that bone is hidden in the current frame, as the game skips the bone's mesh
      m.onBeforeCompile = sh => {
        sh.uniforms.uHidden = { value: hidden };
        sh.vertexShader = 'uniform vec4 uHidden[64];\n' + sh.vertexShader.replace('#include <project_vertex>',
          '#include <project_vertex>\n#ifdef USE_SKINNING\n{ int hj = int(skinIndex.x); if (uHidden[hj / 4][hj - (hj / 4) * 4] > 0.5) gl_Position = vec4(0.0, 0.0, -2.0, 1.0); }\n#endif');
      };
      m.customProgramCacheKey = () => 'dw3hidden';
    }
  }
  setHidden(masks) { this.hiddenMasks = masks || {}; this.hidden.fill(0); this.updateHidden(); }
  updateHidden() {
    const f = this.action ? Math.round(this.action.time * FPS) : 0;
    this.hidden.fill(0);
    for (const [b, mask] of Object.entries(this.hiddenMasks)) {
      const i = Math.min(Math.max(0, f), mask.length - 1);
      if (mask[i] === '1') this.hidden[Number(b)] = 1;
    }
  }
  play(name, loop) {
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
    this.mixer.stopAllAction();
    this.root.traverse(o => { if (o.isMesh) { o.geometry.dispose(); } });
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
    this.opts = { filter: 'nearest', wireframe: false, cull: false, hd: false, skeleton: false };
    this.hdMaps = new Map();                 // page -> THREE.Texture
    this.speed = 1; this.playing = false; this.loop = true;
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
    for (const i of [this.a, this.b]) if (i) i.updateHidden();
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    if (this.onTick) this.onTick();
  }

  async load(url) {
    const gltf = await this.loader.loadAsync(url);
    this.clear();
    this.a = new Instance(gltf);
    this.scene.add(this.a.root);
    this.hdMaps.clear();
    this.applyMaterials();
    this.measure();
    this.frame();
    return this.a;
  }

  async compare(url, on) {
    if (this.b) { this.scene.remove(this.b.root); this.b.dispose(); this.b = null; }
    if (on && url && this.a) {
      this.b = new Instance(await this.loader.loadAsync(url));
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

  setBackground(hex) { this.scene.background = new THREE.Color(hex); }
  setGrid(on) { this.grid.visible = on; }

  setOption(k, v) { this.opts[k] = v; this.applyMaterials(); }

  setSkeleton(on) {
    this.opts.skeleton = on;
    if (this.skel) { this.scene.remove(this.skel); this.skel = null; }
    if (on && this.a) { this.skel = new THREE.SkeletonHelper(this.a.root); this.scene.add(this.skel); }
  }

  async setHd(maps) {
    // maps: {page: url}
    this.hdMaps.clear();
    const tl = new THREE.TextureLoader();
    for (const [page, url] of Object.entries(maps || {})) {
      const t = await tl.loadAsync(url);
      t.flipY = false;                     // glTF convention, as the converter's pages
      t.colorSpace = THREE.SRGBColorSpace;
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      this.hdMaps.set(Number(page), t);
    }
    this.applyMaterials();
  }

  applyMaterials() {
    for (const inst of [this.a, this.b]) {
      if (!inst) continue;
      for (const m of inst.materials) {
        const hd = this.opts.hd ? this.hdMaps.get(m.userData.page) : null;
        m.map = hd || m.userData.originalMap;
        if (m.map) {
          const nearest = this.opts.filter === 'nearest' && !hd;
          m.map.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter;
          m.map.minFilter = nearest ? THREE.NearestFilter : THREE.LinearMipmapLinearFilter;
          m.map.anisotropy = nearest ? 1 : this.renderer.capabilities.getMaxAnisotropy();
          m.map.generateMipmaps = !nearest;
          m.map.needsUpdate = true;
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
