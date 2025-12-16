document.addEventListener("DOMContentLoaded", () => {

const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) throw new Error("No initData");

const HEADERS = { "X-Telegram-Init-Data": initData };

let IS_ADMIN = false;
let BALANCE = 0;

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

/* ---------------- MODAL ---------------- */

function showModal(html) {
    modalContent.innerHTML = html;
    modal.style.display = "block";
}

function closeModal() {
    modal.style.display = "none";
    modalContent.innerHTML = "";
}

/* ---------------- PROMO BUTTON ---------------- */

function renderPromoButton() {
    if (document.getElementById("redeem-promo-btn")) return;

    const container = document.querySelector(".container");
    if (!container) return;

    const btn = document.createElement("button");
    btn.id = "redeem-promo-btn";
    btn.className = "promo";
    btn.innerText = "🎁 Ввести промокод";
    btn.onclick = openRedeemPromoModal;

    const balanceCard = document.getElementById("balance")?.parentElement;
    if (balanceCard) {
        container.insertBefore(btn, balanceCard);
    } else {
        container.appendChild(btn);
    }
}

/* ---------------- USER ---------------- */

async function loadMe() {
    const me = await api("/me");
    IS_ADMIN = me.is_admin;
    BALANCE = me.balance;
    document.getElementById("balance").innerText = `💰 Баланс: ${BALANCE}`;
    renderAdminControls();
    renderPromoButton();
}

/* ---------------- TOP ---------------- */

async function loadTop() {
    const top = await api("/top");
    const el = document.getElementById("top-list");
    if (!el) return;

    if (!top || top.length === 0) {
        el.innerText = "Пока пусто 😔";
        return;
    }

    const medals = ["🥇", "🥈", "🥉", "🔹", "🔹"];

    el.innerHTML = top.map((u, i) => `
        <div class="top-row">
            <div class="top-rank">${medals[i] || "🔹"}</div>
            <div class="top-name">${u.username}</div>
            <div class="top-score"><b>${u.balance}</b></div>
        </div>
    `).join("");
}

/* ---------------- ADMIN ---------------- */

function renderAdminControls() {
    const c = document.getElementById("admin-controls");
    c.innerHTML = "";
    if (!IS_ADMIN) return;

    const row = document.createElement("div");
    row.style.display = "grid";
    row.style.gridTemplateColumns = "1fr 1fr";
    row.style.gap = "10px";

    const btnEvent = document.createElement("button");
    btnEvent.className = "admin";
    btnEvent.innerText = "➕ Создать событие";
    btnEvent.onclick = openCreateModal;

    const btnPromo = document.createElement("button");
    btnPromo.className = "admin";
    btnPromo.innerText = "🎟 Создать промокод";
    btnPromo.onclick = openPromoModal;

    row.appendChild(btnEvent);
    row.appendChild(btnPromo);
    c.appendChild(row);
}

function openCreateModal() {
    showModal(`
        <b>➕ Новое событие</b>

        <input id="title" type="text" placeholder="Название события">
        <input id="red" type="text" placeholder="Коэф 🔴">
        <input id="black" type="text" placeholder="Коэф ⚫">

        <button class="admin" onclick="submitCreate()">Создать</button>
        <button onclick="closeModal()">Отмена</button>
    `);
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

/* ---------------- PROMOCODES ---------------- */

function openPromoModal() {
    showModal(`
        <b>🎟 Создание промокода</b>

        <input id="promo-code" type="text" placeholder="Код промокода">
        <input id="promo-amount" type="text" placeholder="Сколько баллов">
        <input id="promo-limit" type="text" placeholder="Количество использований">

        <button class="admin" onclick="submitPromo()">Создать</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitPromo() {
    const code = document.getElementById("promo-code").value.trim();
    const amountRaw = document.getElementById("promo-amount").value.trim();
    const limitRaw = document.getElementById("promo-limit").value.trim();

    if (!code || !/^\d+$/.test(amountRaw) || !/^\d+$/.test(limitRaw)) {
        alert("Заполни все поля корректно");
        return;
    }

    const amount = Number(amountRaw);
    const limit = Number(limitRaw);

    if (amount <= 0 || limit <= 0) {
        alert("Значения должны быть больше 0");
        return;
    }

    await api("/admin/promocodes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, amount, limit })
    });

    closeModal();
    alert("✅ Промокод создан");
}

/* ---------------- BETTING ---------------- */

function openBetModal(eventId, side, odds, title) {
    showModal(`
        <b>🎯 Оформление ставки</b>

        <div style="margin-top:6px">🎲 ${title}</div>
        <div style="margin-top:6px">
            Команда: <b>${side === "red" ? "Красные 🔴" : "Черные ⚫"}</b>
        </div>
        <div style="margin-top:6px">Коэф: <b>x${odds}</b></div>
        <div style="margin-top:6px">Баланс: <b>${BALANCE}</b></div>

        <input id="bet-amount" type="text" placeholder="Введите сумму">

        <button class="admin" onclick="submitBet(${eventId}, '${side}')">Поставить</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitBet(eventId, side) {
    const input = document.getElementById("bet-amount");
    const rawValue = input.value.trim();

    if (rawValue === "") {
        alert("Введите сумму ставки");
        return;
    }

    if (!/^\d+$/.test(rawValue)) {
        alert("Сумма должна быть числом");
        return;
    }

    const amount = Number(rawValue);

    if (amount <= 0) {
        alert("Сумма должна быть больше 0");
        return;
    }

    if (amount > BALANCE) {
        alert("Недостаточно баллов");
        return;
    }

    await api("/bet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, side, amount })
    });

    closeModal();
    loadMe();
}

/* ---------------- EVENTS ---------------- */

async function loadEvents() {
    const events = await api("/events");
    const container = document.getElementById("events");
    const emptyState = document.getElementById("empty-state");

    container.innerHTML = "";

    if (events.length === 0) {
        emptyState.style.display = "block";
        container.style.display = "none";
        return;
    }

    emptyState.style.display = "none";
    container.style.display = "block";

    for (const e of events) {
        const safeTitle = e.title.replace(/'/g, "&#39;");
        const card = document.createElement("div");
        card.className = "card";
        card.id = `event-${e.id}`;

        card.innerHTML = `
            <div class="event-head">
                <b>${safeTitle}</b>
                ${IS_ADMIN ? `<button class="gear" onclick="openOddsModal(${e.id}, ${e.red_odds}, ${e.black_odds})">⚙️</button>` : ""}
            </div>

            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

            <button class="red bet-btn"
                onclick="openBetModal(${e.id}, 'red', ${e.red_odds}, '${safeTitle}')">
                🔴 x${e.red_odds}
            </button>

            <button class="black bet-btn"
                onclick="openBetModal(${e.id}, 'black', ${e.black_odds}, '${safeTitle}')">
                ⚫ x${e.black_odds}
            </button>

            ${IS_ADMIN ? `<button class="admin" onclick="openFinishModal(${e.id})">Завершить</button>` : ""}
        `;

        container.appendChild(card);
    }
}

/* ---------------- PROMO REDEEM ---------------- */

function openRedeemPromoModal() {
    showModal(`
        <b>🎁 Ввести промокод</b>

        <input id="redeem-promo-code" type="text" placeholder="Введите промокод">

        <button class="promo" onclick="submitRedeemPromo()">Применить</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitRedeemPromo() {
    const input = document.getElementById("redeem-promo-code");
    const code = input.value.trim();

    if (!code) {
        alert("Введите промокод");
        return;
    }

    try {
        const res = await api("/promocode/redeem", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code })
        });

        closeModal();
        alert(`🎉 Промокод применён! +${res.added} баллов`);
        await loadMe();

    } catch (e) {
        alert(e.message.replace(/^Error:\s*/, "") || "Не удалось применить промокод");
    }
}

/* ---------------- INIT ---------------- */

loadTop();
loadMe();
loadEvents();
setInterval(loadTop, 5000);
setInterval(loadMe, 3000);
setInterval(loadEvents, 3000);

});
