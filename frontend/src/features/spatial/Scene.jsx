import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
/** Render only schema-validated primitives. No model-authored scripts, URLs or shaders. */
/** @param {{spec:import("./types").SceneSpec, selected:string|null, onSelect:(id:string)=>void, onError:(message:string)=>void, resetKey:number, isolated?:boolean, playing?:boolean, step?:number}} props */
export default function Scene({
  spec,
  selected,
  onSelect,
  onError,
  resetKey,
  isolated = false,
  playing = true,
  step = 0,
}) {
  const host = useRef(null),
    state = useRef({ selected, isolated, playing, step }),
    callback = useRef(onSelect),
    refresh = useRef(null);
  state.current = { selected, isolated, playing, step };
  callback.current = onSelect;
  useEffect(() => {
    refresh.current?.();
  }, [selected, isolated, playing, step]);
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      onError(
        "3D is unavailable on this device. All object explanations, guided steps and questions remain available below.",
      );
      return;
    }
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#152b2c");
    const camera = new THREE.PerspectiveCamera(44, 1, 0.1, 200);
    const c = spec.camera || { x: 8, y: 6, z: 12 };
    camera.position.set(c.x, c.y, c.z);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.domElement.setAttribute(
      "aria-label",
      "3D learning scene. Drag to rotate, scroll to zoom, right drag to pan. Select objects with the accessible list.",
    );
    el.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.minDistance = 1;
    controls.maxDistance = 70;
    scene.add(new THREE.AmbientLight("#f8eddc", 2));
    const light = new THREE.DirectionalLight("#ffffff", 3);
    light.position.set(8, 12, 10);
    scene.add(light);
    const root = new THREE.Group();
    scene.add(root);
    const grid = new THREE.GridHelper(50, 40, "#45665a", "#25433d");
    grid.position.y = -5;
    scene.add(grid);
    const objects = new Map(),
      labels = new Map();
    const vector = (p) => new THREE.Vector3(p.x, p.y, p.z);
    for (const o of spec.objects) {
      const size = o.dimensions,
        m = o.material;
      const material = new THREE.MeshStandardMaterial({
        color: m.color,
        opacity: m.opacity,
        transparent: m.opacity < 1,
        depthWrite: m.opacity >= 1,
        roughness: m.roughness,
        metalness: m.metalness,
      });
      let geometry, node;
      if (o.type === "sphere")
        geometry = new THREE.SphereGeometry(size.x / 2, 32, 24);
      if (o.type === "box")
        geometry = new THREE.BoxGeometry(size.x, size.y, size.z);
      if (o.type === "cylinder")
        geometry = new THREE.CylinderGeometry(
          size.x / 2,
          size.x / 2,
          size.y,
          28,
        );
      if (o.type === "cone")
        geometry = new THREE.ConeGeometry(size.x / 2, size.y, 28);
      if (o.type === "torus")
        geometry = new THREE.TorusGeometry(
          size.x / 2,
          Math.min(size.y / 5, size.x / 5),
          12,
          48,
        );
      if (["line", "curve"].includes(o.type)) {
        const points = o.points.map(vector);
        const pts =
          o.type === "curve"
            ? new THREE.CatmullRomCurve3(points).getPoints(60)
            : points;
        geometry = new THREE.BufferGeometry().setFromPoints(pts);
        node = new THREE.Line(
          geometry,
          new THREE.LineBasicMaterial({ color: m.color }),
        );
      }
      if (o.type === "arrow" || o.type === "bond") {
        const a = vector(o.points[0]),
          b = vector(o.points.at(-1)),
          direction = b.clone().sub(a),
          length = direction.length();
        if (o.type === "arrow")
          node = new THREE.ArrowHelper(
            direction.normalize(),
            a,
            Math.max(0.01, length),
            m.color,
            Math.min(0.5, length / 3),
            Math.min(0.25, length / 6),
          );
        else {
          geometry = new THREE.CylinderGeometry(
            0.065,
            0.065,
            Math.max(length, 0.01),
            10,
          );
          node = new THREE.Mesh(geometry, material);
          node.position.copy(a).add(b).multiplyScalar(0.5);
          node.quaternion.setFromUnitVectors(
            new THREE.Vector3(0, 1, 0),
            direction.normalize(),
          );
        }
      }
      if (o.type === "particles") {
        const points = [];
        for (let i = 0; i < 96; i++) {
          points.push(
            (Math.sin(i * 57.13) * size.x) / 2,
            (Math.sin(i * 93.71) * size.y) / 2,
            (Math.sin(i * 31.07) * size.z) / 2,
          );
        }
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(points, 3),
        );
        node = new THREE.Points(
          geometry,
          new THREE.PointsMaterial({ color: m.color, size: 0.09 }),
        );
      }
      if (!node) node = new THREE.Mesh(geometry, material);
      else if (node.material !== material) material.dispose();
      if (!["arrow", "bond"].includes(o.type))
        node.position.copy(vector(o.position));
      node.traverse((child) => {
        child.userData.objectId = o.id;
      });
      node.userData.base = node.position.clone();
      root.add(node);
      objects.set(o.id, node);
      const label = document.createElement("span");
      label.className = "spatial-object-label";
      label.textContent = o.label;
      el.appendChild(label);
      labels.set(o.id, label);
    }
    const connections = [];
    for (const connection of spec.connections) {
      const a = objects.get(connection.source),
        b = objects.get(connection.target);
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([a.position, b.position]),
        new THREE.LineBasicMaterial({
          color: "#789b89",
          transparent: true,
          opacity: 0.6,
        }),
      );
      root.add(line);
      connections.push({ line, a, b, ...connection });
    }
    const ray = new THREE.Raycaster(),
      pointer = new THREE.Vector2();
    let down;
    const onDown = (e) => {
      down = [e.clientX, e.clientY];
    };
    const onPick = (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5)
        return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        (-(e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      ray.setFromCamera(pointer, camera);
      const hits = ray.intersectObjects(
        [...objects.values()].filter((o) => o.visible),
        true,
      );
      const id = hits.find((h) => h.object.userData.objectId)?.object.userData
        .objectId;
      if (id) callback.current(id);
    };
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onPick);
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame,
      disposed = false,
      start = performance.now(),
      elapsed = 0,
      last = performance.now(),
      previousStep = -1;
    const hasAnimations = spec.objects.some((o) => o.animation);
    function render() {
      if (disposed) return;
      const width = el.clientWidth,
        height = el.clientHeight;
      if (width < 2 || height < 2) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      const time = performance.now();
      if (state.current.playing && !reduced) elapsed += (time - last) / 1000;
      last = time;
      if (previousStep !== state.current.step) {
        previousStep = state.current.step;
        const s = spec.steps[previousStep];
        if (s?.camera) {
          camera.position.copy(vector(s.camera));
          const target = objects.get(s.object_ids[0]);
          if (target) controls.target.copy(target.position);
          controls.update();
        }
      }
      for (const o of spec.objects) {
        const node = objects.get(o.id);
        node.visible =
          !state.current.isolated || state.current.selected === o.id;
        node.traverse((child) => {
          if (child.material?.emissive)
            child.material.emissive.set(
              state.current.selected === o.id ? "#314c30" : "#000000",
            );
        });
        const a = o.animation;
        if (a && !reduced) {
          const phase = ((elapsed % a.duration) / a.duration) * 2 * Math.PI;
          if (a.kind === "rotate") node.rotation[a.axis] = phase;
          if (a.kind === "orbit") {
            const centre = vector(a.target),
              base = node.userData.base;
            node.position.set(
              centre.x + Math.cos(phase) * a.radius,
              base.y,
              centre.z + Math.sin(phase) * a.radius,
            );
          }
          if (a.kind === "translate")
            node.position
              .copy(node.userData.base)
              .lerp(vector(a.target), (Math.sin(phase) + 1) / 2);
          if (a.kind === "pulse")
            node.scale.setScalar(1 + 0.08 * Math.sin(phase));
        }
        const p = node.position.clone();
        p.y += o.dimensions.y / 2 + 0.3;
        p.project(camera);
        const label = labels.get(o.id);
        label.style.left = `${(p.x * 0.5 + 0.5) * width}px`;
        label.style.top = `${(-p.y * 0.5 + 0.5) * height}px`;
        label.hidden =
          !node.visible || p.z > 1 || Math.abs(p.x) > 1 || Math.abs(p.y) > 1;
      }
      for (const c of connections) {
        c.line.visible = !state.current.isolated;
        c.line.geometry.setFromPoints([c.a.position, c.b.position]);
      }
      renderer.render(scene, camera);
    }
    function loop() {
      render();
      frame = requestAnimationFrame(loop);
    }
    refresh.current = render;
    controls.addEventListener("change", render);
    const resize = new ResizeObserver(render);
    resize.observe(el);
    if (hasAnimations && !reduced) loop();
    else render();
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      refresh.current = null;
      resize.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onPick);
      scene.traverse((o) => {
        if (
          o instanceof THREE.Mesh ||
          o instanceof THREE.Line ||
          o instanceof THREE.Points
        ) {
          o.geometry.dispose();
          for (const material of Array.isArray(o.material)
            ? o.material
            : [o.material])
            material.dispose();
        }
      });
      renderer.dispose();
      el.replaceChildren();
    };
  }, [spec, resetKey]);
  return <div className="spatial-canvas" ref={host} />;
}
