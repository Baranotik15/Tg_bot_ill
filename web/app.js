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
        headers: { ...HEADERS, ...(options.headers || {}) }
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

function showModal(html, focusId = null) {
    modalContent.innerHTML = html;
    modal.style.display = "block";
    setTimeout(() => {
        const el = focusId
            ? document.getElementById(focusId)
            : modalContent.querySelector("input");
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

modal.onclick = e => e.target === modal && closeModal();

async function loadMe() {
    const me = await api("/me");
    IS_ADMIN = me.is_admin;
    document.getElementById("balance").innerText = `💰 Баланс: ${me.balance}`;
}

async function placeBet(eventId, side, odds, title, balance) {
    showModal(`
        <b>${title}</b><br><br>
        🎯 Ставка на: <b>${side === "red" ? "Красных 🔴" : "Черных ⚫"}</b><br>
        📈 Коэффициент: <b>${odds}x</b><br><br>
        💳 Баланс: <b>${balance}</b><br><br>
        <input id="bet-amount" type="text" inputmode="numeric" placeholder="Введите сумму">
        <button class="admin" onclick="submitBet(${eventId}, '${side}')">Сделать ставку</button>
        <button onclick="closeModal()">Отмена</button>
    `, "bet-amount");
}

async function submitBet(eventId, side) {
    const amount = document.getElementById("bet-amount").value.trim();
    if (!amount || isNaN(amount) || Number(amount) <= 0) {
        alert("Введите корректную сумму");
        return;
    }

    await api("/bet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, side })
    });

    closeModal();
    tg.close();
}

async function loadEvents() {
    const events = await api("/events");
    const me = await api("/me");

    const container = document.getElementById("events");
    container.innerHTML = "";

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <b>${e.title}</b>
            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

            <button class="red bet-btn">🔴 x${e.red_odds}</button>
            <button class="black bet-btn">⚫ x${e.black_odds}</button>
        `;

        const [redBtn, blackBtn] = card.querySelectorAll(".bet-btn");

        redBtn.onclick = () =>
            placeBet(e.id, "red", e.red_odds, e.title, me.balance);

        blackBtn.onclick = () =>
            placeBet(e.id, "black", e.black_odds, e.title, me.balance);

        container.appendChild(card);
    }
}

loadMe();
loadEvents();
setInterval(loadEvents, 2000);
