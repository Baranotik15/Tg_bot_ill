// Глобальные переменные для доступа из onclick
let IS_ADMIN = false;
let BALANCE = 0;
let modal, modalContent, HEADERS;

// Глобальные функции, которые будут определены после DOMContentLoaded
let api, showModal, loadEvents, loadMe;

// Глобальные функции для вызова из onclick в HTML
window.closeModal = function() {
    if (modal && modalContent) {
        modal.style.display = "none";
        modalContent.innerHTML = "";
    }
};

window.submitCreate = async function() {
    const title = document.getElementById("title")?.value.trim();
    const red = parseFloat(document.getElementById("red")?.value.replace(",", "."));
    const black = parseFloat(document.getElementById("black")?.value.replace(",", "."));

    if (!title || isNaN(red) || isNaN(black) || red <= 0 || black <= 0) {
        alert("Заполни все поля корректно");
        return;
    }

    if (!api) {
        alert("Система еще не загружена");
        return;
    }

    await api("/admin/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, red_odds: red, black_odds: black })
    });

    window.closeModal();
    if (loadEvents) loadEvents();
};

window.submitPromo = async function() {
    const code = document.getElementById("promo-code")?.value.trim();
    const amountRaw = document.getElementById("promo-amount")?.value.trim();
    const limitRaw = document.getElementById("promo-limit")?.value.trim();

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

    if (!api) {
        alert("Система еще не загружена");
        return;
    }

    await api("/admin/promocodes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, amount, limit })
    });

    window.closeModal();
    alert("✅ Промокод создан");
};

window.openBetModal = function(eventId, side, odds, title) {
    if (!showModal) {
        alert("Система еще не загружена");
        return;
    }
    showModal(`
        <b>🎯 Оформление ставки</b>

        <div style="margin-top:6px">🎲 ${title}</div>
        <div style="margin-top:6px">
            Команда: <b>${side === "red" ? "Красные 🔴" : "Черные ⚫"}</b>
        </div>
        <div style="margin-top:6px">Коэф: <b>x${odds}</b></div>
        <div style="margin-top:6px">Баланс: <b>${BALANCE}</b></div>

        <input id="bet-amount" type="text" placeholder="Введите сумму">

        <button class="admin" onclick="window.submitBet(${eventId}, '${side}')">Поставить</button>
        <button onclick="window.closeModal()">Отмена</button>
    `);
};

window.submitBet = async function(eventId, side) {
    const input = document.getElementById("bet-amount");
    const rawValue = input?.value.trim();

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

    if (!api) {
        alert("Система еще не загружена");
        return;
    }

    await api("/bet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, side, amount })
    });

    window.closeModal();
    if (loadMe) loadMe();
};

window.openOddsModal = function(eventId, redOdds, blackOdds) {
    if (!showModal) {
        alert("Система еще не загружена");
        return;
    }
    showModal(`
        <b>⚙️ Изменить коэффициенты</b>

        <input id="odds-red" type="text" placeholder="Коэф 🔴" value="${redOdds}">
        <input id="odds-black" type="text" placeholder="Коэф ⚫" value="${blackOdds}">

        <button class="admin" onclick="window.submitOdds(${eventId})">Сохранить</button>
        <button onclick="window.closeModal()">Отмена</button>
    `);
};

window.submitOdds = async function(eventId) {
    const red = parseFloat(document.getElementById("odds-red")?.value.replace(",", "."));
    const black = parseFloat(document.getElementById("odds-black")?.value.replace(",", "."));

    if (isNaN(red) || isNaN(black) || red <= 0 || black <= 0) {
        alert("Заполни все поля корректно");
        return;
    }

    if (!api) {
        alert("Система еще не загружена");
        return;
    }

    await api(`/admin/events/${eventId}/odds`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ red_odds: red, black_odds: black })
    });

    window.closeModal();
    if (loadEvents) loadEvents();
};

window.openFinishModal = function(eventId) {
    if (!showModal) {
        alert("Система еще не загружена");
        return;
    }
    showModal(`
        <b>🏁 Завершить событие</b>

        <div style="margin-top:6px">Выберите победителя:</div>

        <button class="red" onclick="window.submitFinish(${eventId}, 'red')">🔴 Красные</button>
        <button class="black" onclick="window.submitFinish(${eventId}, 'black')">⚫ Черные</button>
        <button onclick="window.closeModal()">Отмена</button>
    `);
};

window.submitFinish = async function(eventId, winner) {
    if (!confirm("Вы уверены, что хотите завершить событие?")) {
        return;
    }

    if (!api) {
        alert("Система еще не загружена");
        return;
    }

    await api(`/admin/events/${eventId}/finish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ winner })
    });

    window.closeModal();
    if (loadEvents) loadEvents();
};

window.submitRedeemPromo = async function() {
    const input = document.getElementById("redeem-promo-code");
    const btn = document.getElementById("redeem-btn");
    const code = input?.value.trim();

    if (!code) {
        alert("Введите промокод");
        return;
    }

    if (!api) {
        alert("Система еще не загружена");
        return;
    }

    if (btn) btn.disabled = true;

    try {
        const res = await api("/promocode/redeem", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code })
        });

        window.closeModal();
        alert(`🎉 Промокод применён! +${res.added} баллов`);
        if (loadMe) await loadMe();

    } catch (e) {
        alert(e.message || "Не удалось применить промокод");
    } finally {
        if (btn) btn.disabled = false;
    }
};

document.addEventListener("DOMContentLoaded", () => {

const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) throw new Error("No initData");

HEADERS = { "X-Telegram-Init-Data": initData };

modal = document.getElementById("modal");
modalContent = document.getElementById("modal-content");

api = async function(path, options = {}) {
    const res = await fetch(path, {
        ...options,
        credentials: "same-origin",
        headers: {
            ...HEADERS,
            ...(options.headers || {})
        }
    });

    if (!res.ok) {
        let msg = "Ошибка";
        try {
            const data = await res.json();
            msg = data.detail || msg;
        } catch (_) {}
        throw new Error(msg);
    }
    return res.json();
};

/* ---------------- MODAL ---------------- */

showModal = function(html) {
    if (modalContent && modal) {
        modalContent.innerHTML = html;
        modal.style.display = "block";
    }
};

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

loadMe = async function() {
    const me = await api("/me");
    IS_ADMIN = me.is_admin;
    BALANCE = me.balance;
    document.getElementById("balance").innerText = `💰 Баланс: ${BALANCE}`;
    renderAdminControls();
    renderPromoButton();
};

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

        <button class="admin" onclick="window.submitCreate()">Создать</button>
        <button onclick="window.closeModal()">Отмена</button>
    `);
}

/* ---------------- PROMOCODES ---------------- */

function openPromoModal() {
    showModal(`
        <b>🎟 Создание промокода</b>

        <input id="promo-code" type="text" placeholder="Код промокода">
        <input id="promo-amount" type="text" placeholder="Сколько баллов">
        <input id="promo-limit" type="text" placeholder="Количество использований">

        <button class="admin" onclick="window.submitPromo()">Создать</button>
        <button onclick="window.closeModal()">Отмена</button>
    `);
}

/* ---------------- BETTING ---------------- */

/* ---------------- EVENTS ---------------- */

loadEvents = async function() {
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

        const safeTitleEscaped = safeTitle.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
        card.innerHTML = `
            <div class="event-head">
                <b>${safeTitle}</b>
                ${IS_ADMIN ? `<button class="gear" onclick="window.openOddsModal(${e.id}, ${e.red_odds}, ${e.black_odds})">⚙️</button>` : ""}
            </div>

            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

            <button class="red bet-btn"
                onclick="window.openBetModal(${e.id}, 'red', ${e.red_odds}, '${safeTitleEscaped}')">
                🔴 x${e.red_odds}
            </button>

            <button class="black bet-btn"
                onclick="window.openBetModal(${e.id}, 'black', ${e.black_odds}, '${safeTitleEscaped}')">
                ⚫ x${e.black_odds}
            </button>

            ${IS_ADMIN ? `<button class="admin" onclick="window.openFinishModal(${e.id})">Завершить</button>` : ""}
        `;

        container.appendChild(card);
    }
}

/* ---------------- PROMO REDEEM ---------------- */

function openRedeemPromoModal() {
    showModal(`
        <b>🎁 Ввести промокод</b>

        <input id="redeem-promo-code" type="text" placeholder="Введите промокод">

        <button id="redeem-btn" class="promo" onclick="window.submitRedeemPromo()">Применить</button>
        <button onclick="window.closeModal()">Отмена</button>
    `);
}

/* ---------------- INIT ---------------- */

loadTop();
loadMe();
loadEvents();
setInterval(loadTop, 5000);
setInterval(loadMe, 3000);
setInterval(loadEvents, 3000);

});
