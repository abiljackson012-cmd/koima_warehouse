"use strict";
const ROLES = { buyer: "Сатып алушы", manager: "Меңгеруші", admin: "Әкімші" };
const TYPES = { in: "Кіріс", out: "Шығыс", init: "Бастапқы қалдық" };
const STATUS = { new: "Жаңа", done: "Орындалды" };
const MAX_IMG = 3 * 1024 * 1024;
const SECTIONS = ["goods", "cart", "orders", "moves", "users"];
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n).toLocaleString("ru-RU");
const isStaff = () => !!me && me.role !== "buyer";
const isAdmin = () => !!me && me.role === "admin";

let me = null, editId = null, moveId = null, moveType = null, confirmAction = null, searchTimer = null, toastTimer = null;

/* ---------- API ---------- */
function apiError(message, status, details = [], code = "") {
  return Object.assign(new Error(message), { status, details, code });
}
async function parse(res) {
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* JSON емес жауап */ }
  if (!res.ok) {
    const e = (data && data.error) || { message: "Күтпеген қате. Қайта көріңіз." };
    throw apiError(e.message, res.status, e.details, e.code);
  }
  return data;
}
async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch("/api" + path, {
      method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw apiError("Серверге қосылу мүмкін болмады. Интернетті немесе серверді тексеріңіз.", 0);
  }
  return parse(res);
}
async function upload(path, file) {
  const fd = new FormData();
  fd.append("image", file);
  let res;
  try {
    res = await fetch("/api" + path, { method: "POST", credentials: "same-origin", body: fd });
  } catch {
    throw apiError("Суретті жүктеу мүмкін болмады.", 0);
  }
  return parse(res);
}
function errText(err) {
  const extra = (err.details || []).map((d) => (d.field ? d.field + ": " : "") + d.message);
  return extra.length ? `${err.message} ${extra.join(" ")}` : err.message;
}
function setMsg(id, text, ok = false) {
  const el = $(id);
  el.textContent = text || "";
  el.classList.toggle("ok", ok);
}
function showBanner(text) {
  const b = $("banner");
  b.textContent = text || "";
  b.classList.toggle("hide", !text);
}
function toast(msg, isErr = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 2800);
}
async function busy(form, fn) {
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  try { await fn(); } finally { btn.disabled = false; }
}
function handle(err) {
  if (err.status === 401) return showAuth("login", "Сессия аяқталды. Қайта кіріңіз.");
  showBanner(errText(err));
}

/* ---------- Auth ---------- */
function showAuth(which = "login", msg = "", ok = false) {
  me = null;
  setCartCount(0);
  $("app").classList.add("hide");
  $("auth").classList.remove("hide");
  $("loginForm").classList.toggle("hide", which !== "login");
  $("regForm").classList.toggle("hide", which !== "reg");
  setMsg("lmsg", which === "login" ? msg : "", ok);
  setMsg("rmsg", "");
  $("lp").value = "";
}
function applyRoles() {
  document.querySelectorAll("[data-show]").forEach((el) => {
    const need = el.dataset.show;
    const ok = need === "buyer" ? !isStaff() : need === "staff" ? isStaff() : need === "admin" ? isAdmin() : true;
    el.classList.toggle("hide", !ok);
  });
}
function showApp() {
  $("auth").classList.add("hide");
  $("app").classList.remove("hide");
  $("who").textContent = me.username;
  $("role").textContent = ROLES[me.role];
  applyRoles();
  tab("goods");
  if (isStaff()) loadStats(); else loadCart();
}

$("toReg").onclick = () => { $("regForm").reset(); showAuth("reg"); $("ru").focus(); };
$("toLogin").onclick = () => showAuth("login");

$("loginForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const username = $("lu").value.trim(), password = $("lp").value;
  if (!username || !password) return setMsg("lmsg", "Логин мен құпиясөзді енгізіңіз.");
  busy(e.target, async () => {
    try {
      me = (await api("/auth/login", { method: "POST", body: { username, password } })).user;
      setMsg("lmsg", "");
      showApp();
    } catch (err) { setMsg("lmsg", errText(err)); }
  });
});

$("regForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const body = { username: $("ru").value.trim(), email: $("re").value.trim(), password: $("rp").value };
  if (body.password !== $("rp2").value) return setMsg("rmsg", "Құпиясөздер сәйкес келмейді. Қайта енгізіңіз.");
  busy(e.target, async () => {
    try {
      await api("/auth/register", { method: "POST", body });
      showAuth("login", "Тіркелу сәтті өтті. Енді кіріңіз.", true);
      $("lu").value = body.username;
      $("lp").focus();
    } catch (err) { setMsg("rmsg", errText(err)); }
  });
});

$("logout").onclick = async () => {
  try { await api("/auth/logout", { method: "POST" }); } catch { /* сессия бұрын аяқталған болуы мүмкін */ }
  $("lu").value = "";
  showAuth("login");
};

/* ---------- Tabs ---------- */
function tab(t) {
  SECTIONS.forEach((x) => $(x).classList.toggle("hide", x !== t));
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
  const loaders = { goods: loadGoods, cart: loadCart, orders: loadOrders, moves: loadMoves, users: loadUsers };
  if (loaders[t]) loaders[t]();
}
document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => tab(b.dataset.t)));

/* ---------- Stats & catalog ---------- */
async function loadStats() {
  try {
    const s = (await api("/stats")).stats;
    $("s1").textContent = fmt(s.products);
    $("s2").textContent = fmt(s.total_quantity);
    $("s3").textContent = fmt(s.total_value) + " ₸";
    $("s4").textContent = fmt(s.low_stock);
  } catch (e) { handle(e); }
}
function refreshGoods() {
  loadGoods();
  if (isStaff()) loadStats();
}
async function loadGoods() {
  try {
    const qs = new URLSearchParams();
    const q = $("q").value.trim();
    if (q) qs.set("search", q);
    if (isStaff() && $("f").value === "1") qs.set("low", "1");
    const list = (await api("/products?" + qs)).products;
    $("grid").innerHTML = list.length ? list.map(card).join("")
      : `<p class="empty">Тауар табылмады. Іздеуді өзгертіңіз.</p>`;
  } catch (e) { handle(e); }
}
function imgOrPlaceholder(p) {
  return p.image_url
    ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" loading="lazy">`
    : `<span class="ph" aria-hidden="true">${esc(String(p.name || "?").trim().charAt(0).toUpperCase())}</span>`;
}
function card(p) {
  const out = p.quantity === 0;
  let stock, actions;
  if (isStaff()) {
    stock = `<span class="tag ${p.low ? "bad" : "ok"}">${p.low ? "Аз қалды" : "Жеткілікті"}</span>
      <span class="muted">Қалдық: <b>${p.quantity}</b></span>`;
    actions = `<div class="acts">
      <button class="btn sm" data-a="in" data-id="${p.id}">Кіріс</button>
      <button class="btn sm ghost" data-a="out" data-id="${p.id}">Шығыс</button>
      <button class="btn sm ghost" data-a="edit" data-id="${p.id}">Өңдеу</button>
      ${isAdmin() ? `<button class="btn sm ghost" data-a="del" data-id="${p.id}" data-name="${esc(p.name)}">Жою</button>` : ""}
    </div>`;
  } else {
    stock = out ? `<span class="tag bad">Таусылған</span>` : `<span class="tag ok">Қоймада бар</span>`;
    actions = out ? "" : `<div class="buy">
      <input class="qin" type="number" min="1" max="${p.quantity}" value="1" aria-label="Саны">
      <button class="btn sm" data-a="cart" data-id="${p.id}">Себетке қосу</button>
    </div>`;
  }
  return `<article class="card">
    <div class="pimg">${imgOrPlaceholder(p)}</div>
    <div class="cbody">
      <h3>${esc(p.name)}</h3>
      <p class="muted">${esc(p.sku)} · ${esc(p.category)}</p>
      <p class="price">${fmt(p.price)} ₸</p>
      <div class="stock">${stock}</div>
      ${actions}
    </div>
  </article>`;
}

/* ---------- Cart ---------- */
function setCartCount(n) {
  $("cartCount").textContent = n ? ` (${n})` : "";
}
async function loadCart() {
  if (isStaff()) return;
  try {
    const cart = (await api("/cart")).cart;
    setCartCount(cart.count);
    $("cartList").innerHTML = cart.items.length ? cart.items.map(cartRow).join("")
      : `<p class="empty">Себет бос. «Тауарлар» бөлімінен тауар қосыңыз.</p>`;
    $("checkout").innerHTML = cart.items.length
      ? `<div class="total">Жалпы сома: <b>${fmt(cart.total)} ₸</b></div>
         <button class="btn" data-a="order">Тапсырыс беру</button>`
      : "";
  } catch (e) { handle(e); }
}
function cartRow(it) {
  const warn = it.available ? "" : `<span class="tag bad">Қоймада тек ${it.stock} дана бар</span>`;
  const img = it.image_url
    ? `<img src="${esc(it.image_url)}" alt="">`
    : `<span class="ph" aria-hidden="true">${esc(it.name.charAt(0))}</span>`;
  return `<div class="crow">
    <div class="cthumb">${img}</div>
    <div>
      <b>${esc(it.name)}</b>
      <p class="muted">${fmt(it.price)} ₸ · ${esc(it.sku)}</p>
      ${warn}
    </div>
    <div class="cqty">
      <button class="btn sm ghost" data-a="dec" data-id="${it.product_id}" aria-label="Азайту">−</button>
      <input class="qin" type="number" min="0" max="1000" value="${it.quantity}" data-pid="${it.product_id}" aria-label="Саны">
      <button class="btn sm ghost" data-a="inc" data-id="${it.product_id}" aria-label="Көбейту">+</button>
    </div>
    <div class="csum">${fmt(it.subtotal)} ₸</div>
    <button class="btn sm ghost" data-a="rm" data-id="${it.product_id}">Алып тастау</button>
  </div>`;
}
async function addToCart(pid, btn) {
  const quantity = Number(btn.parentElement.querySelector(".qin").value);
  if (!Number.isInteger(quantity) || quantity < 1) return toast("Санды 1-ден бастап бүтін сан етіп енгізіңіз.", true);
  btn.disabled = true;
  try {
    const r = await api("/cart", { method: "POST", body: { product_id: pid, quantity } });
    setCartCount(r.cart.count);
    toast("Себетке қосылды");
  } catch (e) { toast(errText(e), true); }
  finally { btn.disabled = false; }
}
async function setCartQty(pid, quantity) {
  if (!Number.isInteger(quantity) || quantity < 0) return loadCart();
  try {
    await api(`/cart/${pid}`, { method: "PATCH", body: { quantity } });
    loadCart();
  } catch (e) {
    toast(errText(e), true);
    loadCart();
  }
}
async function removeFromCart(pid) {
  try {
    await api(`/cart/${pid}`, { method: "DELETE" });
    toast("Алынып тасталды");
    loadCart();
  } catch (e) { toast(errText(e), true); }
}
async function placeOrder(btn) {
  btn.disabled = true;
  try {
    const r = await api("/orders", { method: "POST" });
    toast(`Тапсырыс №${r.order.id} қабылданды`);
  } catch (e) {
    toast(errText(e), true);
  }
  loadCart();
  loadGoods();
  loadOrders();
}

/* ---------- Orders ---------- */
async function loadOrders() {
  try {
    const list = (await api("/orders")).orders;
    $("orderList").innerHTML = list.length ? list.map(orderCard).join("")
      : `<p class="empty">Тапсырыс әзірге жоқ.</p>`;
  } catch (e) { handle(e); }
}
function orderCard(o) {
  const done = o.status === "done";
  const items = o.items.map((i) => `${esc(i.product_name)} × ${i.quantity}`).join(", ");
  const who = isStaff() ? `${esc(o.username)} · ` : "";
  const act = isStaff() && !done
    ? `<button class="btn sm" data-a="done" data-id="${o.id}">Орындалды деп белгілеу</button>` : "";
  return `<article class="ocard">
    <div class="orow"><b>Тапсырыс №${o.id}</b><span class="tag ${done ? "ok" : "nw"}">${STATUS[o.status]}</span></div>
    <p class="muted">${esc(new Date(o.created_at).toLocaleString("ru-RU"))}</p>
    <p>${who}${items}</p>
    <p><b>${fmt(o.total)} ₸</b></p>
    ${act}
  </article>`;
}
async function setOrderStatus(oid) {
  try {
    await api(`/orders/${oid}`, { method: "PATCH", body: { status: "done" } });
    toast("Белгіленді");
    loadOrders();
  } catch (e) { toast(errText(e), true); }
}

/* ---------- Moves & users (staff) ---------- */
async function loadMoves() {
  if (!isStaff()) return;
  try {
    const list = (await api("/movements")).movements;
    $("mb").innerHTML = list.length ? list.map((m) =>
      `<tr><td>${esc(new Date(m.created_at).toLocaleString("ru-RU"))}</td><td>${esc(m.product_name)}</td>
       <td class="${m.type === "out" ? "out" : "in"}">${TYPES[m.type]}</td><td>${m.quantity}</td><td>${esc(m.username)}</td></tr>`).join("")
      : `<tr><td colspan="5" class="empty">Әзірге операция жоқ.</td></tr>`;
  } catch (e) { handle(e); }
}
async function loadUsers() {
  if (!isAdmin()) return;
  try {
    const list = (await api("/users")).users;
    $("ub").innerHTML = list.map((u) => {
      const self = u.id === me.id;
      const sel = `<select data-role-for="${u.id}" aria-label="Рөл" ${self ? "disabled" : ""}>${
        Object.keys(ROLES).map((r) => `<option value="${r}" ${r === u.role ? "selected" : ""}>${ROLES[r]}</option>`).join("")}</select>`;
      const del = self ? "" : `<button class="btn sm ghost" data-a="deluser" data-id="${u.id}" data-name="${esc(u.username)}">Жою</button>`;
      return `<tr><td>${esc(u.username)}</td><td>${esc(u.email)}</td><td>${ROLES[u.role]}</td><td>${sel}</td><td>${del}</td></tr>`;
    }).join("");
  } catch (e) { handle(e); }
}

/* ---------- Product form (staff) ---------- */
$("addBtn").onclick = () => openItem();
$("q").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadGoods, 250); });
$("f").addEventListener("change", loadGoods);

function setPreview(url) {
  $("ipreview").innerHTML = url ? `<img src="${esc(url)}" alt="Тауар суреті">` : "Сурет жоқ";
}
async function openItem(id) {
  if (!isStaff()) return;
  editId = id || null;
  let p = {};
  if (id) {
    try { p = (await api("/products/" + id)).product; } catch (e) { return handle(e); }
  }
  $("dit").textContent = id ? "Тауарды өңдеу" : "Тауар қосу";
  $("iname").value = p.name || "";
  $("isku").value = p.sku || "";
  $("icat").value = p.category || "";
  $("iprice").value = p.price ?? "";
  $("imin").value = p.min_quantity ?? 10;
  $("iqty").value = 0;
  $("qtyrow").classList.toggle("hide", !!id);
  $("ifile").value = "";
  setPreview(p.image_url || null);
  setMsg("imsg", "");
  $("di").showModal();
}
$("ifile").addEventListener("change", () => {
  const f = $("ifile").files[0];
  if (!f) return setPreview(null);
  if (f.size > MAX_IMG) { $("ifile").value = ""; return setMsg("imsg", "Сурет тым үлкен. Ең көбі 3 МБ."); }
  if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { $("ifile").value = ""; return setMsg("imsg", "Тек JPG, PNG немесе WEBP суретін таңдаңыз."); }
  setMsg("imsg", "");
  setPreview(URL.createObjectURL(f));
});
$("itemForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const num = (id) => ($(id).value.trim() === "" ? null : Number($(id).value));
  const body = {
    sku: $("isku").value.trim(),
    name: $("iname").value.trim(),
    category: $("icat").value.trim() || "Басқа",
    price: num("iprice"),
    min_quantity: num("imin") ?? 0,
  };
  if (!body.name || !body.sku || body.price === null) return setMsg("imsg", "Атауын, артикулін және бағасын толтырыңыз.");
  if (!editId) body.quantity = num("iqty") ?? 0;
  busy(e.target, async () => {
    try {
      const r = await api(editId ? "/products/" + editId : "/products", { method: editId ? "PUT" : "POST", body });
      if (!editId) editId = r.product.id;  // тауар сақталды; суретті қайталағанда дубль жасалмайды
      refreshGoods();
      const file = $("ifile").files[0];
      if (file) await upload(`/products/${editId}/image`, file);
      $("di").close();
      toast("Сақталды");
      refreshGoods();
    } catch (err) { setMsg("imsg", errText(err)); }
  });
});

/* ---------- Stock movement (staff) ---------- */
function openMove(id, type) {
  moveId = id;
  moveType = type;
  $("dmt").textContent = type === "in" ? "Кіріс (тауар қабылдау)" : "Шығыс (тауар беру)";
  $("mqty").value = 1;
  setMsg("mmsg", "");
  $("dm").showModal();
}
$("moveForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const quantity = Number($("mqty").value);
  if (!Number.isInteger(quantity) || quantity < 1) return setMsg("mmsg", "Санды 1-ден бастап бүтін сан етіп енгізіңіз.");
  busy(e.target, async () => {
    try {
      await api(`/products/${moveId}/movements`, { method: "POST", body: { type: moveType, quantity } });
      $("dm").close();
      refreshGoods();
      loadMoves();
    } catch (err) { setMsg("mmsg", errText(err)); }
  });
});

/* ---------- Confirm & global clicks ---------- */
function askConfirm(text, fn) {
  $("dcm").textContent = text;
  confirmAction = fn;
  $("dc").showModal();
}
$("dcok").onclick = async () => {
  $("dc").close();
  try { await confirmAction(); toast("Жойылды"); } catch (err) { handle(err); }
};

document.addEventListener("click", (e) => {
  const c = e.target.closest("[data-close]");
  if (c) return $(c.dataset.close).close();
  const b = e.target.closest("[data-a]");
  if (!b) return;
  const id = Number(b.dataset.id);
  switch (b.dataset.a) {
    case "in": case "out": return openMove(id, b.dataset.a);
    case "edit": return openItem(id);
    case "cart": return addToCart(id, b);
    case "inc": case "dec": {
      const cur = Number(b.parentElement.querySelector(".qin").value) || 0;
      return setCartQty(id, Math.max(0, cur + (b.dataset.a === "inc" ? 1 : -1)));
    }
    case "rm": return removeFromCart(id);
    case "order": return placeOrder(b);
    case "done": return setOrderStatus(id);
    case "del": return askConfirm(`«${b.dataset.name}» тауарын жою керек пе? Қозғалыс тарихы сақталады.`, async () => {
      await api("/products/" + id, { method: "DELETE" });
      refreshGoods();
    });
    case "deluser": return askConfirm(`«${b.dataset.name}» аккаунтын жою керек пе?`, async () => {
      await api("/users/" + id, { method: "DELETE" });
      loadUsers();
    });
  }
});
document.addEventListener("change", async (e) => {
  const s = e.target.closest("[data-role-for]");
  if (s) {
    try {
      await api("/users/" + s.dataset.roleFor, { method: "PATCH", body: { role: s.value } });
      toast("Рөл өзгертілді");
    } catch (err) { toast(errText(err), true); }
    return loadUsers();
  }
  if (e.target.matches(".qin[data-pid]")) setCartQty(Number(e.target.dataset.pid), Number(e.target.value));
});

/* ---------- Start ---------- */
(async function boot() {
  try {
    me = (await api("/auth/me")).user;
    showApp();
  } catch (e) {
    showAuth("login", e.status === 401 ? "" : errText(e));
  }
})();
