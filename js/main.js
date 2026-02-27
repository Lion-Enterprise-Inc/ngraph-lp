// ===== Hero Canvas Animation =====
(function () {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w, h, particles = [];
  const CHARS = '01';
  const MAX_PARTICLES = 80;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }

  function createParticle() {
    return {
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: -Math.random() * 0.5 - 0.1,
      char: CHARS[Math.floor(Math.random() * CHARS.length)],
      alpha: Math.random() * 0.5 + 0.1,
      size: Math.random() * 12 + 10,
    };
  }

  function init() {
    resize();
    particles = [];
    for (let i = 0; i < MAX_PARTICLES; i++) particles.push(createParticle());
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    for (const p of particles) {
      ctx.fillStyle = `rgba(59,130,246,${p.alpha})`;
      ctx.font = `${p.size}px monospace`;
      ctx.fillText(p.char, p.x, p.y);
      p.x += p.vx;
      p.y += p.vy;
      if (p.y < -20 || p.x < -20 || p.x > w + 20) {
        p.x = Math.random() * w;
        p.y = h + 20;
        p.alpha = Math.random() * 0.5 + 0.1;
      }
    }
    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', resize);
  init();
  draw();
})();

// ===== Scroll Fade-In =====
(function () {
  const els = document.querySelectorAll('.fade-in');
  if (!els.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          observer.unobserve(e.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  els.forEach((el) => observer.observe(el));
})();

// ===== Counter Animation =====
(function () {
  const counters = document.querySelectorAll('.stat-value[data-target]');
  if (!counters.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        const el = e.target;
        const target = parseInt(el.dataset.target, 10);
        const duration = 1500;
        const start = performance.now();

        function update(now) {
          const progress = Math.min((now - start) / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          el.textContent = Math.round(eased * target).toLocaleString();
          if (progress < 1) requestAnimationFrame(update);
        }

        requestAnimationFrame(update);
        observer.unobserve(el);
      });
    },
    { threshold: 0.5 }
  );

  counters.forEach((el) => observer.observe(el));
})();

// ===== Hamburger Menu =====
(function () {
  const btn = document.querySelector('.hamburger');
  const nav = document.querySelector('.mobile-nav');
  if (!btn || !nav) return;

  btn.addEventListener('click', () => {
    btn.classList.toggle('active');
    nav.classList.toggle('active');
  });

  nav.querySelectorAll('a').forEach((a) => {
    a.addEventListener('click', () => {
      btn.classList.remove('active');
      nav.classList.remove('active');
    });
  });
})();

// ===== Smooth Scroll for anchor links =====
(function () {
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href');
      if (id === '#') return;
      const target = document.querySelector(id);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
})();

// ===== Form Submission =====
(function () {
  const form = document.getElementById('apply-form');
  if (!form) return;
  const status = document.getElementById('form-status');
  const btn = form.querySelector('.btn-submit');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    btn.disabled = true;
    btn.textContent = '送信中...';
    status.className = 'form-status';
    status.textContent = '';

    const data = Object.fromEntries(new FormData(form));

    try {
      const res = await fetch('/api/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (res.ok) {
        status.className = 'form-status success';
        status.textContent = '送信完了しました。担当者より折り返しご連絡いたします。';
        form.reset();
      } else {
        throw new Error('送信に失敗しました');
      }
    } catch (err) {
      status.className = 'form-status error';
      status.textContent = '送信に失敗しました。お手数ですが、info@ngraph.jp までメールでお問い合わせください。';
    } finally {
      btn.disabled = false;
      btn.textContent = '申込みを送信する';
    }
  });
})();