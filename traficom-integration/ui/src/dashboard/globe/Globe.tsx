/**
 * Interactive 3D Earth centred on Finland, with the flagged space and terrestrial notices.
 * three.js is loaded on demand (its own chunk), the Earth texture is painted from bundled
 * Natural Earth outlines (no image download), and rendering pauses when the view is hidden.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import land from "./land.json";
import { FINLAND, ISSUE, toVector, type GlobeMarker } from "./globeData";

type Hover = { marker: GlobeMarker; x: number; y: number } | null;

export function webglAvailable(): boolean {
  if (typeof window === "undefined" || typeof WebGLRenderingContext === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function paintEarth(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;
  const ocean = ctx.createLinearGradient(0, 0, 0, height);
  ocean.addColorStop(0, "#0b1d33");
  ocean.addColorStop(0.5, "#0d2440");
  ocean.addColorStop(1, "#0b1d33");
  ctx.fillStyle = ocean;
  ctx.fillRect(0, 0, width, height);
  const x = (lon: number) => ((lon + 180) / 360) * width;
  const y = (lat: number) => ((90 - lat) / 180) * height;
  ctx.strokeStyle = "rgba(120,160,200,0.10)";
  ctx.lineWidth = 1;
  for (let lon = -180; lon <= 180; lon += 30) {
    ctx.beginPath();
    ctx.moveTo(x(lon), 0);
    ctx.lineTo(x(lon), height);
    ctx.stroke();
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    ctx.beginPath();
    ctx.moveTo(0, y(lat));
    ctx.lineTo(width, y(lat));
    ctx.stroke();
  }
  const ring = (points: number[][]) => {
    ctx.beginPath();
    points.forEach(([lon, lat], i) => (i === 0 ? ctx.moveTo(x(lon!), y(lat!)) : ctx.lineTo(x(lon!), y(lat!))));
    ctx.closePath();
  };
  ctx.fillStyle = "#2b4663";
  ctx.strokeStyle = "#5a7fa3";
  ctx.lineWidth = 1.2;
  for (const points of land.land) {
    ring(points);
    ctx.fill();
    ctx.stroke();
  }
  ctx.fillStyle = "rgba(56,189,248,0.35)";
  ctx.strokeStyle = "#7dd3fc";
  ctx.lineWidth = 2.5;
  for (const points of land.finland) {
    ring(points);
    ctx.fill();
    ctx.stroke();
  }
  return canvas;
}

function iconTexture(kind: "space" | "terrestrial"): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "#ffffff";
  if (kind === "space") {
    ctx.fillRect(26, 24, 12, 16); // body
    ctx.fillRect(4, 28, 18, 8); // panels
    ctx.fillRect(42, 28, 18, 8);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(32, 24);
    ctx.lineTo(32, 14);
    ctx.stroke();
  } else {
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(32, 10);
    ctx.lineTo(20, 56);
    ctx.moveTo(32, 10);
    ctx.lineTo(44, 56);
    ctx.moveTo(24, 40);
    ctx.lineTo(40, 40);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(32, 10, 6, 0, Math.PI * 2);
    ctx.fill();
  }
  return canvas;
}

export function Globe({ markers }: { markers: GlobeMarker[] }) {
  const host = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [hover, setHover] = useState<Hover>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">(webglAvailable() ? "loading" : "unavailable");

  useEffect(() => {
    if (status === "unavailable" || !host.current) return undefined;
    const element = host.current;
    let disposed = false;
    let cleanup = () => {};
    void (async () => {
      const THREE = await import("three");
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      if (disposed) return;
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(element.clientWidth, element.clientHeight);
      element.appendChild(renderer.domElement);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(34, element.clientWidth / element.clientHeight, 0.1, 100);
      const [fx, fy, fz] = toVector(36, FINLAND.lon, 4.5);
      camera.position.set(fx, fy, fz);
      camera.lookAt(0, 0, 0);

      scene.add(new THREE.AmbientLight(0xffffff, 1.1));
      const sun = new THREE.DirectionalLight(0xffffff, 1.3);
      sun.position.set(fx + 2, fy + 3, fz);
      scene.add(sun);

      const texture = new THREE.CanvasTexture(paintEarth(2048, 1024));
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = 4;
      const earth = new THREE.Mesh(
        new THREE.SphereGeometry(1, 72, 48),
        new THREE.MeshPhongMaterial({ map: texture, shininess: 8 }),
      );
      scene.add(earth);
      const atmosphere = new THREE.Mesh(
        new THREE.SphereGeometry(1.06, 48, 32),
        new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.08, side: THREE.BackSide }),
      );
      scene.add(atmosphere);

      const starPositions = new Float32Array(900 * 3);
      for (let i = 0; i < starPositions.length; i += 1) starPositions[i] = (Math.random() - 0.5) * 60;
      const stars = new THREE.BufferGeometry();
      stars.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
      scene.add(new THREE.Points(stars, new THREE.PointsMaterial({ color: 0x8aa4c0, size: 0.05 })));

      const icons = {
        space: new THREE.CanvasTexture(iconTexture("space")),
        terrestrial: new THREE.CanvasTexture(iconTexture("terrestrial")),
      };
      const finland = new THREE.Vector3(...toVector(FINLAND.lat, FINLAND.lon, 1.01));
      const sprites: InstanceType<typeof THREE.Sprite>[] = [];
      const disposables: { dispose: () => void }[] = [texture, icons.space, icons.terrestrial, stars];
      for (const marker of markers) {
        const position = new THREE.Vector3(...toVector(marker.lat, marker.lon, marker.radius));
        const material = new THREE.SpriteMaterial({ map: icons[marker.kind], color: marker.color, depthWrite: false });
        const sprite = new THREE.Sprite(material);
        const size = marker.kind === "space" ? 0.1 : 0.06;
        sprite.scale.set(size, size, 1);
        sprite.position.copy(position);
        sprite.userData = { marker, size };
        scene.add(sprite);
        sprites.push(sprite);
        disposables.push(material);
        // Arc from the notice to Finland, lifted above the surface.
        const mid = position.clone().add(finland).multiplyScalar(0.5);
        mid.setLength(Math.max(position.length(), 1.05) + position.distanceTo(finland) * 0.25);
        const curve = new THREE.QuadraticBezierCurve3(position, mid, finland);
        const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(32));
        const line = new THREE.Line(
          geometry,
          new THREE.LineBasicMaterial({ color: marker.color, transparent: true, opacity: 0.28 }),
        );
        scene.add(line);
        disposables.push(geometry, line.material as { dispose: () => void });
      }

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.enablePan = false;
      controls.minDistance = 1.6;
      controls.maxDistance = 8;
      controls.rotateSpeed = 0.5;
      controls.zoomSpeed = 0.6;

      const raycaster = new THREE.Raycaster();
      const pointer = new THREE.Vector2();
      let hovered: InstanceType<typeof THREE.Sprite> | null = null;
      const pick = (event: PointerEvent) => {
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObjects(sprites, false)[0];
        return { hit: hit?.object as InstanceType<typeof THREE.Sprite> | undefined, rect };
      };
      const onMove = (event: PointerEvent) => {
        const { hit, rect } = pick(event);
        if (hovered && hovered !== hit) {
          const s = hovered.userData.size as number;
          hovered.scale.set(s, s, 1);
        }
        hovered = hit ?? null;
        if (hit) {
          const s = (hit.userData.size as number) * 1.6;
          hit.scale.set(s, s, 1);
          renderer.domElement.style.cursor = "pointer";
          setHover({ marker: hit.userData.marker as GlobeMarker, x: event.clientX - rect.left, y: event.clientY - rect.top });
        } else {
          renderer.domElement.style.cursor = "grab";
          setHover(null);
        }
      };
      const onClick = (event: PointerEvent) => {
        const { hit } = pick(event);
        if (!hit) return;
        const marker = hit.userData.marker as GlobeMarker;
        navigate(marker.caseId ? `/cases/${encodeURIComponent(marker.caseId)}` : "/ific");
      };
      const onLeave = () => setHover(null);
      renderer.domElement.addEventListener("pointermove", onMove);
      renderer.domElement.addEventListener("click", onClick as EventListener);
      renderer.domElement.addEventListener("pointerleave", onLeave);

      let visible = true;
      const observer = new IntersectionObserver(([entry]) => {
        visible = Boolean(entry?.isIntersecting);
      });
      observer.observe(element);
      const resize = new ResizeObserver(() => {
        camera.aspect = element.clientWidth / Math.max(element.clientHeight, 1);
        camera.updateProjectionMatrix();
        renderer.setSize(element.clientWidth, element.clientHeight);
      });
      resize.observe(element);

      let frame = 0;
      let first = true;
      const loop = () => {
        frame = requestAnimationFrame(loop);
        if (!visible || document.hidden) return;
        controls.update();
        renderer.render(scene, camera);
        if (first) {
          first = false;
          setStatus("ready");
        }
      };
      loop();

      cleanup = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        resize.disconnect();
        controls.dispose();
        renderer.domElement.removeEventListener("pointermove", onMove);
        renderer.domElement.removeEventListener("click", onClick as EventListener);
        renderer.domElement.removeEventListener("pointerleave", onLeave);
        disposables.forEach((d) => d.dispose());
        earth.geometry.dispose();
        atmosphere.geometry.dispose();
        renderer.dispose();
        renderer.domElement.remove();
      };
    })().catch(() => setStatus("unavailable"));
    return () => {
      disposed = true;
      cleanup();
    };
  }, [markers, navigate, status === "unavailable"]); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = Object.entries(
    markers.reduce<Record<string, number>>((acc, m) => ({ ...acc, [m.classification]: (acc[m.classification] ?? 0) + 1 }), {}),
  );

  return (
    <section className="globe-section" aria-label="Flagged satellite and terrestrial notices around Finland">
      <div className="globe-canvas" ref={host} />
      <div className="globe-title">
        <h2>Live satellite and terrestrial screening</h2>
        <p className="small muted">
          {markers.filter((m) => m.kind === "space").length} space and{" "}
          {markers.filter((m) => m.kind === "terrestrial").length} terrestrial notices flagged around Finland
        </p>
      </div>
      <ul className="globe-legend plain" aria-label="Legend">
        {counts.map(([key, count]) => (
          <li key={key}>
            <span className="globe-dot" style={{ background: ISSUE[key]!.color }} aria-hidden="true" />
            {ISSUE[key]!.text} <span className="muted">({count})</span>
          </li>
        ))}
      </ul>
      <p className="globe-hint small muted">
        {status === "ready" && "Drag to rotate, scroll to zoom, click a notice to open it. GSO at nominal longitude; non-GSO positions illustrative."}
        {status === "loading" && "Loading the 3D view…"}
        {status === "unavailable" && "3D view unavailable in this browser; the KPIs and lists below show the same data."}
      </p>
      {hover && (
        <div
          className="globe-card"
          role="tooltip"
          style={{ left: hover.x + 14, top: hover.y + 14, borderLeftColor: hover.marker.color }}
        >
          <strong>{hover.marker.label}</strong>
          <span className="small muted">
            {hover.marker.kind === "space" ? "Space notice" : "Terrestrial station"} · {hover.marker.administration} · {hover.marker.frequency}
          </span>
          <span style={{ color: hover.marker.color }}>{hover.marker.issue}</span>
          {hover.marker.margin !== null && <span className="small">Margin {hover.marker.margin.toFixed(1)} dB</span>}
          {hover.marker.illustrative && <span className="small muted">Illustrative position (non-GSO)</span>}
          <span className="small muted">{hover.marker.caseId ? "Click to open the case" : "Click to open IFIC findings"}</span>
        </div>
      )}
    </section>
  );
}
