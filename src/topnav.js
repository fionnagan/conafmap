// ── TOP NAV — active section tracking + mobile menu ──────────────────────────
(function initTopNav() {
  const nav        = document.getElementById('topnav');
  const menuBtn    = document.getElementById('topnavMenuBtn');
  const mobileMenu = document.getElementById('topnavMobile');
  if (!nav) return;

  // ── Scrolled shadow ──────────────────────────────────────────────────────
  window.addEventListener('scroll', function () {
    nav.classList.toggle('scrolled', window.scrollY > 8);
  }, { passive: true });

  // ── Mobile menu toggle ───────────────────────────────────────────────────
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', function () {
      const open = mobileMenu.classList.toggle('open');
      menuBtn.innerHTML = open ? '&#10005;' : '&#9776;';
      menuBtn.setAttribute('aria-expanded', String(open));
      mobileMenu.setAttribute('aria-hidden', String(!open));
    });
    // Close on any link click
    mobileMenu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        mobileMenu.classList.remove('open');
        menuBtn.innerHTML = '&#9776;';
        menuBtn.setAttribute('aria-expanded', 'false');
        mobileMenu.setAttribute('aria-hidden', 'true');
      });
    });
  }

  // ── Active section tracking ──────────────────────────────────────────────
  const NAV_H = 60; // offset — nav height + a little breathing room
  const desktopLinks = Array.from(document.querySelectorAll('.topnav-link[data-section]'));
  const mobileLinks  = Array.from(document.querySelectorAll('.topnav-mobile-link[data-section]'));

  function getVisibleTop(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    // Skip sections hidden by JS (e.g. spotlight before data loads)
    if (el.style.display === 'none') return null;
    return el.getBoundingClientRect().top + window.scrollY;
  }

  function updateActive() {
    const y = window.scrollY + NAV_H;
    let activeId = desktopLinks.length ? desktopLinks[0].dataset.section : null;

    for (const link of desktopLinks) {
      const top = getVisibleTop(link.dataset.section);
      if (top !== null && top <= y) activeId = link.dataset.section;
    }

    desktopLinks.forEach(function (l) {
      l.classList.toggle('active', l.dataset.section === activeId);
    });
    mobileLinks.forEach(function (l) {
      l.classList.toggle('active', l.dataset.section === activeId);
    });
  }

  window.addEventListener('scroll', updateActive, { passive: true });
  // Re-check after spotlight section loads (it starts hidden)
  setTimeout(updateActive, 800);
  setTimeout(updateActive, 2000);
  updateActive();
})();
