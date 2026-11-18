// Fill the Minecraft server status boxes (status box on the Minecraft page, card on
// the home page) with live data from the mcstatus.io API: state, players and version.
// Refreshed every 60 seconds while the page is visible; the API caches its answers
// for 60 seconds as well. Also handles the buttons that copy the server address.
(() => {
  const API = "https://api.mcstatus.io/v2/status/java/";
  const REFRESH_INTERVAL = 60 * 1000;
  const COPY_FEEDBACK_DURATION = 2 * 1000;
  const EMPTY = "–";

  const boxes = [...document.querySelectorAll("[data-mc-status]")];
  const addresses = [...new Set(boxes.map((box) => box.dataset.mcStatus))];
  let lastRefresh = 0;

  function setField(box, field, value) {
    for (const element of box.querySelectorAll(`[data-mc-field="${field}"]`)) {
      element.textContent = value;
    }
  }

  // state: "online", "offline" or "unknown" (status not loaded)
  function show(box, state, server) {
    box.dataset.mcState = state;
    setField(box, "status", state);
    if (state === "online") {
      setField(box, "players", `${server.players.online} / ${server.players.max}`);
      setField(box, "version", server.version?.name_clean || EMPTY);
    } else {
      setField(box, "players", EMPTY);
      setField(box, "version", EMPTY);
    }
  }

  async function loadStatus(address) {
    const response = await fetch(API + encodeURIComponent(address));
    if (!response.ok) throw new Error(`mcstatus.io ${address}: HTTP ${response.status}`);
    return response.json();
  }

  async function refresh() {
    lastRefresh = Date.now();
    await Promise.all(
      addresses.map(async (address) => {
        const targets = boxes.filter((box) => box.dataset.mcStatus === address);
        try {
          const server = await loadStatus(address);
          for (const box of targets) show(box, server.online ? "online" : "offline", server);
        } catch (error) {
          console.warn("minecraft status: data not loaded:", error);
          for (const box of targets) show(box, "unknown", null);
        }
      }),
    );
  }

  if (addresses.length > 0) {
    refresh();
    setInterval(() => {
      if (!document.hidden) refresh();
    }, REFRESH_INTERVAL);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && Date.now() - lastRefresh >= REFRESH_INTERVAL) refresh();
    });
  }

  for (const button of document.querySelectorAll("[data-mc-copy]")) {
    let resetTimer;
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.mcCopy);
      } catch (error) {
        console.warn("minecraft status: address not copied:", error);
        return;
      }
      button.classList.add("mc-status__copy--done");
      clearTimeout(resetTimer);
      resetTimer = setTimeout(
        () => button.classList.remove("mc-status__copy--done"),
        COPY_FEEDBACK_DURATION,
      );
    });
  }
})();
