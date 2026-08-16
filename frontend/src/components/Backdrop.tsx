'use client';

import { useEffect, useRef } from 'react';

/**
 * Sahifa orqa foni: harakatlanuvchi 3D zarralar to'ri.
 *
 * NEGA KUTUBXONASIZ (three.js emas):
 *
 *   three.js siqilgan holda ~600 KB. Bu FON uchun — foydalanuvchi
 *   hatto qaramaydigan narsa uchun juda katta narx: sayt sekin
 *   ochilardi, mobil internetda esa ayniqsa. Bu yerdagi effekt
 *   oddiy perspektiva formulasi bilan chiziladi (`fov / z`) va
 *   hech qanday bog'liqlik talab qilmaydi.
 *
 * TEZLIKNI SAQLAYDIGAN QARORLAR:
 *
 *   * Varaq ko'rinmasa animatsiya TO'XTAYDI. Fon uchun batareyani
 *     yeyish ma'nosiz.
 *   * `prefers-reduced-motion` yoqilgan bo'lsa harakat umuman yo'q —
 *     bu tanlovni harakatdan boshi aylanadigan odamlar qo'yadi.
 *   * Kichik ekranda zarra soni kamayadi.
 *   * Chizish `alpha` bilan bitta canvasda, soya va blur yo'q —
 *     ular har kadrda qayta hisoblanadi va eng qimmat amal.
 */

/** Zarra soni: kenglikka qarab. Katta ekranda ko'proq, telefonda kam. */
function particleCount(width: number): number {
  if (width < 640) return 45;
  if (width < 1280) return 80;
  return 120;
}

/** Perspektiva kuchi. Kattaroq qiymat — chuqurroq ko'rinish. */
const FOV = 260;

/** Zarra shu chuqurlikdan o'tsa boshiga qaytariladi. */
const DEPTH = 900;

type Particle = { x: number; y: number; z: number; r: number };

export function Backdrop() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let particles: Particle[] = [];
    let width = 0;
    let height = 0;
    let frame = 0;

    // Sichqoncha ozgina qiyshaytiradi — harakat tirik ko'rinadi,
    // lekin diqqatni tortmaydi.
    let tiltX = 0;
    let tiltY = 0;
    let targetX = 0;
    let targetY = 0;

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      particles = Array.from({ length: particleCount(width) }, () => ({
        x: (Math.random() - 0.5) * width * 1.6,
        y: (Math.random() - 0.5) * height * 1.6,
        z: Math.random() * DEPTH,
        r: 0.6 + Math.random() * 1.6,
      }));
    }

    function onPointer(event: PointerEvent) {
      targetX = (event.clientX / width - 0.5) * 40;
      targetY = (event.clientY / height - 0.5) * 40;
    }

    function draw() {
      ctx!.clearRect(0, 0, width, height);

      tiltX += (targetX - tiltX) * 0.04;
      tiltY += (targetY - tiltY) * 0.04;

      const centerX = width / 2;
      const centerY = height / 2;

      // Yaqinroq zarralar keyin chizilsin — ustma-ust tushganda
      // yaqinrog'i ko'rinadi.
      const sorted = [...particles].sort((a, b) => b.z - a.z);

      for (const p of sorted) {
        if (!reduced) {
          p.z -= 0.55;
          if (p.z < 1) {
            p.z = DEPTH;
            p.x = (Math.random() - 0.5) * width * 1.6;
            p.y = (Math.random() - 0.5) * height * 1.6;
          }
        }

        const scale = FOV / p.z;
        const sx = centerX + (p.x + tiltX * (p.z / DEPTH) * 8) * scale;
        const sy = centerY + (p.y + tiltY * (p.z / DEPTH) * 8) * scale;

        if (sx < -50 || sx > width + 50 || sy < -50 || sy > height + 50) continue;

        // Uzoqdagi zarra xira va mayda: chuqurlik shundan sezilaydi.
        const depth = 1 - p.z / DEPTH;
        const alpha = 0.06 + depth * 0.42;
        const radius = Math.max(0.4, p.r * scale * 0.9);

        // Rang chuqurlikka qarab ko'kdan feruzaga o'tadi
        const g = Math.round(165 + depth * 40);
        const b = Math.round(233 - depth * 40);
        ctx!.fillStyle = `rgba(14, ${g}, ${b}, ${alpha})`;
        ctx!.beginPath();
        ctx!.arc(sx, sy, radius, 0, Math.PI * 2);
        ctx!.fill();
      }

      frame = requestAnimationFrame(draw);
    }

    function start() {
      if (!frame) frame = requestAnimationFrame(draw);
    }

    function stop() {
      if (frame) {
        cancelAnimationFrame(frame);
        frame = 0;
      }
    }

    function onVisibility() {
      // Varaq ko'rinmasa fon uchun batareya sarflashning ma'nosi yo'q
      if (document.hidden) stop();
      else start();
    }

    resize();
    start();

    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onPointer);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return (
    <div className="backdrop" aria-hidden="true">
      {/*
        Ikki qatlam: pastda rangli "aurora" dog'lari (CSS bilan
        harakatlanadi, protsessorga tegmaydi), ustida 3D zarralar.
        Faqat zarralar bo'lsa fon quruq, faqat dog'lar bo'lsa
        chuqurlik sezilmasdi.
      */}
      <div className="aurora aurora-1" />
      <div className="aurora aurora-2" />
      <div className="aurora aurora-3" />
      <canvas ref={canvasRef} className="backdrop-canvas" />
      <div className="backdrop-grid" />
    </div>
  );
}
