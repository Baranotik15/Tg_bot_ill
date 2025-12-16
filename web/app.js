const tg = window.Telegram.WebApp;
tg.expand();
if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();

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

function showModal(html, focusId = null) {
    modalContent.innerHTML = html;
    modal.style.display = "block";

    setTimeout(() => {
        const el = focusId ? document.getElementById(focusId) : modalContent.querySelector("input,textarea");
        if (el) {
            el.focus();
            el.click();
        }
    }, 80);
}

function closeModal() {
    modal.style.display = "none";
    modalContent.innerHTML = "";
}

modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
});

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

function openCreateModal() {
    showModal(`
        <input id="title" type="text" placeholder="Название" autocomplete="off">
        <input id="red" type="text" inputmode="decimal" pattern="[0-9]*[.,]?[0-9]*" placeholder="Коэф 🔴" autocomplete="off" enterkeyhint="next">
        <input id="black" type="text" inputmode="decimal" pattern="[0-9]*[.,]?[0-9]*" placeholder="Коэф ⚫" autocomplete="off" enterkeyhint="done">
        <button class="admin" onclick="submitCreate()">Создать</button>
        <button onclick="closeModal()">Отмена</button>
    `, "title");
}

async function submitCreate() {
    const title = document.getElementById("title").value.trim();
    const red = parseFloat(document.getElementById("red").value.replace(",", "."));
    const black = parseFloat(document.getElementById("black").value.replace(",", "."));

    if (!title || isNaN(red) || isNaN(black) || red <= 0 || black <= 0) {
        alert("Заполни все поля корректно");
        return;
    }

    await api("/admin/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, red_odds: red, black_odds: black })
    });

    closeModal();
    loadEvents();
}

function openOddsModal(id, red, black) {
    showModal(`
        <input id="red-odds" type="text" inputmode="decimal" pattern="[0-9]*[.,]?[0-9]*" value="${red}" autocomplete="off" enterkeyhint="next">
        <input id="black-odds" type="text" inputmode="decimal" pattern="[0-9]*[.,]?[0-9]*" value="${black}" autocomplete="off" enterkeyhint="done">
        <button class="admin" onclick="submitOdds(${id})">Сохранить</button>
        <button onclick="closeModal()">Отмена</button>
    `, "red-odds");
}

async function submitOdds(id) {
    const red = parseFloat(document.getElementById("red-odds").value.replace(",", "."));
    const black = parseFloat(document.getElementById("black-odds").value.replace(",", "."));

    if (isNaN(red) || isNaN(black) || red <= 0 || black <= 0) {
        alert("Введите корректные коэффициенты");
        return;
    }

    await api(`/admin/events/${id}/odds`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ red_odds: red, black_odds: black })
    });

    closeModal();
    loadEvents();
}

function openFinishModal(id) {
    showModal(`
        <button class="red" onclick="finishEvent(${id}, 'red')">🔴 Красные</button>
        <button class="black" onclick="finishEvent(${id}, 'black')">⚫ Черные</button>
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
            <div class="event-head" style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
                <b>${e.title}</b>
                ${IS_ADMIN ? `<button class="gear" style="width:auto; padding:6px 10px;" onclick="openOddsModal(${e.id}, ${e.red_odds}, ${e.black_odds})">⚙️</button>` : ""}
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
setInterval(loadMe, 2000);
setInterval(loadEvents, 2000);
