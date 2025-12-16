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

function showModal(html) {
    modalContent.innerHTML = html;
    modal.style.display = "block";
}

function closeModal() {
    modal.style.display = "none";
    modalContent.innerHTML = "";
}

async function loadMe() {
    const me = await api("/me");
    IS_ADMIN = me.is_admin;
    BALANCE = me.balance;
    document.getElementById("balance").innerText = `💰 Баланс: ${BALANCE}`;
}

function openBetModal(eventId, side, odds) {
    showModal(`
        <b>🎯 Ставка на ${side === "red" ? "Красных 🔴" : "Черных ⚫"}</b>
        <div style="margin-top:8px">Коэф: x${odds}</div>
        <div style="margin-top:8px">Ваш баланс: ${BALANCE}</div>

        <input id="bet-amount" type="text" inputmode="numeric" placeholder="Введите сумму">
        <button class="admin" onclick="submitBet(${eventId}, '${side}')">Поставить</button>
        <button onclick="closeModal()">Отмена</button>
    `);
}

async function submitBet(eventId, side) {
    const amount = parseInt(document.getElementById("bet-amount").value);

    if (!amount || amount <= 0) {
        alert("Введите корректную сумму");
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

async function loadEvents() {
    const events = await api("/events");
    const container = document.getElementById("events");
    container.innerHTML = "";

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <b>${e.title}</b>
            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

            <button class="red bet-btn"
                onclick="openBetModal(${e.id}, 'red', ${e.red_odds})">
                🔴 x${e.red_odds}
            </button>

            <button class="black bet-btn"
                onclick="openBetModal(${e.id}, 'black', ${e.black_odds})">
                ⚫ x${e.black_odds}
            </button>
        `;

        container.appendChild(card);
    }
}

loadMe();
loadEvents();
setInterval(loadMe, 3000);
setInterval(loadEvents, 3000);
