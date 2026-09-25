/**
 * Lumina — campo de nodos 3D de fondo (<canvas id="field">). Puramente
 * decorativo. Opcional: si no hay canvas, no hace nada.
 */
(() => {
  const canvas = document.getElementById("field");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, dpr;
  let mouseX = 0,
    mouseY = 0,
    targetX = 0,
    targetY = 0;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  // Canvas 2D no lee custom properties de CSS: los colores van como RGB.
  // Luz de luna cerca (--moon), tinta apagada lejos (--ink-3): estrellas,
  // no una red de neón.
  const NODE_A = [191, 208, 253]; // cerca
  const NODE_B = [136, 146, 171]; // lejos

  // Densidad baja (la usa la cara: no debe competir con ella).
  const COUNT = 45;
  const LINE_ALPHA_SCALE = 0.45;
  const DOT_ALPHA_SCALE = 0.55;
  const LINE_ALPHA_BASE = 0.34;
  const DOT_FALLOFF = 0.35;
  const GLOW_BLUR = 4;

  const nodes = Array.from({ length: COUNT }, () => ({
    x: (Math.random() - 0.5) * 2400,
    y: (Math.random() - 0.5) * 1600,
    z: Math.random() * 1000 + 60,
    r: Math.random() * 1.6 + 0.6,
  }));

  if (!reduceMotion) {
    window.addEventListener("mousemove", (e) => {
      targetX = e.clientX / w - 0.5;
      targetY = e.clientY / h - 0.5;
    });
  }

  function lerpColor(t) {
    const c = NODE_A.map((v, i) => Math.round(v + (NODE_B[i] - v) * t));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  function project(ts) {
    if (!reduceMotion) {
      mouseX += (targetX - mouseX) * 0.04;
      mouseY += (targetY - mouseY) * 0.04;
    }
    const cx = w / 2;
    const cy = h / 2;
    const drift = reduceMotion ? 0 : ts * 0.00002;

    return nodes.map((n) => {
      const depth = n.z;
      const parX = n.x + mouseX * depth * 0.25 + Math.sin(drift + n.z) * 6;
      const parY = n.y + mouseY * depth * 0.25 + Math.cos(drift + n.z) * 6;
      const scale = 500 / (500 + depth);
      return {
        sx: cx + parX * scale,
        sy: cy + parY * scale,
        r: n.r * scale * 2.4,
        t: Math.min(depth / 1000, 1),
      };
    });
  }

  function renderFrame(ts) {
    ctx.clearRect(0, 0, w, h);
    const projected = project(ts || 0);

    ctx.lineWidth = 0.8;
    for (let i = 0; i < projected.length; i++) {
      for (let j = i + 1; j < projected.length; j++) {
        const p1 = projected[i];
        const p2 = projected[j];
        const dist = Math.hypot(p1.sx - p2.sx, p1.sy - p2.sy);
        if (dist < 110) {
          const alpha = (1 - dist / 110) * LINE_ALPHA_BASE * LINE_ALPHA_SCALE;
          ctx.strokeStyle = `rgba(191,208,253,${alpha})`;
          ctx.beginPath();
          ctx.moveTo(p1.sx, p1.sy);
          ctx.lineTo(p2.sx, p2.sy);
          ctx.stroke();
        }
      }
    }

    projected.forEach((p) => {
      const color = lerpColor(p.t);
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = GLOW_BLUR;
      ctx.globalAlpha = (1 - p.t * DOT_FALLOFF) * DOT_ALPHA_SCALE;
      ctx.arc(p.sx, p.sy, Math.max(p.r, 0.6), 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    });
    ctx.shadowBlur = 0;
  }

  if (reduceMotion) {
    renderFrame(0); // un solo cuadro estático
    return;
  }

  // Solo se anima con la cara a la vista y la pestaña visible: con la
  // consola abierta el canvas queda oculto y no hay por qué gastar batería.
  let rafId = null;
  const loop = (ts) => {
    renderFrame(ts);
    rafId = requestAnimationFrame(loop);
  };
  function syncLoop() {
    const visible = !document.hidden && document.documentElement.dataset.view !== "dashboard";
    if (visible && rafId === null) rafId = requestAnimationFrame(loop);
    if (!visible && rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }
  document.addEventListener("visibilitychange", syncLoop);
  document.addEventListener("viewchange", syncLoop);
  syncLoop();
})();
