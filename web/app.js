const tg = window.Telegram.WebApp;
tg.ready();

const initData = tg.initData;

async function loadMe() {
  const res = await fetch("/api/me", {
    headers: {
      "Authorization": initData
    }
  });
  const data = await res.json();
  document.getElementById("me").innerText =
    `Баланс: ${data.balance}`;
}

async function loadEvents() {
  const res = await fetch("/api/events");
  const events = await res.json();

  const ul = document.getElementById("events");
  ul.innerHTML = "";

  events.forEach(e => {
    const li = document.createElement("li");
    li.innerText = `${e.title} 🔴x${e.red_odds} ⚫x${e.black_odds}`;
    ul.appendChild(li);
  });
}

loadMe();
loadEvents();
