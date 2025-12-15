// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// DEBUG: отправляем initData на сервер сразу
fetch("/debug-init", {
    method: "POST",
    headers: {
        "Content-Type": "text/plain"
    },
    body: initData || "EMPTY_INIT_DATA"
});

// API находится на том же домене
const API_BASE = "";

// initData — ЭТО КЛЮЧЕВО
const initData = tg.initData;

if (!initData) {
    alert("❌ initData не получен. Открой WebApp ТОЛЬКО из Telegram.");
    console.error("initData is empty");
}

// Универсальный запрос к API
async function api(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "GET",
        headers: {
            // Дублируем в два заголовка: некоторые прокси режут кастомные X-*
            "X-Telegram-Init-Data": initData,
            "Authorization": initData
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

    const balanceEl = document.getElementById("balance");
    if (!balanceEl) {
        throw new Error("Element #balance not found");
    }

    balanceEl.innerText = `💰 Баланс: ${me.balance}`;
}

// Загрузка событий
async function loadEvents() {
    const events = await api("/events");
    const container = document.getElementById("events");

    if (!container) {
        throw new Error("Element #events not found");
    }

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
            <div>⏱ Осталось: ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

            <button class="red">
                🔴 Красные ×${e.red_odds}
            </button>

            <button class="black">
                ⚫ Черные ×${e.black_odds}
            </button>
        `;

        // обработчики
        card.querySelector(".red").onclick = () =>
            placeBet(e.id, "red", e.red_odds);

        card.querySelector(".black").onclick = () =>
            placeBet(e.id, "black", e.black_odds);

        container.appendChild(card);
    }
}

// Отправка ставки в бота
function placeBet(eventId, team, odds) {
    const amount = prompt(`Введите сумму ставки (×${odds})`);
    if (!amount) return;

    tg.sendData(JSON.stringify({
        action: "bet",
        event_id: eventId,
        team: team,
        amount: Number(amount)
    }));

    alert("✅ Ставка отправлена в бот");
}

// Точка входа
(async () => {
    try {
        console.log("Telegram initData:", initData);

        await loadMe();
        await loadEvents();
    } catch (err) {
        console.error("WEB ERROR:", err);
        alert("❌ Ошибка загрузки данных. Смотри логи сервера.");
    }
})();
