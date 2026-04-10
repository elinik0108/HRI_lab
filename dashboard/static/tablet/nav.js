/**
 * Pepper Tablet — Page-navigation dropdown
 *
 * Include this script at the bottom of any tablet page:
 *   <script src="nav.js"></script>
 *
 * A ☰ icon appears in the top-right corner.  Tapping it reveals a drawer
 * with links to every standard tablet page, preserving all current URL
 * parameters (so ?color=... theming carries through).
 *
 * The nav resolves URLs relative to the current page's origin so it works
 * whether the page is served from the laptop or deployed to the robot.
 */
(function () {
  "use strict";

  const PAGES = [
    { id: "welcome",   label: "👋  Welcome",   icon: "👋", file: "welcome.html"   },
    { id: "menu",      label: "📋  Menu",       icon: "📋", file: "menu_demo.html" },
    { id: "listening", label: "🎙  Listening",  icon: "🎙", file: "listening.html" },
    { id: "question",  label: "❓  Question",   icon: "❓", file: "question.html"  },
    { id: "answer",    label: "💬  Answer",     icon: "💬", file: "answer.html"    },
    { id: "info",      label: "ℹ️  Info",        icon: "ℹ️", file: "info.html"      },
  ];

  // Inject styles
  const style = document.createElement("style");
  style.textContent = `
    #_nav-toggle {
      position: fixed;
      top: 1rem; right: 1rem;
      z-index: 1000;
      background: rgba(30,40,56,.85);
      backdrop-filter: blur(6px);
      border: 1px solid rgba(255,255,255,.15);
      border-radius: .75rem;
      width: clamp(2.8rem, 8vw, 4rem);
      height: clamp(2.8rem, 8vw, 4rem);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer;
      font-size: clamp(1.2rem, 3.5vw, 1.8rem);
      transition: background .15s;
    }
    #_nav-toggle:hover { background: rgba(88,166,255,.35); }

    #_nav-drawer {
      position: fixed;
      top: 0; right: 0;
      width: clamp(220px, 55vw, 340px);
      height: 100%;
      z-index: 999;
      background: rgba(13,17,23,.96);
      backdrop-filter: blur(12px);
      border-left: 1px solid rgba(255,255,255,.1);
      transform: translateX(100%);
      transition: transform .22s cubic-bezier(.4,0,.2,1);
      display: flex; flex-direction: column;
      padding: 1.2rem .8rem;
      gap: .4rem;
      overflow-y: auto;
    }
    #_nav-drawer.open { transform: translateX(0); }

    #_nav-drawer h3 {
      color: #8b949e;
      font-size: clamp(.75rem, 2vw, 1rem);
      font-weight: 700;
      letter-spacing: .1em;
      text-transform: uppercase;
      padding: .4rem .8rem .8rem;
      border-bottom: 1px solid rgba(255,255,255,.08);
      margin-bottom: .2rem;
    }

    .nav-item {
      display: block;
      padding: .85em 1.1em;
      border-radius: .65rem;
      color: #e6edf3;
      text-decoration: none;
      font-size: clamp(1rem, 2.8vw, 1.4rem);
      font-weight: 500;
      transition: background .14s;
      border: 1px solid transparent;
    }
    .nav-item:hover { background: rgba(88,166,255,.18); border-color: rgba(88,166,255,.3); }
    .nav-item.active { background: rgba(88,166,255,.28); border-color: rgba(88,166,255,.55); color: #58a6ff; }

    #_nav-backdrop {
      display: none;
      position: fixed; inset: 0;
      z-index: 998;
      background: rgba(0,0,0,.45);
    }
    #_nav-backdrop.open { display: block; }
  `;
  document.head.appendChild(style);

  // Build markup
  const toggle   = document.createElement("div");
  toggle.id      = "_nav-toggle";
  toggle.innerHTML = "☰";
  toggle.setAttribute("role", "button");
  toggle.setAttribute("aria-label", "Navigation menu");

  const backdrop  = document.createElement("div");
  backdrop.id     = "_nav-backdrop";

  const drawer    = document.createElement("div");
  drawer.id       = "_nav-drawer";
  drawer.setAttribute("role", "navigation");

  const heading   = document.createElement("h3");
  heading.textContent = "Tablet Pages";
  drawer.appendChild(heading);

  // Current page filename for active highlight
  const currentFile = location.pathname.split("/").pop() || "";
  // Carry over any params the caller set (e.g. ?color=...)
  const baseParams = new URLSearchParams(location.search);

  PAGES.forEach(({ label, file }) => {
    const a = document.createElement("a");
    a.className = "nav-item";
    a.textContent = label;
    // Build URL relative to current page (same directory — avoids new URL() API)
    const base = location.href.replace(/\/[^/]*(\?.*)?$/, "/");
    const extras = [];
    for (const key of ["color", "accent"]) {
      const val = baseParams.get(key);
      if (val !== null) extras.push(key + "=" + encodeURIComponent(val));
    }
    a.href = base + file + (extras.length ? "?" + extras.join("&") : "");
    if (file === currentFile) a.classList.add("active");
    drawer.appendChild(a);
  });

  document.body.appendChild(toggle);
  document.body.appendChild(backdrop);
  document.body.appendChild(drawer);

  function openDrawer()  { drawer.classList.add("open"); backdrop.classList.add("open"); }
  function closeDrawer() { drawer.classList.remove("open"); backdrop.classList.remove("open"); }

  toggle.addEventListener("click", () =>
    drawer.classList.contains("open") ? closeDrawer() : openDrawer()
  );
  backdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });
})();
