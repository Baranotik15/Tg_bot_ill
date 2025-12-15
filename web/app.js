const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = "";

const authHeader = tg.initData; // получаем initData

console.log(authHeader);  // Логируем для проверки, что передается в запросе

async function api(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: {
            "Authorization": authHeader
        }
    });

    if (!res.ok) {
        throw new Error(await res.text());
    }

    return res.json();
}

async function loadMe() {
    try {
        const me = await api("/me");
        console.log(me);  // Логируем, что пришло с сервера
        document.getElementById("balance").innerText = `💰 Баланс: ${me.balance} баллов`;
    } catch (e) {
        console.error('Ошибка при загрузке данных', e);
        alert("Ошибка загрузки данных");
    }
}

async function loadEvents() {
    try {
        const events = await api("/events");
        const container = document.getElementById("events");
        container.innerHTML = "";

        if (events.length === 0) {
            container.innerHTML = `<div class="card">❌ Нет активных событий</div>`;
            return;
        }

        for (const e of events) {
            const card = document.createElement("div");
            card.className = "card";

            card.innerHTML = `
                <div class="event-title">${e.title}</div>
                <div>⏱ Осталось: ${Math.floor(e.time_left / 60)}:${String(e.time_left % 60).padStart(2, "0")}</div>

                <button class="red" onclick="placeBet(${e.id}, 'red', ${e.red_odds})">
                    🔴 Красные ×${e.red_odds}
                </button>

                <button class="black" onclick="placeBet(${e.id}, 'black', ${e.black_odds})">
                    ⚫ Черные ×${e.black_odds}
                </button>
            `;

            container.appendChild(card);
        }
    } catch (e) {
        console.error('Ошибка при загрузке событий', e);
        alert("Ошибка загрузки данных");
    }
}

function placeBet(eventId, team, odds) {
    const amount = prompt(`Введите сумму ставки (коэф ×${odds})`);
    if (!amount) return;

    tg.sendData(JSON.stringify({
        action: "bet",
        event_id: eventId,
        team: team,
        amount: Number(amount)
    }));

    alert("Ставка отправлена в бот");
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
