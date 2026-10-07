(() => {
  const G = window.GF;
  G.id = (prefix) => prefix + "_" + crypto.randomUUID();
  G.clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  G.random = (a, b) => a + Math.random() * (b - a);
  G.pick = (a) => a[Math.floor(Math.random() * a.length)];
  G.escape = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  G.items = {
    berry: {
      item_id: "berry",
      item_name: "달빛딸기",
      base_price: 18,
      color: "#ed93b4",
    },
    crystal: {
      item_id: "crystal",
      item_name: "별결정",
      base_price: 70,
      color: "#9ba1e5",
    },
    gel: {
      item_id: "gel",
      item_name: "슬라임젤",
      base_price: 24,
      color: "#79c8ad",
    },
    token: {
      item_id: "token",
      item_name: "달빛 토큰",
      base_price: 30000,
      color: "#e7bc73",
    },
  };
  G.zones = [
    {
      id: "VILLAGE_01",
      name: "Moonberry Village",
      x: 0,
      y: 0,
      w: 530,
      h: 450,
      color: "#d9eddb",
    },
    {
      id: "FOREST_01",
      name: "Moonberry Forest",
      x: 530,
      y: 0,
      w: 750,
      h: 400,
      color: "#c3dfc9",
    },
    {
      id: "CAVE_01",
      name: "Starlight Cave",
      x: 930,
      y: 400,
      w: 350,
      h: 420,
      color: "#dbd6eb",
    },
    {
      id: "LAKE_01",
      name: "Moon Lake",
      x: 0,
      y: 450,
      w: 510,
      h: 370,
      color: "#d1e8ea",
    },
    {
      id: "GUILD_01",
      name: "Guild Square",
      x: 510,
      y: 400,
      w: 420,
      h: 420,
      color: "#eedee2",
    },
  ];
  G.zone = (x, y) =>
    G.zones.find(
      (z) => x >= z.x && x < z.x + z.w && y >= z.y && y < z.y + z.h,
    ) || G.zones[0];
  G.blankInventory = () => ({ berry: 0, crystal: 0, gel: 0, token: 0 });
  G.defaultState = () => ({
    version: 1,
    users: [],
    characters: [],
    activeUser: null,
    activeCharacter: null,
    world: null,
    logs: {
      events: [],
      transactions: [],
      sessions: [],
      dropped: { events: 0, transactions: 0, sessions: 0 },
    },
  });
  G.store = {
    state: G.defaultState(),
    warning: "",
    load() {
      try {
        const s = JSON.parse(localStorage.getItem("aetheria.v1"));
        if (s?.version === 1) this.state = s;
      } catch (e) {
        this.warning =
          "저장 데이터를 읽지 못했습니다. 원본 저장소는 덮어쓰지 않습니다.";
        this.blocked = true;
      }
      return this.state;
    },
    save() {
      if (this.blocked) return false;
      let trimmed = false;
      // Prefer keeping character progress when a browser has a smaller quota.
      // All discarded rows are counted and visible in the operator export.
      for (let attempt = 0; attempt < 50; attempt++) {
        try {
          localStorage.setItem("aetheria.v1", JSON.stringify(this.state));
          this.warning = trimmed
            ? "저장 공간 제한: 오래된 로그를 순환했습니다. Export를 권장합니다."
            : "";
          return true;
        } catch (e) {
          if (e.name !== "QuotaExceededError") break;
          const logs = this.state.logs;
          const kind = ["events", "transactions", "sessions"].find(
            (k) => logs[k].length > 500,
          );
          if (!kind) break;
          const removed = logs[kind].splice(
            0,
            Math.min(500, logs[kind].length - 500),
          );
          logs.dropped[kind] += removed.length;
          trimmed = true;
        }
      }
      this.warning =
        "저장 공간이 부족합니다. 운영자 메뉴에서 로그를 내보내세요.";
      return false;
    },
    character(user, nickname) {
      const c = {
        character_id: G.id("C"),
        user_id: user.user_id,
        nickname,
        level: 1,
        exp: 0,
        gold: 160,
        reputation: 0,
        created_at: new Date().toISOString(),
        hp: 100,
        x: 265,
        y: 310,
        inventory: G.blankInventory(),
        quests: {},
        kills: 0,
        soldCrystals: 0,
      };
      this.state.characters.push(c);
      this.save();
      return c;
    },
  };
})();
