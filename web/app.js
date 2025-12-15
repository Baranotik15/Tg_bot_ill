const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) throw new Error("No initData");

const HEADERS = { "X-Telegram-Init-Data": initData };

let IS_ADMIN = false;

const modal = document.getElementById("modal");
const modalContent = document.getElementById("modal-content");

/* ================= API ================= */

async function api(path, options = {}) {
    const res = await fetch(path, {
        credentials: "same-origin",
        headers: {
            ...HEADERS,
            ...(options.headers || {})
        },
        ...options
    });

    if (!res.ok) {
        throw new Error(await res.text());
    }
    return res.json();
}

/* ================= USER ================= */

async function loadMe() {
    try {
        const me = await api("/me");
        IS_ADMIN = me.is_admin;
        document.getElementById("balance").innerText = `💰 Баланс: ${me.balance}`;
        renderAdminControls();
    } catch (e) {
        console.error(e);
    }
}

/* ================= ADMIN UI ================= */

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

/* ================= MODAL ================= */

function showModal(html) {
    modalContent.innerHTML = html;
    modal.style.display = "block";
}

function closeModal() {
    modal.style.display = "none";
    modalContent.innerHTML = "";
}

/* ================= CREATE EVENT ================= */

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
    const title = document.getElementById("title").value.trim();
    const red = Number(document.getElementById("red").value);
    const black = Number(document.getElementById("black").value);

    if (!title || red <= 0 || black <= 0) {
        alert("Заполни все поля корректно");
        return;
    }

    try {
        await api("/admin/events", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title,
                red_odds: red,
                black_odds: black
            })
        });

        closeModal();
        alert("✅ Событие успешно создано");
        loadEvents();

    } catch (e) {
        alert("❌ Ошибка создания события");
        console.error(e);
    }
}

/* ================= FINISH EVENT ================= */

function openFinishModal(id) {
    showModal(`
        <button class="red" onclick="finishEvent(${id}, 'red')">🔴 Красные</button>
        <button class="black" onclick="finishEvent(${id}, 'black')">⚫ Чёрные</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function finishEvent(id, winner) {
    try {
        await api(`/admin/events/${id}/finish`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ winner })
        });

        closeModal();
        alert("✅ Событие успешно завершено");
        document.getElementById(`event-${id}`)?.remove();

    } catch (e) {
        alert("❌ Ошибка завершения события");
        console.error(e);
    }
}

/* ================= EVENTS LIST ================= */

async function loadEvents() {
    try {
        const events = await api("/events");
        const container = document.getElementById("events");
        container.innerHTML = "";

        for (const e of events) {
            const card = document.createElement("div");
            card.className = "card";
            card.id = `event-${e.id}`;

            card.innerHTML = `
                <b>${e.title}</b>
                <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>
                <button class="red" disabled>🔴 x${e.red_odds}</button>
                <button class="black" disabled>⚫ x${e.black_odds}</button>
                ${IS_ADMIN ? `<button class="admin" onclick="openFinishModal(${e.id})">Завершить</button>` : ""}
            `;

            container.appendChild(card);
        }
    } catch (e) {
        console.error(e);
    }
}

/* ================= INIT ================= */

loadMe();
loadEvents();

setInterval(loadMe, 2000);
setInterval(loadEvents, 2000);
