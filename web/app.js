// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// ✅ СНАЧАЛА получаем initData
const initData = tg.initData;

// 🔍 ЛОГ В КОНСОЛЬ (Telegram WebView)
console.log("Telegram initData:", initData);

// 🔍 СРАЗУ отправляем на сервер
fetch("/debug-init", {
    method: "POST",
    headers: {
        "Content-Type": "text/plain"
    },
    body: initData || "EMPTY_INIT_DATA"
});

// API на том же домене
const API_BASE = "";

if (!initData) {
    alert("❌ initData НЕ получен. Открой WebApp ТОЛЬКО через кнопку в Telegram.");
}

// Универсальный запрос
async function api(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: {
            "X-Telegram-Init-Data": initData,
            "Authorization": initData
        }
    });

    if (!res.ok) {
        throw new Error(await res.text());
    }

    return res.json();
}

async function loadMe() {
    const me = await api("/me");
    document.getElementById("balance").innerText =
        `💰 Баланс: ${me.balance}`;
}

async function loadEvents() {
    const events = await api("/events");
    const container = document.getElementById("events");
    container.innerHTML = "";

    if (!events.length) {
        container.innerHTML = `<div class="card">❌ Нет активных событий</div>`;
        return;
    }

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
            <div class="event-title">${e.title}</div>
            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>
            <button class="red">🔴 Красные ×${e.red_odds}</button>
            <button class="black">⚫ Черные ×${e.black_odds}</button>
        `;
        container.appendChild(card);
    }
}

(async () => {
    try {
        await loadMe();
        await loadEvents();
    } catch (e) {
        console.error("WEB ERROR:", e);
        alert("❌ Ошибка загрузки данных");
    }
})();
