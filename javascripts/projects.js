// Fill the GitHub project cards on the home page with live repository data:
// description, language, stars and forks. One request per repository owner,
// the result is kept for the browser session.
(() => {
  const cards = [...document.querySelectorAll(".repo-card[data-repo]")];
  if (cards.length === 0) return;

  const CACHE_KEY = "home-projects";
  const API = "https://api.github.com";
  const LANGUAGE_COLORS = {
    "C": "#555555",
    "C++": "#f34b7d",
    "CSS": "#563d7c",
    "Go": "#00add8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "Kotlin": "#a97bff",
    "Python": "#3572a5",
    "Rust": "#dea584",
    "Shell": "#89e051",
    "TypeScript": "#3178c6",
  };
  const DEFAULT_LANGUAGE_COLOR = "#8b949e";

  const names = cards.map((card) => card.dataset.repo);

  function readCache() {
    try {
      const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY));
      if (cached && names.every((name) => name.toLowerCase() in cached)) return cached;
    } catch {
      // Storage unavailable or invalid: load fresh data
    }
    return null;
  }

  function writeCache(data) {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify(data));
    } catch {
      // Storage unavailable: data is loaded again on the next visit
    }
  }

  async function getJson(path) {
    const response = await fetch(API + path, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) throw new Error(`GitHub API ${path}: HTTP ${response.status}`);
    return response.json();
  }

  // Owners with several listed repositories: one request for all of them.
  // Owners with a single listed repository: one request for that repository.
  async function loadRepos() {
    const byOwner = {};
    for (const name of names) {
      const owner = name.split("/")[0];
      (byOwner[owner] ??= []).push(name);
    }
    const requests = Object.entries(byOwner).map(([owner, repos]) =>
      repos.length > 1
        ? getJson(`/users/${owner}/repos?per_page=100&type=owner`)
        : getJson(`/repos/${repos[0]}`).then((repo) => [repo]),
    );
    const data = {};
    for (const repo of (await Promise.all(requests)).flat()) {
      data[repo.full_name.toLowerCase()] = {
        description: repo.description || "",
        language: repo.language,
        stars: repo.stargazers_count,
        forks: repo.forks_count,
      };
    }
    return data;
  }

  function fill(card, repo) {
    card.querySelector('[data-field="description"]').textContent = repo.description;
    const show = (field, value) => {
      const element = card.querySelector(`[data-field="${field}"]`);
      element.querySelector("[data-value]").textContent = value;
      element.hidden = false;
      return element;
    };
    if (repo.language) {
      const language = show("language", repo.language);
      language.querySelector(".repo-card__dot").style.backgroundColor =
        LANGUAGE_COLORS[repo.language] || DEFAULT_LANGUAGE_COLOR;
    }
    if (repo.stars) show("stars", repo.stars);
    if (repo.forks) show("forks", repo.forks);
  }

  async function run() {
    let data = readCache();
    if (data === null) {
      data = await loadRepos();
      writeCache(data);
    }
    for (const card of cards) {
      const repo = data[card.dataset.repo.toLowerCase()];
      if (repo) {
        fill(card, repo);
      } else {
        console.warn(`home projects: repository ${card.dataset.repo} not found`);
      }
    }
  }

  run().catch((error) => console.warn("home projects: data not loaded:", error));
})();
