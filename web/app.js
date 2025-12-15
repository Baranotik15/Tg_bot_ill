const tg = window.Telegram.WebApp;
tg.expand();

// API на том же домене
const API_BASE = "";

const initData = tg.initData;

async function api(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "GET",
        headers: {
            "X-Telegram-Init-Data": initData
        }
    });

    if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
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
        container.innerHTML =
            `<div class="card">❌ Нет активных событий</div>`;
        return;
    }

    for (const e of events) {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <div class="event-title">${e.title}</div>
            <div>⏱ ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

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

function placeBet(eventId, team, odds) {
    const amount = prompt(`Введите сумму (×${odds})`);
    if (!amount) return;

    tg.sendData(JSON.stringify({
        action: "bet",
        event_id: eventId,
        team,
        amount: Number(amount)
    }));

    alert("Ставка отправлена");
}

(async () => {
    try {
        await loadMe();
        await loadEvents();
    } catch (e) {
        alert("Ошибка загрузки данных");
        console.error(e);
    }
})();
