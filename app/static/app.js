"use strict";
const ROLES = { user: "Қолданушы", manager: "Меңгеруші", admin: "Әкімші" };
const TYPES = { in: "Кіріс", out: "Шығыс", init: "Бастапқы қалдық" };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n).toLocaleString("ru-RU");
const canEdit = () => me && me.role !== "user";
const isAdmin = () => me && me.role === "admin";

let me = null, editId = null, moveId = null, moveType = null, confirmAction = null, searchTimer = null;

/* ---------- API ---------- */
async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch("/api" + path, {
      method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw apiError("Серверге қосылу мүмкін болмады. Интернетті тексеріп, қайта көріңіз.", 0);
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* JSON емес жауап */ }
  if (!res.ok) {
    const e = (data && data.error) || { message: "Күтпеген қате. Қайта көріңіз." };
    throw apiError(e.message, res.status, e.details, e.code);
  }
  return data;
}
function apiError(message, status, details = [], code = "") {
  const err = new Error(message);
  Object.assign(err, { status, details, code });
  return err;
}
function errText(err) {
  const extra = (err.details || []).map((d) => (d.field ? d.field + ": " : "") + d.message);
  return extra.length ? err.message + " " + extra.join(" ") : err.message;
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
async function busy(form, fn) {
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  try { await fn(); } finally { btn.disabled = false; }
}

/* ---------- Auth ---------- */
function showAuth(which = "login", msg = "", ok = false) {
  me = null;
  $("app").classList.add("hide");
  $("auth").classList.remove("hide");
  $("loginForm").classList.toggle("hide", which !== "login");
  $("regForm").classList.toggle("hide", which !== "reg");
  setMsg("lmsg", msg, ok); setMsg("rmsg", "");
  $("lp").value = "";
}
function showApp() {
  $("auth").classList.add("hide");
  $("app").classList.remove("hide");
  $("who").textContent = me.username;
  $("role").textContent = ROLES[me.role];
  document.querySelectorAll(".edit-only").forEach((e) => e.classList.toggle("hide", !canEdit()));
  document.querySelector('[data-t="users"]').classList.toggle("hide", !isAdmin());
  tab("goods");
  refresh();
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
      setMsg("lmsg", ""); showApp();
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
      $("lu").value = body.username; $("lp").focus();
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
  ["goods", "moves", "users"].forEach((x) => $(x).classList.toggle("hide", x !== t));
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
}
document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => tab(b.dataset.t)));

/* ---------- Data ---------- */
function handle(err) {
  if (err.status === 401) return showAuth("login", "Сессия аяқталды. Қайта кіріңіз.");
  showBanner(errText(err));
}
async function refresh() {
  showBanner("");
  await Promise.all([loadStats(), loadGoods(), loadMoves(), isAdmin() ? loadUsers() : null]);
}
async function loadStats() {
  try {
    const s = (await api("/stats")).stats;
    $("s1").textContent = fmt(s.products);
    $("s2").textContent = fmt(s.total_quantity);
    $("s3").textContent = fmt(s.total_value) + " ₸";
    $("s4").textContent = fmt(s.low_stock);
  } catch (e) { handle(e); }
}
async function loadGoods() {
  try {
    const qs = new URLSearchParams({ low: $("f").value });
    if ($("q").value.trim()) qs.set("search", $("q").value.trim());
    const list = (await api("/products?" + qs)).products;
    $("gb").innerHTML = list.length ? list.map(goodRow).join("")
      : `<tr><td colspan="7" class="empty">Тауар табылмады. Іздеуді өзгертіңіз${canEdit() ? " немесе жаңа тауар қосыңыз" : ""}.</td></tr>`;
  } catch (e) { handle(e); }
}
function goodRow(p) {
  const acts = canEdit()
    ? `<button class="btn sm" data-a="in" data-id="${p.id}">Кіріс</button><button class="btn sm ghost" data-a="out" data-id="${p.id}">Шығыс</button><button class="btn sm ghost" data-a="edit" data-id="${p.id}">Өңдеу</button>` : "";
  const del = isAdmin() ? `<button class="btn sm ghost" data-a="del" data-id="${p.id}" data-name="${esc(p.name)}">Жою</button>` : "";
  return `<tr><td>${esc(p.sku)}</td><td>${esc(p.name)}</td><td>${esc(p.category)}</td><td>${fmt(p.price)} ₸</td><td><b>${p.quantity}</b></td>
    <td><span class="tag ${p.low ? "bad" : "ok"}">${p.low ? "Аз қалды" : "Жеткілікті"}</span></td><td><div class="acts">${acts}${del}</div></td></tr>`;
}
async function loadMoves() {
  try {
    const list = (await api("/movements")).movements;
    $("mb").innerHTML = list.length ? list.map((m) =>
      `<tr><td>${esc(new Date(m.created_at).toLocaleString("ru-RU"))}</td><td>${esc(m.product_name)}</td>
       <td class="${m.type === "out" ? "out" : "in"}">${TYPES[m.type]}</td><td>${m.quantity}</td><td>${esc(m.username)}</td></tr>`).join("")
      : `<tr><td colspan="5" class="empty">Әзірге операция жоқ. Тауарға кіріс немесе шығыс жасаңыз.</td></tr>`;
  } catch (e) { handle(e); }
}
async function loadUsers() {
  try {
    const list = (await api("/users")).users;
    $("ub").innerHTML = list.map((u) => {
      const self = u.id === me.id;
      const sel = `<select data-role-for="${u.id}" aria-label="Рөл" ${self ? "disabled" : ""}>${Object.keys(ROLES).map((r) => `<option value="${r}" ${r === u.role ? "selected" : ""}>${ROLES[r]}</option>`).join("")}</select>`;
      const del = self ? "" : `<button class="btn sm ghost" data-a="deluser" data-id="${u.id}" data-name="${esc(u.username)}">Жою</button>`;
      return `<tr><td>${esc(u.username)}</td><td>${esc(u.email)}</td><td>${ROLES[u.role]}</td><td>${sel}</td><td>${del}</td></tr>`;
    }).join("");
  } catch (e) { handle(e); }
}

$("q").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadGoods, 250); });
$("f").addEventListener("change", loadGoods);

/* ---------- Actions ---------- */
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-a]");
  if (b) {
    const id = Number(b.dataset.id);
    if (b.dataset.a === "in" || b.dataset.a === "out") openMove(id, b.dataset.a);
    if (b.dataset.a === "edit") openItem(id);
    if (b.dataset.a === "del") askConfirm(`«${b.dataset.name}» тауарын жою керек пе? Қозғалыс тарихы сақталады.`, async () => { await api("/products/" + id, { method: "DELETE" }); refresh(); });
    if (b.dataset.a === "deluser") askConfirm(`«${b.dataset.name}» аккаунтын жою керек пе?`, async () => { await api("/users/" + id, { method: "DELETE" }); loadUsers(); });
  }
  const c = e.target.closest("[data-close]");
  if (c) $(c.dataset.close).close();
});
document.addEventListener("change", async (e) => {
  const s = e.target.closest("[data-role-for]");
  if (!s) return;
  try { await api("/users/" + s.dataset.roleFor, { method: "PATCH", body: { role: s.value } }); showBanner(""); }
  catch (err) { handle(err); }
  loadUsers();
});

function askConfirm(text, fn) {
  $("dcm").textContent = text;
  confirmAction = fn;
  $("dc").showModal();
}
$("dcok").onclick = async () => {
  $("dc").close();
  try { await confirmAction(); } catch (err) { handle(err); }
};

/* Тауар қосу/өңдеу */
async function openItem(id) {
  if (!canEdit()) return;
  editId = id || null;
  let p = {};
  if (id) { try { p = (await api("/products/" + id)).product; } catch (e) { return handle(e); } }
  $("dit").textContent = id ? "Тауарды өңдеу" : "Тауар қосу";
  $("iname").value = p.name || ""; $("isku").value = p.sku || ""; $("icat").value = p.category || "";
  $("iprice").value = p.price ?? ""; $("imin").value = p.min_quantity ?? 10; $("iqty").value = 0;
  $("qtyrow").classList.toggle("hide", !!id);
  setMsg("imsg", "");
  $("di").showModal();
}
$("addBtn").onclick = () => openItem();
$("itemForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const num = (id) => ($(id).value.trim() === "" ? null : Number($(id).value));
  const body = { sku: $("isku").value.trim(), name: $("iname").value.trim(), category: $("icat").value.trim() || "Басқа", price: num("iprice"), min_quantity: num("imin") ?? 0 };
  if (!body.name || !body.sku || body.price === null) return setMsg("imsg", "Атауын, артикулін және бағасын толтырыңыз.");
  if (!editId) body.quantity = num("iqty") ?? 0;
  busy(e.target, async () => {
    try {
      await api(editId ? "/products/" + editId : "/products", { method: editId ? "PUT" : "POST", body });
      $("di").close(); refresh();
    } catch (err) { setMsg("imsg", errText(err)); }
  });
});

/* Кіріс / шығыс */
function openMove(id, type) {
  moveId = id; moveType = type;
  $("dmt").textContent = type === "in" ? "Кіріс (тауар қабылдау)" : "Шығыс (тауар беру)";
  $("mqty").value = 1; setMsg("mmsg", "");
  $("dm").showModal();
}
$("moveForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const quantity = Number($("mqty").value);
  if (!Number.isInteger(quantity) || quantity < 1) return setMsg("mmsg", "Санды 1-ден бастап бүтін сан етіп енгізіңіз.");
  busy(e.target, async () => {
    try {
      await api(`/products/${moveId}/movements`, { method: "POST", body: { type: moveType, quantity } });
      $("dm").close(); refresh();
    } catch (err) { setMsg("mmsg", errText(err)); }
  });
});

/* ---------- Start ---------- */
(async function boot() {
  try {
    me = (await api("/auth/me")).user;
    showApp();
  } catch (e) {
    if (e.status === 401) showAuth("login");
    else { showAuth("login", errText(e)); }
  }
})();
