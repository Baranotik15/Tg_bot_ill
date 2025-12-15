// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// если API и сайт на одном домене — оставляем пустым
const API_BASE = "";

// Telegram initData (то, что проверяется на бэке)
const initData = tg.initData;

// Универсальная функция API
async function api(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: options.method || "GET",
        headers: {
            "Content-Type": "application/json",
            "X-Telegram-Init-Data": initData,
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
    }

    return res.json();
}

// Загрузка данных пользователя
async function loadMe() {
    const me = await api("/me");
    document.getElementById("balance").innerText =
        `💰 Баланс: ${me.balance} баллов`;
}

// Загрузка активных событий
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

        card.innerHTML = `
            <div class="event-title">${e.title}</div>
            <div>
                ⏱ Осталось: ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}
            </div>

            <button class="red"
                onclick="placeBet(${e.id}, 'red', ${e.red_odds})">
                🔴 Красные ×${e.red_odds}
            </button>

            <button class="black"
                onclick="placeBet(${e.id}, 'black', ${e.black_odds})">
                ⚫ Черные ×${e.black_odds}
            </button>
        `;

        container.appendChild(card);
    }
}

// Отправка ставки в бота
function placeBet(eventId, team, odds) {
    const amount = prompt(`Введите сумму ставки (коэф ×${odds})`);
    if (!amount || isNaN(amount) || Number(amount) <= 0) return;

    tg.sendData(JSON.stringify({
        action: "bet",
        event_id: eventId,
        team: team,
        amount: Number(amount),
    }));

    tg.showAlert("Ставка отправлена в бот");
}

(async () => {
    try {
        await loadMe();
        await loadEvents();
    } catch (err) {
        console.error("WebApp error:", err);
        tg.showAlert("Ошибка загрузки данных");
    }
})();
