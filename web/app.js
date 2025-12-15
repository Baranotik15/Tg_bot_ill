const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) {
    throw new Error("initData empty");
}

const HEADERS = {
    "X-Telegram-Init-Data": initData
};

let eventsCache = new Map();
let timerInterval = null;

async function api(path) {
    const res = await fetch(path, {
        headers: HEADERS,
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

    for (const e of events) {
        const cached = eventsCache.get(e.id);

        if (!cached) {
            createEventCard(e);
            eventsCache.set(e.id, { ...e });
        } else {
            cached.red_odds = e.red_odds;
            cached.black_odds = e.black_odds;
            cached.time_left = Math.min(cached.time_left, e.time_left);

            updateEventUI(e.id, cached);
        }
    }
}

function createEventCard(e) {
    const container = document.getElementById("events");

    const card = document.createElement("div");
    card.className = "card";
    card.id = `event-${e.id}`;

    card.innerHTML = `
        <div class="event-title">${e.title}</div>
        <div class="time" id="time-${e.id}"></div>
        <button class="red" id="red-${e.id}">🔴 Красные ×${e.red_odds}</button>
        <button class="black" id="black-${e.id}">⚫ Черные ×${e.black_odds}</button>
    `;

    container.appendChild(card);
}

function updateEventUI(id, e) {
    document.getElementById(`red-${id}`).innerText = `🔴 Красные ×${e.red_odds}`;
    document.getElementById(`black-${id}`).innerText = `⚫ Черные ×${e.black_odds}`;
}

function startTimer() {
    if (timerInterval) return;

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

function startFastPolling() {
    loadMe();
    loadEvents();
    startTimer();

    setInterval(loadMe, 2000);
    setInterval(loadEvents, 2000);
}

startFastPolling();
