/**
 * Mini App «Бро Кколи» — id товаров = catalog.MINI_APP_PRODUCT_IDS в боте.
 * Открывайте через reply-кнопку «Магазин», иначе sendData недоступен.
 *
 * --- Свои картинки ---
 * Положите файлы в папку web/images/ рядом с index.html:
 *   images/logo.png          — логотип (квадрат ~256×256, PNG или JPG)
 *   images/products/<id>.jpg — фото товара; <id> как в поле id ниже (например buckwheat_chicken.jpg)
 * Если файла нет, покажется эмодзи из поля emoji.
 *
 * Промокод «Применить»: код сохраняется и проверяется ботом при оформлении (БД).
 * web/promos.json и PROMO_CODES — по желанию, только чтобы показать процент скидки в корзине до отправки.
 */

const PRODUCTS = [
  {
    id: "buckwheat_chicken",
    title: "Гречка с курицей",
    emoji: "🍲",
    price: 350,
    image: "images/products/buckwheat_chicken.jpg",
  },
  {
    id: "rice_chicken",
    title: "Рис с курицей",
    emoji: "🍛",
    price: 350,
    image: "images/products/rice_chicken.jpg",
  },
  {
    id: "beef_buckwheat",
    title: "Гречка с говядиной",
    emoji: "🥩",
    price: 350,
    image: "images/products/beef_buckwheat.jpg",
  },
];

/** Слайды: лёгкий светлый тон поверх фото (слабый градиент) */
const BANNERS_LIGHT = [
  {
    image: "images/banner-1.jpg",
    bg: "linear-gradient(145deg,rgba(240,253,244,0.75) 0%,rgba(220,252,231,0.5) 50%,rgba(187,247,208,0.25) 100%)",
  },
  {
    image: "images/banner-2.jpg",
    bg: "linear-gradient(145deg,rgba(236,253,245,0.7) 0%,rgba(209,250,229,0.35) 100%)",
  },
  {
    image: "images/banner-3.jpg",
    bg: "linear-gradient(145deg,rgba(240,253,244,0.65) 0%,rgba(167,243,208,0.22) 100%)",
  },
];

const BANNERS_DARK = [
  {
    image: "images/banner-1.jpg",
    bg: "linear-gradient(145deg,rgba(147,201,78,0.14) 0%,rgba(60,70,55,0.12) 50%,rgba(25,28,24,0.1) 100%)",
  },
  {
    image: "images/banner-2.jpg",
    bg: "linear-gradient(145deg,rgba(130,190,70,0.12) 0%,rgba(45,52,42,0.1) 100%)",
  },
  {
    image: "images/banner-3.jpg",
    bg: "linear-gradient(145deg,rgba(147,201,78,0.1) 0%,rgba(55,62,50,0.08) 100%)",
  },
];

const LOGO_IMAGE = "images/logo.png";

const CART_KEY = "broccoli_cart_v1";
const THEME_KEY = "broccoli_theme";
const PROMO_KEY = "broccoli_promo_v1";

/** Дублируйте сюда коды из бота или правьте promos.json при деплое */
const PROMO_CODES = {};

let MERGED_PROMOS = {};

let appliedPromo = null;

function loadAppliedPromoState() {
  try {
    const raw = localStorage.getItem(PROMO_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw);
    if (o && typeof o.code === "string" && typeof o.discount === "number") return o;
  } catch {
    return null;
  }
  return null;
}

function saveAppliedPromo() {
  if (!appliedPromo) localStorage.removeItem(PROMO_KEY);
  else localStorage.setItem(PROMO_KEY, JSON.stringify(appliedPromo));
}

const tg = window.Telegram && window.Telegram.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

let sliderIntervalId = null;

function getTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function applyTelegramChrome() {
  if (!tg) return;
  const dark = getTheme() === "dark";
  if (tg.setHeaderColor) tg.setHeaderColor(dark ? "#0a0a0a" : "#ffffff");
  if (tg.setBackgroundColor) tg.setBackgroundColor(dark ? "#0a0a0a" : "#f4f7f4");
}

function initTheme() {
  let t = localStorage.getItem(THEME_KEY);
  if (t !== "light" && t !== "dark") {
    t = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", t);
  applyTelegramChrome();
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.setAttribute(
      "aria-label",
      t === "dark" ? "Светлая тема" : "Тёмная тема",
    );
  }
}

function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  document.documentElement.setAttribute("data-theme", next);
  applyTelegramChrome();
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.setAttribute(
      "aria-label",
      next === "dark" ? "Светлая тема" : "Тёмная тема",
    );
  }
  rebuildSlider();
}

function rebuildSlider() {
  const track = document.getElementById("slider-track");
  const dots = document.getElementById("slider-dots");
  if (!track || !dots) return;
  if (sliderIntervalId) {
    clearInterval(sliderIntervalId);
    sliderIntervalId = null;
  }
  track.innerHTML = "";
  dots.innerHTML = "";
  initSlider();
}

function initLogo() {
  const img = document.getElementById("logo-image");
  const fallback = document.getElementById("logo-emoji");
  if (!img || !fallback) return;
  img.src = LOGO_IMAGE;
  img.addEventListener("error", () => {
    img.hidden = true;
    fallback.hidden = false;
  });
  img.addEventListener("load", () => {
    if (img.naturalWidth > 0) {
      fallback.hidden = true;
    }
  });
}

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function cartCount(cart) {
  return Object.values(cart).reduce((s, q) => s + Number(q || 0), 0);
}

function updateBadge() {
  const cart = loadCart();
  const n = cartCount(cart);
  const el = document.getElementById("cart-badge");
  if (!el) return;
  el.textContent = n;
  el.style.display = n > 0 ? "flex" : "none";
}

function mergeRemotePromos() {
  MERGED_PROMOS = { ...PROMO_CODES };
  return fetch("promos.json?v=11", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .then((j) => {
      if (j && typeof j === "object" && !Array.isArray(j)) {
        for (const [k, v] of Object.entries(j)) {
          const n = Number(v);
          if (Number.isFinite(n) && n > 0 && n <= 100) {
            MERGED_PROMOS[String(k).toUpperCase()] = Math.min(100, Math.round(n));
          }
        }
      }
    })
    .catch(() => {});
}

/** После загрузки promos.json подставить процент в сохранённый промокод (было discount: 0). */
function reconcileAppliedPromoDiscount() {
  if (!appliedPromo || !appliedPromo.code) return;
  const key = String(appliedPromo.code).toUpperCase();
  const p = MERGED_PROMOS[key];
  if (p == null || !Number.isFinite(Number(p))) return;
  const n = Math.max(0, Math.min(100, Math.round(Number(p))));
  if (n !== Number(appliedPromo.discount)) {
    appliedPromo.discount = n;
    saveAppliedPromo();
  }
}

function computeTotals() {
  const cart = loadCart();
  let subtotal = 0;
  PRODUCTS.forEach((p) => {
    const q = Number(cart[p.id]) || 0;
    if (q > 0) subtotal += q * p.price;
  });
  if (!appliedPromo || subtotal <= 0) {
    return {
      subtotal,
      discountPercent: 0,
      final: subtotal,
      saved: 0,
      promoPending: false,
    };
  }
  let d = Number(appliedPromo.discount) || 0;
  if (!Number.isFinite(d)) d = 0;
  d = Math.max(0, Math.min(100, d));
  if (!d) {
    return {
      subtotal,
      discountPercent: 0,
      final: subtotal,
      saved: 0,
      promoPending: true,
    };
  }
  const final = Math.max(0, Math.round(subtotal * (1 - d / 100)));
  return {
    subtotal,
    discountPercent: d,
    final,
    saved: subtotal - final,
    promoPending: false,
  };
}

function setCartQty(id, qty) {
  const n = Math.max(0, Math.min(999, Math.floor(Number(qty))));
  const cart = loadCart();
  if (n < 1) delete cart[id];
  else cart[id] = n;
  saveCart(cart);
  updateBadge();
  renderCartList();
}

function addToCart(id) {
  const cart = loadCart();
  cart[id] = (Number(cart[id]) || 0) + 1;
  saveCart(cart);
  updateBadge();
  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
}

function productImageBlock(p) {
  const src = p.image ? escapeHtml(p.image) : "";
  const em = escapeHtml(p.emoji);
  if (!src) {
    return `<div class="product-card__img"><span class="product-card__emoji">${em}</span></div>`;
  }
  return `
    <div class="product-card__img">
      <img class="product-card__photo" src="${src}" alt="" loading="lazy"
        onerror="this.style.display='none'; var f=this.nextElementSibling; if(f) f.style.display='flex';" />
      <span class="product-card__emoji" style="display:none;position:absolute;inset:0;align-items:center;justify-content:center;">${em}</span>
    </div>`;
}

function renderProducts() {
  const grid = document.getElementById("products-grid");
  if (!grid) return;
  grid.innerHTML = "";
  PRODUCTS.forEach((p) => {
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `
      ${productImageBlock(p)}
      <div class="product-card__body">
        <h3 class="product-card__title">${escapeHtml(p.title)}</h3>
        <div class="product-card__row">
          <div class="product-card__price">${p.price} ₽</div>
          <button type="button" class="btn btn--primary btn--sm btn-add" data-id="${p.id}">+</button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
  grid.querySelectorAll(".btn-add").forEach((btn) => {
    btn.addEventListener("click", () => addToCart(btn.dataset.id));
  });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function updateCartTotals() {
  const summary = document.getElementById("cart-summary");
  const subEl = document.getElementById("cart-subtotal");
  const promoLine = document.getElementById("cart-promo-line");
  const finalRow = document.getElementById("cart-final-row");
  const finalEl = document.getElementById("cart-final");
  if (!summary || !subEl || !promoLine || !finalRow || !finalEl) return;

  const cart = loadCart();
  let has = false;
  PRODUCTS.forEach((p) => {
    if ((Number(cart[p.id]) || 0) > 0) has = true;
  });

  if (!has) {
    summary.hidden = true;
    if (appliedPromo) {
      appliedPromo = null;
      saveAppliedPromo();
    }
    refreshPromoUI();
    return;
  }

  summary.hidden = false;
  const t = computeTotals();
  const showDiscountedPay =
    appliedPromo &&
    t.discountPercent > 0 &&
    t.final < t.subtotal;
  if (showDiscountedPay) {
    subEl.classList.add("cart-summary__price--strike");
    subEl.textContent = `${t.subtotal} ₽`;
    promoLine.hidden = false;
    promoLine.textContent = `Промокод ${appliedPromo.code} применён: −${t.discountPercent}%`;
    finalRow.hidden = false;
    finalEl.textContent = `${t.final} ₽`;
  } else if (t.promoPending && appliedPromo) {
    subEl.classList.remove("cart-summary__price--strike");
    subEl.textContent = `${t.subtotal} ₽`;
    promoLine.hidden = false;
    promoLine.textContent =
      `Промокод ${appliedPromo.code} — точную сумму со скидкой подтвердит бот после оформления`;
    finalRow.hidden = true;
  } else {
    subEl.classList.remove("cart-summary__price--strike");
    subEl.textContent = `${t.subtotal} ₽`;
    promoLine.hidden = true;
    finalRow.hidden = true;
    finalEl.textContent = "—";
  }
}

function refreshPromoUI() {
  const msg = document.getElementById("promo-msg");
  const clearBtn = document.getElementById("promo-clear");
  if (!msg || !clearBtn) return;
  if (!appliedPromo) {
    msg.hidden = true;
    msg.textContent = "";
    msg.className = "promo-block__msg";
    clearBtn.hidden = true;
    return;
  }
  clearBtn.hidden = false;
}

function showPromoMessage(text, ok) {
  const msg = document.getElementById("promo-msg");
  if (!msg) return;
  msg.hidden = false;
  msg.textContent = text;
  msg.className = ok ? "promo-block__msg promo-block__msg--ok" : "promo-block__msg promo-block__msg--err";
}

function tryApplyPromo() {
  const input = document.getElementById("promo-input");
  if (!input) return;
  const raw = String(input.value || "").trim();
  if (!raw) {
    showPromoMessage("Введите промокод", false);
    return;
  }
  if (raw.length < 2 || raw.length > 32) {
    showPromoMessage("Код: от 2 до 32 символов", false);
    return;
  }
  const cart = loadCart();
  let has = false;
  PRODUCTS.forEach((p) => {
    if ((Number(cart[p.id]) || 0) > 0) has = true;
  });
  if (!has) {
    showPromoMessage("Сначала добавьте товары в корзину", false);
    return;
  }
  const codeNorm = raw.toUpperCase();
  const fromFile = MERGED_PROMOS[codeNorm];
  const pct =
    fromFile != null && Number.isFinite(Number(fromFile))
      ? Math.max(0, Math.min(100, Math.round(Number(fromFile))))
      : 0;
  appliedPromo = { code: codeNorm, discount: pct };
  saveAppliedPromo();
  updateCartTotals();
  if (pct > 0) {
    showPromoMessage(`Промокод ${codeNorm} применён: −${pct}%`, true);
  } else {
    showPromoMessage(
      `Код ${codeNorm} сохранён. Скидку проверит бот при оформлении (как в /add_promo).`,
      true,
    );
  }
  refreshPromoUI();
  if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
}

function clearPromo() {
  appliedPromo = null;
  saveAppliedPromo();
  const input = document.getElementById("promo-input");
  if (input) input.value = "";
  const msg = document.getElementById("promo-msg");
  if (msg) {
    msg.hidden = true;
    msg.textContent = "";
    msg.className = "promo-block__msg";
  }
  refreshPromoUI();
  updateCartTotals();
}

function initCartListDelegation() {
  const list = document.getElementById("cart-list");
  if (!list || list.dataset.delegation) return;
  list.dataset.delegation = "1";
  list.addEventListener("click", (e) => {
    const btn = e.target.closest(".cart-qty-btn");
    if (!btn || !btn.dataset.id) return;
    const id = btn.dataset.id;
    const act = btn.dataset.qtyAct;
    const cart = loadCart();
    let q = Number(cart[id]) || 0;
    if (act === "minus") q = Math.max(0, q - 1);
    else if (act === "plus") q = Math.min(999, q + 1);
    setCartQty(id, q);
  });
  list.addEventListener("change", (e) => {
    const inp = e.target.closest(".cart-qty-input");
    if (!inp || !inp.dataset.id) return;
    let q = parseInt(inp.value, 10);
    if (!Number.isFinite(q)) q = 1;
    setCartQty(inp.dataset.id, q);
  });
}

function renderCartList() {
  const list = document.getElementById("cart-list");
  const empty = document.getElementById("cart-empty");
  const cart = loadCart();
  if (!list || !empty) return;
  list.innerHTML = "";
  let has = false;
  PRODUCTS.forEach((p) => {
    const q = Number(cart[p.id]) || 0;
    if (q < 1) return;
    has = true;
    const line = q * p.price;
    const row = document.createElement("div");
    row.className = "cart-row";
    row.innerHTML = `
      <div class="cart-row__main">
        <div class="cart-row__title">${escapeHtml(p.title)}</div>
        <div class="cart-row__qty">
          <button type="button" class="cart-qty-btn" data-qty-act="minus" data-id="${escapeHtml(p.id)}" aria-label="Меньше">−</button>
          <input type="number" class="cart-qty-input" data-id="${escapeHtml(p.id)}" min="1" max="999" value="${q}" inputmode="numeric" />
          <button type="button" class="cart-qty-btn" data-qty-act="plus" data-id="${escapeHtml(p.id)}" aria-label="Больше">+</button>
        </div>
      </div>
      <div class="cart-row__line-total">${line} ₽</div>
    `;
    list.appendChild(row);
  });
  empty.style.display = has ? "none" : "block";
  updateCartTotals();
  refreshPromoUI();
}

function initSlider() {
  const track = document.getElementById("slider-track");
  const dots = document.getElementById("slider-dots");
  if (!track || !dots) return;
  const banners = getTheme() === "dark" ? BANNERS_DARK : BANNERS_LIGHT;
  banners.forEach((b, i) => {
    const slide = document.createElement("div");
    slide.className = "slider__slide";
    if (b.image) {
      const img = document.createElement("img");
      img.className = "slider__slide-photo";
      img.src = b.image;
      img.alt = "";
      img.loading = "eager";
      img.decoding = "async";
      img.addEventListener("error", () => {
        img.remove();
      });
      slide.appendChild(img);
    }
    const overlay = document.createElement("div");
    overlay.className = "slider__slide-overlay";
    overlay.style.background = b.bg;
    overlay.setAttribute("aria-hidden", "true");
    slide.appendChild(overlay);
    slide.setAttribute("aria-hidden", "true");
    track.appendChild(slide);
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "slider__dot" + (i === 0 ? " slider__dot--active" : "");
    dot.addEventListener("click", () => goSlide(i));
    dots.appendChild(dot);
  });
  let idx = 0;
  function goSlide(i) {
    idx = i;
    track.style.transform = `translateX(-${idx * 100}%)`;
    dots.querySelectorAll(".slider__dot").forEach((d, j) => {
      d.classList.toggle("slider__dot--active", j === idx);
    });
  }
  sliderIntervalId = setInterval(() => {
    idx = (idx + 1) % banners.length;
    goSlide(idx);
  }, 4000);
}

function showPage(name) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("page--active"));
  const map = { home: "page-home", cart: "page-cart", profile: "page-profile" };
  const el = document.getElementById(map[name]);
  if (el) el.classList.add("page--active");
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("nav-btn--active", b.dataset.page === name);
  });
  if (name === "cart") renderCartList();
}

function renderProfile() {
  const box = document.getElementById("profile-info");
  if (!box || !tg) return;
  const u = tg.initDataUnsafe && tg.initDataUnsafe.user;
  if (!u) {
    box.textContent = "Откройте приложение из Telegram, чтобы увидеть профиль.";
    return;
  }
  const lines = [
    `Имя: ${u.first_name || ""} ${u.last_name || ""}`.trim(),
    u.username ? `@${u.username}` : "",
    `ID: ${u.id}`,
  ].filter(Boolean);
  box.innerHTML = lines.map((l) => `<div>${escapeHtml(l)}</div>`).join("");
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => showPage(btn.dataset.page));
});

document.getElementById("checkout-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const cart = loadCart();
  const items = [];
  PRODUCTS.forEach((p) => {
    const qty = Number(cart[p.id]) || 0;
    if (qty > 0) items.push({ id: p.id, title: p.title, qty, price: p.price });
  });
  if (!items.length) {
    if (tg) tg.showAlert("Добавьте товары в корзину");
    return;
  }
  const promoInput = document.getElementById("promo-input");
  const promoTyped = promoInput ? String(promoInput.value || "").trim() : "";
  if (!promoTyped) {
    appliedPromo = null;
    saveAppliedPromo();
  } else {
    const up = promoTyped.toUpperCase();
    if (!appliedPromo || appliedPromo.code !== up) {
      if (tg) {
        tg.showAlert(
          "Промокод не подтверждён: нажмите «Применить» с верным кодом или очистите поле.",
        );
      }
      return;
    }
  }

  const fd = new FormData(e.target);
  const totals = computeTotals();
  const payload = {
    items,
    deliveryType: fd.get("deliveryType"),
    city: String(fd.get("city") || "").trim(),
    address: String(fd.get("address") || "").trim(),
    phone: String(fd.get("phone") || "").trim(),
    comment: String(fd.get("comment") || "").trim(),
    payment: fd.get("payment"),
    total_price: totals.subtotal,
    applied_promo: appliedPromo ? appliedPromo.code : "",
    discount_percent: appliedPromo ? appliedPromo.discount : 0,
    final_price: totals.final,
  };
  if (payload.city.length < 2 || payload.phone.length < 5 || payload.address.length < 3) {
    if (tg) tg.showAlert("Укажите город, адрес и телефон");
    return;
  }
  if (!tg) {
    console.log("payload", payload);
    alert("Telegram WebApp недоступен (откройте из бота)");
    return;
  }
  try {
    tg.sendData(JSON.stringify(payload));
    localStorage.removeItem(CART_KEY);
    localStorage.removeItem(PROMO_KEY);
    appliedPromo = null;
    updateBadge();
    renderCartList();
    if (tg.close) tg.close();
  } catch (err) {
    console.error(err);
    tg.showAlert("Не удалось отправить заказ");
  }
});

async function boot() {
  appliedPromo = loadAppliedPromoState();
  await mergeRemotePromos();
  reconcileAppliedPromoDiscount();
  initTheme();
  initLogo();
  renderProducts();
  initSlider();
  initCartListDelegation();
  document.getElementById("promo-apply")?.addEventListener("click", () => tryApplyPromo());
  document.getElementById("promo-clear")?.addEventListener("click", () => clearPromo());
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    toggleTheme();
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
  });
  updateBadge();
  renderProfile();
  renderCartList();
  showPage("home");
}

boot();
