const tg = window.Telegram.WebApp;
tg.expand();

const initData = tg.initData;
if (!initData) {
    throw new Error("initData empty");
}

const HEADERS = {
    "X-Telegram-Init-Data": initData
};

let IS_ADMIN = false;
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
    IS_ADMIN = me.is_admin;
    document.getElementById("balance").innerText = `💰 Баланс: ${me.balance}`;
    renderAdminControls();
}

function renderAdminControls() {
    const container = document.getElementById("admin-controls");
    if (!container) return;

    container.innerHTML = "";

    if (!IS_ADMIN) return;

    const btn = document.createElement("button");
    btn.innerText = "➕ Создать событие";
    btn.onclick = createEvent;
    container.appendChild(btn);
}

async function createEvent() {
    const res = await fetch("/admin/events", {
        method: "POST",
        headers: HEADERS,
        credentials: "same-origin"
    });

    if (!res.ok) {
        throw new Error(await res.text());
    }

    await loadEvents();
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
    const red = document.getElementById(`red-${id}`);
    const black = document.getElementById(`black-${id}`);

    if (red) red.innerText = `🔴 Красные ×${e.red_odds}`;
    if (black) black.innerText = `⚫ Черные ×${e.black_odds}`;
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

            if (el) el.innerText = `⏱ ${min}:${sec}`;
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
