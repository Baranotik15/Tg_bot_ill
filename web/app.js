// Telegram WebApp init
const tg = window.Telegram.WebApp;
tg.expand();

// API находится на том же домене
const API_BASE = "";

// Берём initData
const initData = tg.initData || "";

// Жёсткая проверка: WebApp открыт НЕ из Telegram
if (!initData) {
    alert("❌ WebApp открыт не из Telegram.\nОткрой через кнопку в боте.");
    throw new Error("No Telegram initData");
}

// Универсальный API-запрос
async function api(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "GET",
        headers: {
            "X-Telegram-Init-Data": initData
        }
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
    }

    return res.json();
}

// Загрузка пользователя
async function loadMe() {
    const me = await api("/me");
    document.getElementById("balance").innerText =
        `💰 Баланс: ${me.balance}`;
}

// Загрузка событий
async function loadEvents() {
    const events = await api("/events");
    const container = document.getElementById("events");
    container.innerHTML = "";

    if (!events || events.length === 0) {
        container.innerHTML =
            `<div class="card">❌ Нет активных событий</div>`;
        return;
    }

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";

        const minutes = Math.floor(e.time_left / 60);
        const seconds = String(e.time_left % 60).padStart(2, "0");

        card.innerHTML = `
            <div class="event-title">${e.title}</div>
            <div>⏱ Осталось: ${minutes}:${seconds}</div>

            <button class="red" onclick="placeBet(${e.id}, 'red', ${e.red_odds})">
                🔴 Красные ×${e.red_odds}
            </button>

            <button class="black" onclick="placeBet(${e.id}, 'black', ${e.black_odds})">
                ⚫ Черные ×${e.black_odds}
            </button>
        `;

        container.appendChild(card);
    }
}

// Отправка ставки в бот
function placeBet(eventId, team, odds) {
    const amount = prompt(`Введите сумму ставки (коэф ×${odds})`);
    if (!amount) return;

    tg.sendData(JSON.stringify({
        action: "bet",
        event_id: eventId,
        team: team,
        amount: Number(amount)
    }));

    alert("✅ Ставка отправлена в бот");
}

// Старт приложения
(async () => {
    try {
        await loadMe();
        await loadEvents();
    } catch (err) {
        console.error(err);
        alert("❌ Ошибка загрузки данных.\nСмотри логи сервера.");
    }
})();
