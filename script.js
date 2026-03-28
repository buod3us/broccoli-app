/**
 * Mini App «Бро Кколи» — id товаров должны совпадать с catalog.MINI_APP_PRODUCT_IDS в боте.
 */
const PRODUCTS = [
  { id: "buckwheat_chicken", title: "Гречка с курицей", emoji: "🍲", price: 350 },
  { id: "rice_chicken", title: "Рис с курицей", emoji: "🍛", price: 350 },
  { id: "beef_buckwheat", title: "Гречка с говядиной", emoji: "🥩", price: 350 },
];

const BANNERS = [
  { bg: "linear-gradient(135deg,#2e7d32,#66bb6a)", text: "Халяль • 5 минут • Сублимация" },
  { bg: "linear-gradient(135deg,#1b5e20,#81c784)", text: "Бро Кколи — еда для быта и Хаджа" },
  { bg: "linear-gradient(135deg,#388e3c,#a5d6a7)", text: "350 ₽ за порцию в приложении" },
];

const CART_KEY = "broccoli_cart_v1";

const tg = window.Telegram && window.Telegram.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  if (tg.setHeaderColor) tg.setHeaderColor("#ffffff");
  if (tg.setBackgroundColor) tg.setBackgroundColor("#ffffff");
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
  return Object.values(cart).reduce((s, q) => s + q, 0);
}

function updateBadge() {
  const cart = loadCart();
  const n = cartCount(cart);
  const el = document.getElementById("cart-badge");
  if (!el) return;
  el.textContent = n;
  el.style.display = n > 0 ? "flex" : "none";
}

function addToCart(id) {
  const cart = loadCart();
  cart[id] = (cart[id] || 0) + 1;
  saveCart(cart);
  updateBadge();
  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
}

function renderProducts() {
  const grid = document.getElementById("products-grid");
  if (!grid) return;
  grid.innerHTML = "";
  PRODUCTS.forEach((p) => {
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `
      <div class="product-card__img">${p.emoji}</div>
      <div class="product-card__body">
        <h3 class="product-card__title">${escapeHtml(p.title)}</h3>
        <div class="product-card__price">${p.price} ₽</div>
        <button type="button" class="btn btn--primary btn--sm btn-add" data-id="${p.id}">+</button>
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

function renderCartList() {
  const list = document.getElementById("cart-list");
  const empty = document.getElementById("cart-empty");
  const cart = loadCart();
  if (!list || !empty) return;
  list.innerHTML = "";
  let has = false;
  PRODUCTS.forEach((p) => {
    const q = cart[p.id] || 0;
    if (q < 1) return;
    has = true;
    const row = document.createElement("div");
    row.className = "cart-row";
    row.innerHTML = `
      <span>${escapeHtml(p.title)}</span>
      <span><strong>${q}</strong> × ${p.price} ₽</span>
    `;
    list.appendChild(row);
  });
  empty.style.display = has ? "none" : "block";
}

function initSlider() {
  const track = document.getElementById("slider-track");
  const dots = document.getElementById("slider-dots");
  if (!track || !dots) return;
  BANNERS.forEach((b, i) => {
    const slide = document.createElement("div");
    slide.className = "slider__slide";
    slide.style.background = b.bg;
    slide.textContent = b.text;
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
  setInterval(() => {
    idx = (idx + 1) % BANNERS.length;
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
    const qty = cart[p.id] || 0;
    if (qty > 0) items.push({ id: p.id, title: p.title, qty, price: p.price });
  });
  if (!items.length) {
    if (tg) tg.showAlert("Добавьте товары в корзину");
    return;
  }
  const fd = new FormData(e.target);
  const payload = {
    items,
    deliveryType: fd.get("deliveryType"),
    city: String(fd.get("city") || "").trim(),
    phone: String(fd.get("phone") || "").trim(),
    comment: String(fd.get("comment") || "").trim(),
    payment: fd.get("payment"),
  };
  if (payload.city.length < 2 || payload.phone.length < 5) {
    if (tg) tg.showAlert("Укажите город и телефон");
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
    updateBadge();
    renderCartList();
    if (tg.close) tg.close();
  } catch (err) {
    console.error(err);
    tg.showAlert("Не удалось отправить заказ");
  }
});

renderProducts();
initSlider();
updateBadge();
renderProfile();
showPage("home");
