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
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function loadMe() {
    const me = await api("/me");
    IS_ADMIN = me.is_admin;
    document.getElementById("balance").innerText = `💰 Баланс: ${me.balance}`;
    renderAdminControls();
}

function renderAdminControls() {
    const c = document.getElementById("admin-controls");
    c.innerHTML = "";
    if (!IS_ADMIN) return;
    const b = document.createElement("button");
    b.innerText = "➕ Создать событие";
    b.onclick = openModal;
    c.appendChild(b);
}

function openModal() {
    document.getElementById("modal").style.display = "block";
}

function closeModal() {
    document.getElementById("modal").style.display = "none";
}

async function submitCreateEvent() {
    const title = document.getElementById("event-title").value.trim();
    const red = Number(document.getElementById("red-odds").value);
    const black = Number(document.getElementById("black-odds").value);

    if (!title || red <= 0 || black <= 0) return;

    await fetch("/admin/events", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...HEADERS
        },
        credentials: "same-origin",
        body: JSON.stringify({
            title: title,
            red_odds: red,
            black_odds: black
        })
    });

    closeModal();
    loadEvents();
}

async function loadEvents() {
    const events = await api("/events");

    for (const e of events) {
        if (!eventsCache.has(e.id)) {
            createEventCard(e);
            eventsCache.set(e.id, { ...e });
        } else {
            const c = eventsCache.get(e.id);
            c.red_odds = e.red_odds;
            c.black_odds = e.black_odds;
            c.time_left = Math.min(c.time_left, e.time_left);
            updateEventUI(e.id, c);
        }
    }
}

function createEventCard(e) {
    const c = document.getElementById("events");
    const card = document.createElement("div");
    card.className = "card";
    card.id = `event-${e.id}`;
    card.innerHTML = `
        <div class="event-title">${e.title}</div>
        <div id="time-${e.id}"></div>
        <button class="red" id="red-${e.id}">🔴 ×${e.red_odds}</button>
        <button class="black" id="black-${e.id}">⚫ ×${e.black_odds}</button>
    `;
    c.appendChild(card);
}

function updateEventUI(id, e) {
    document.getElementById(`red-${id}`).innerText = `🔴 ×${e.red_odds}`;
    document.getElementById(`black-${id}`).innerText = `⚫ ×${e.black_odds}`;
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
            const m = Math.floor(e.time_left / 60);
            const s = String(e.time_left % 60).padStart(2, "0");
            document.getElementById(`time-${id}`).innerText = `⏱ ${m}:${s}`;
        }
    }, 1000);
}

function start() {
    loadMe();
    loadEvents();
    startTimer();
    setInterval(loadMe, 2000);
    setInterval(loadEvents, 2000);
}

start();
