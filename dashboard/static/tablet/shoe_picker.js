// shoe_picker.js — picker grid, detail view, and confirmation.

(function () {
  // ──────────────────────────────────────────────────────────
  //  Read items from URL params
  // ──────────────────────────────────────────────────────────
  const p = new URLSearchParams(location.search);
  let items = [];
  try { items = JSON.parse(p.get("items") || "[]"); } catch (e) { items = []; }

  // ──────────────────────────────────────────────────────────
  //  Build the grid
  // ──────────────────────────────────────────────────────────
  const grid = document.getElementById("card-grid");

  function imageFor(item) {
    return item.image ? item.image : `img/shoes/${item.id}.jpg`;
  }

  items.forEach((item, idx) => {
    const card = document.createElement("div");
    card.className = "shoe-card";
    card.setAttribute("tabindex", "0");
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${item.color} ${item.type}`);

    const sizes = (item.sizes || []).join(", ");
    card.innerHTML = `
      <img class="shoe-card-image" src="${imageFor(item)}" alt="${item.color} ${item.type}"
           onerror="this.style.opacity=0.3; this.alt='No image';">
      <div class="shoe-card-body">
        <div class="shoe-title">${item.color} ${item.type}</div>
        <div class="shoe-meta">Sizes: ${sizes}</div>
        <div class="shoe-price">€${item.price}</div>
      </div>
    `;

    card.addEventListener("click",   () => showDetail(item, idx));
    card.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") showDetail(item, idx);
    });
    grid.appendChild(card);
  });

  if (items.length === 0) {
    grid.innerHTML = '<p style="opacity:.7;padding:2rem">No items to show.</p>';
  }

  // ──────────────────────────────────────────────────────────
  //  Detail view
  // ──────────────────────────────────────────────────────────
  const gridView   = document.getElementById("grid-view");
  const detailView = document.getElementById("detail-view");
  const detailImg  = document.getElementById("detail-image");
  const detailTitle = document.getElementById("detail-title");
  const detailMeta  = document.getElementById("detail-meta");
  const detailPrice = document.getElementById("detail-price");
  const backBtn    = document.getElementById("back-btn");
  const confirmBtn = document.getElementById("confirm-btn");

  let currentItem  = null;
  let currentIndex = -1;

  function showDetail(item, idx) {
    currentItem  = item;
    currentIndex = idx;

    detailImg.src = imageFor(item);
    detailImg.alt = `${item.color} ${item.type}`;
    detailImg.onerror = () => {
      detailImg.style.opacity = 0.3;
      detailImg.alt = "No image available";
    };

    detailTitle.textContent = `${capitalize(item.color)} ${item.type}`;
    detailMeta.textContent  = `Available sizes: ${(item.sizes || []).join(", ")}`;
    detailPrice.textContent = `€${item.price}`;

    gridView.classList.add("hidden");
    detailView.classList.remove("hidden");
  }

  function hideDetail() {
    detailView.classList.add("hidden");
    gridView.classList.remove("hidden");
    currentItem = null;
    currentIndex = -1;
  }

  backBtn.addEventListener("click", hideDetail);

  // ──────────────────────────────────────────────────────────
  //  Confirm: send the choice to the robot
  // ──────────────────────────────────────────────────────────
  let busy = false;
  confirmBtn.addEventListener("click", () => {
    if (busy || !currentItem) return;
    busy = true;

    const payload = {
      action: "shoe_choice",
      value:  currentItem.id,
      index:  currentIndex,
    };

    try {
      const qs = new QiSession();
      qs.service("TabletInput")
        .then((m) => m.notify(JSON.stringify(payload)))
        .catch(() => {});
    } catch (_e) {}

    fetch("/api/tablet_input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});

    const fb = document.getElementById("feedback");
    document.getElementById("fb-text").textContent =
      `${currentItem.color} ${currentItem.type} selected!`;
    fb.classList.add("show");

    // Stay on the confirmation flash for 1.5s, then reset for next session.
    setTimeout(() => {
      fb.classList.remove("show");
      busy = false;
    }, 1500);
  });

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }
})();