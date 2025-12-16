const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) throw new Error("No initData");

const HEADERS = { "X-Telegram-Init-Data": initData };

let IS_ADMIN = false;

const modal = document.getElementById("modal");
const modalContent = document.getElementById("modal-content");

async function api(path, options = {}) {
    const res = await fetch(path, {
        ...options,
        credentials: "same-origin",
        headers: {
            ...HEADERS,
            ...(options.headers || {})
        }
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

    const btn = document.createElement("button");
    btn.className = "admin";
    btn.innerText = "➕ Создать событие";
    btn.onclick = openCreateModal;
    c.appendChild(btn);
}

function showModal(html) {
    modalContent.innerHTML = html;
    modal.style.display = "block";
}

function closeModal() {
    modal.style.display = "none";
    modalContent.innerHTML = "";
}

function openCreateModal() {
    showModal(`
        <input id="title" placeholder="Название">
        <input id="red" type="number" step="0.1" placeholder="Коэф 🔴">
        <input id="black" type="number" step="0.1" placeholder="Коэф ⚫">
        <button class="admin" onclick="submitCreate()">Создать</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitCreate() {
    await api("/admin/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            title: document.getElementById("title").value,
            red_odds: document.getElementById("red").value,
            black_odds: document.getElementById("black").value
        })
    });
    closeModal();
    alert("Событие создано");
    loadEvents();
}

function openChangeOddsModal(id, red, black) {
    showModal(`
        <h3>⚙️ Изменить коэффициенты</h3>
        <input id="new-red" type="number" step="0.1" value="${red}">
        <input id="new-black" type="number" step="0.1" value="${black}">
        <button class="admin" onclick="submitChangeOdds(${id})">Сохранить</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitChangeOdds(id) {
    await api(`/admin/events/${id}/odds`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            red_odds: document.getElementById("new-red").value,
            black_odds: document.getElementById("new-black").value
        })
    });
    closeModal();
    alert("Коэффициенты обновлены");
    loadEvents();
}

function openFinishModal(id) {
    showModal(`
        <button class="red" onclick="finishEvent(${id}, 'red')">🔴 Красные</button>
        <button class="black" onclick="finishEvent(${id}, 'black')">⚫ Чёрные</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function finishEvent(id, winner) {
    await api(`/admin/events/${id}/finish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ winner })
    });
    closeModal();
    alert("Событие завершено");
    document.getElementById(`event-${id}`)?.remove();
}

async function loadEvents() {
    const events = await api("/events");
    const container = document.getElementById("events");
    container.innerHTML = "";

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";
        card.id = `event-${e.id}`;

        card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center">
                <b>${e.title}</b>
                ${IS_ADMIN ? `<button onclick="openChangeOddsModal(${e.id}, ${e.red_odds}, ${e.black_odds})">⚙️</button>` : ""}
            </div>
            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>
            <button class="red">🔴 x${e.red_odds}</button>
            <button class="black">⚫ x${e.black_odds}</button>
            ${IS_ADMIN ? `<button class="admin" onclick="openFinishModal(${e.id})">Завершить</button>` : ""}
        `;
        container.appendChild(card);
    }
}

loadMe();
loadEvents();
setInterval(loadEvents, 2000);
