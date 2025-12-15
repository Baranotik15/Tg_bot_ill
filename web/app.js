const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;

if (!initData) {
    alert("Открой WebApp через кнопку в Telegram");
    throw new Error("initData empty");
}

async function api(path) {
    const res = await fetch(path, {
        method: "GET",
        headers: {
            "X-Telegram-Init-Data": initData
        },
        credentials: "same-origin"
    });

    if (!res.ok) {
        throw new Error(await res.text());
    }
    return res.json();
}

async function loadMe() {
    const me = await api("/me");
    document.getElementById("balance").innerText = `💰 Баланс: ${me.balance}`;
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
        console.error(e);
        alert("Ошибка загрузки данных");
    }
})();
