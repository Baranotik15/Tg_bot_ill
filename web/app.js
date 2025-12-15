const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
const HEADERS = { "X-Telegram-Init-Data": initData };

let IS_ADMIN = false;
let eventsCache = new Map();

async function api(path, options = {}) {
    const res = await fetch(path, {
        credentials: "same-origin",
        headers: { ...HEADERS, ...options.headers },
        ...options
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function loadMe() {
    const me = await api("/me");
    IS_ADMIN = me.is_admin;
    document.getElementById("balance").innerText = `💰 Баланс: ${me.balance}`;
    renderAdminControls();
}

function renderAdminControls() {
    const c = document.getElementById("admin-controls");
    c.innerHTML = "";
    if (!IS_ADMIN) return;

    const b = document.createElement("button");
    b.className = "admin";
    b.innerText = "➕ Создать событие";
    b.onclick = openCreateModal;
    c.appendChild(b);
}

function openCreateModal() {
    showModal(`
        <input id="title" placeholder="Название">
        <input id="red" type="number" placeholder="Коэф 🔴">
        <input id="black" type="number" placeholder="Коэф ⚫">
        <button class="admin" onclick="submitCreate()">Создать</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitCreate() {
    await api("/admin/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            title: title.value,
            red_odds: red.value,
            black_odds: black.value
        })
    });
    closeModal();
    alert("Событие успешно создано");
    loadEvents();
}

function openFinishModal(id) {
    showModal(`
        <button class="red" onclick="finish(${id}, 'red')">🔴 Красные</button>
        <button class="black" onclick="finish(${id}, 'black')">⚫ Чёрные</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function finish(id, winner) {
    await api(`/admin/events/${id}/finish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ winner })
    });
    closeModal();
    alert("Событие успешно завершено");
    document.getElementById(`event-${id}`)?.remove();
}

function showModal(html) {
    modal.style.display = "block";
    modal-content.innerHTML = html;
}

function closeModal() {
    modal.style.display = "none";
}

async function loadEvents() {
    const events = await api("/events");
    const c = document.getElementById("events");
    c.innerHTML = "";

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";
        card.id = `event-${e.id}`;
        card.innerHTML = `
            <b>${e.title}</b>
            <div>⏱ ${Math.floor(e.time_left/60)}:${String(e.time_left%60).padStart(2,"0")}</div>
            <button class="red">🔴 x${e.red_odds}</button>
            <button class="black">⚫ x${e.black_odds}</button>
            ${IS_ADMIN ? `<button class="admin" onclick="openFinishModal(${e.id})">Завершить</button>` : ""}
        `;
        c.appendChild(card);
    }
}

loadMe();
loadEvents();
setInterval(loadMe, 2000);
setInterval(loadEvents, 2000);
