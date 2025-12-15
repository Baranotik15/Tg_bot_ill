const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) {
    throw new Error("initData empty");
}

const API_HEADERS = {
    "X-Telegram-Init-Data": initData
};

let eventsCache = new Map();
let timerInterval = null;

async function api(path) {
    const res = await fetch(path, {
        headers: API_HEADERS,
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

    eventsCache.clear();

    for (const e of events) {
        eventsCache.set(e.id, {
            ...e,
            time_left: e.time_left
        });

        const card = document.createElement("div");
        card.className = "card";
        card.id = `event-${e.id}`;
        card.innerHTML = `
            <div class="event-title">${e.title}</div>
            <div class="time" id="time-${e.id}"></div>
            <button class="red">🔴 Красные ×${e.red_odds}</button>
            <button class="black">⚫ Черные ×${e.black_odds}</button>
        `;

        container.appendChild(card);
    }

    startTimer();
}

function startTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
    }

    timerInterval = setInterval(() => {
        for (const [id, e] of eventsCache.entries()) {
            if (e.time_left <= 0) {
                document.getElementById(`event-${id}`)?.remove();
                eventsCache.delete(id);
                continue;
            }

            e.time_left -= 1;

            const min = Math.floor(e.time_left / 60);
            const sec = String(e.time_left % 60).padStart(2, "0");
            const el = document.getElementById(`time-${id}`);

            if (el) {
                el.innerText = `⏱ ${min}:${sec}`;
            }
        }
    }, 1000);
}

function startPolling() {
    loadMe();
    loadEvents();

    setInterval(loadMe, 10000);
    setInterval(loadEvents, 10000);
}

startPolling();
