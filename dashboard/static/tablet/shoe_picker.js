(function () {
    const p = new URLSearchParams(location.search);
    if (p.get("title"))
      document.getElementById("title-el").textContent = p.get("title");
    if (p.get("subtitle"))
      document.getElementById("subtitle-el").textContent = p.get("subtitle");

    let items = [];
    try {
      items = JSON.parse(p.get("items") || "[]");
    } catch (e) {
      items = [];
    }
  
    const grid = document.getElementById("card-grid");
  
    items.forEach((item, idx) => {
      const card = document.createElement("div");
      card.className = "shoe-card";
      card.setAttribute("tabindex", "0");
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `${item.color} ${item.type}`);
  
      const sizes = (item.sizes || []).join(", ");
      card.innerHTML = `
        <div class="shoe-title">${item.color} ${item.type}</div>
        <div class="shoe-meta">Sizes: ${sizes}</div>
        <div class="shoe-price">€${item.price}</div>
      `;
  
      card.addEventListener("click", () => handleChoice(card, item, idx));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") handleChoice(card, item, idx);
      });
      grid.appendChild(card);
    });
  
    if (items.length === 0) {
      grid.innerHTML = '<p style="opacity:.7;padding:2rem">No items to show.</p>';
    }
  
    let busy = false;
  
    function handleChoice(card, item, index) {
      if (busy) return;
      busy = true;
      card.classList.add("selected");
  
      const payload = { action: "shoe_choice", value: item.id, index };
  
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
        `${item.color} ${item.type} selected!`;
      fb.classList.add("show");
  
      setTimeout(() => {
        fb.classList.remove("show");
        card.classList.remove("selected");
        busy = false;
      }, 1500);
    }
  })();