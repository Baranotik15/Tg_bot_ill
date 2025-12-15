// === Telegram WebApp init ===
const tg = window.Telegram.WebApp;
tg.expand();

// === API base ===
// ВАЖНО: оставляем пустым, чтобы запросы шли на тот же домен
const API_BASE = "";

// === Telegram auth data ===
const AUTH_DATA = tg.initData;

// === UI helpers ===
const balanceEl = document.getElementById("balance");
const eventsEl = document.getElementById("events");

// === Проверка, что WebApp открыт корректно ===
if (!AUTH_DATA) {
    balanceEl.innerText = "❌ Ошибка: WebApp открыт не из Telegram";
    alert("Открой WebApp ТОЛЬКО через кнопку в боте");
    throw new Error("tg.initData is empty");
}

// === Универсальный API вызов ===
async function api(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "GET",
        headers: {
            "Authorization": AUTH_DATA,
            "Content-Type": "application/json"
        }
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
    }

    return res.json();
}

// === Загрузка профиля ===
async function loadMe() {
    const me = await api("/me");
    balanceEl.innerText = `💰 Баланс: ${me.balance} баллов`;
}

// === Загрузка событий ===
async function loadEvents() {
    const events = await api("/events");
    eventsEl.innerHTML = "";

    if (!events || events.length === 0) {
        eventsEl.innerHTML =
            `<div class="card">❌ Нет активных событий</div>`;
        return;
    }

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <div class="event-title">${e.title}</div>
            <div>⏱ Осталось: ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

            <button class="red">
                🔴 Красные ×${e.red_odds}
            </button>

            <button class="black">
                ⚫ Черные ×${e.black_odds}
            </button>
        `;

        const [redBtn, blackBtn] = card.querySelectorAll("button");

        redBtn.onclick = () => placeBet(e.id, "red", e.red_odds);
        blackBtn.onclick = () => placeBet(e.id, "black", e.black_odds);

        eventsEl.appendChild(card);
    }
}

// === Отправка ставки в бота ===
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

// === Старт приложения ===
(async () => {
    try {
        await loadMe();
        await loadEvents();
    } catch (err) {
        console.error(err);
        balanceEl.innerText = "❌ Ошибка загрузки данных";
        alert("Ошибка загрузки данных");
    }
})();
