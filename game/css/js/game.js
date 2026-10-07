(() => {
  const G = GF;
  G.services = [
    { id: "quest", name: "모모 · 모험 안내", x: 175, y: 215, color: "#f6dccb" },
    { id: "shop", name: "포포 · 작은 상점", x: 360, y: 190, color: "#dee8ef" },
    {
      id: "market",
      name: "루나 · 달빛 거래소",
      x: 435,
      y: 330,
      color: "#e8dcf1",
    },
    { id: "forest", name: "새싹 · 숲지기", x: 620, y: 160, color: "#dae9d1" },
  ];
  G.questDefs = [
    {
      id: "berries",
      name: "오늘의 달빛딸기",
      description: "달빛딸기 6개를 모모에게 전달",
      goal: 6,
      reward: 120,
      exp: 40,
    },
    {
      id: "slimes",
      name: "동굴 청소",
      description: "퀘스트 수락 후 슬라임 3마리 처치",
      goal: 3,
      reward: 180,
      exp: 70,
    },
    {
      id: "merchant",
      name: "상인의 부탁",
      description: "퀘스트 수락 후 별결정 2개 판매",
      goal: 2,
      reward: 100,
      exp: 45,
    },
  ];
  G.validPosition = (x, y) => ({
    x: G.clamp(x, 25, 1255),
    y: G.clamp(y, 55, 795),
  });
  G.createWorld = () => ({
    clock: Date.now(),
    elapsed: 0,
    realElapsed: 0,
    speed: 60,
    paused: false,
    npcs: G.npc.create(),
    resources: [
      ...Array.from({ length: 14 }, (_, i) => ({
        id: "BERRY_" + i,
        item: "berry",
        x: 580 + (i % 7) * 87,
        y: 200 + Math.floor(i / 7) * 115,
        available: true,
        respawn: 0,
      })),
      ...Array.from({ length: 8 }, (_, i) => ({
        id: "CRYSTAL_" + i,
        item: "crystal",
        x: i < 4 ? 740 + (i % 4) * 120 : 985 + (i % 4) * 65,
        y: i < 4 ? 105 : 725,
        available: true,
        respawn: 0,
      })),
    ],
    slimes: Array.from({ length: 7 }, (_, i) => ({
      id: "SLIME_" + i,
      x: 1000 + (i % 3) * 95,
      y: 495 + Math.floor(i / 3) * 72,
      hp: 60,
      maxHp: 60,
      phase: G.random(0, 6),
      respawn: 0,
      hit: 0,
    })),
    prices: Object.fromEntries(
      Object.entries(G.items).map(([k, v]) => [k, v.base_price]),
    ),
    listings: [],
    nextNormalTrade: 900,
  });
  G.news = (text) => {
    G.messages.unshift({ text, time: G.logger.now() });
    G.messages = G.messages.slice(0, 6);
  };
  G.messages = [];
  G.gainExp = (actor, amount) => {
    actor.exp = (actor.exp || 0) + amount;
    while (actor.exp >= actor.level * 100) {
      actor.exp -= actor.level * 100;
      actor.level++;
      if (actor === G.player) G.toast("레벨 업! Lv." + actor.level);
    }
  };
  G.gatherSuccess = (actor, r) => {
    if (!r.available) return false;
    r.available = false;
    r.respawn = G.world.realElapsed + 18;
    actor.inventory[r.item]++;
    G.gainExp(actor, 12);
    G.logger.event(actor, "gather_success", {
      item_id: r.item,
      quantity: 1,
      metadata: { object_id: r.id },
    });
    if (actor === G.player) {
      G.news(G.items[r.item].item_name + " +1");
      G.toast(G.items[r.item].item_name + "을 채집했어요");
    }
    return true;
  };
  G.attack = (actor, s) => {
    if (s.hp <= 0 || Math.hypot(actor.x - s.x, actor.y - s.y) > 65)
      return false;
    const damage = actor === G.player ? 25 : 18;
    G.logger.event(actor, "attack", { metadata: { monster_id: s.id, damage } });
    s.hp -= damage;
    s.hit = G.world.realElapsed;
    actor.anim = "attack";
    actor.animUntil = G.world.realElapsed + 0.32;
    actor.hp = Math.max(0, actor.hp - 6);
    actor.damageUntil = G.world.realElapsed + 0.15;
    G.logger.event(actor, "damaged", {
      metadata: { monster_id: s.id, damage: 6, hp: actor.hp },
    });
    if (s.hp <= 0) {
      s.hp = 0;
      s.respawn = G.world.realElapsed + 15;
      G.economy.earn(actor, 35);
      G.gainExp(actor, 25);
      actor.inventory.gel++;
      actor.kills = (actor.kills || 0) + 1;
      G.logger.event(actor, "monster_kill", {
        gold_delta: 35,
        metadata: { monster_id: s.id },
      });
      G.logger.event(actor, "item_drop", {
        item_id: "gel",
        quantity: 1,
        metadata: { monster_id: s.id },
      });
      if (actor === G.player) {
        G.news("슬라임을 물리쳤어요 · +35 G / +25 EXP");
        G.toast("슬라임젤 +1 · 35 G");
      }
    }
    return true;
  };
  G.game = {
    keys: new Set(),
    running: false,
    last: 0,
    uiTick: 0,
    saveTick: 0,
    moveTick: 0,
    start(character) {
      G.player = character;
      G.world = G.store.state.world || G.createWorld();
      G.world.paused = false;
      document.getElementById("pause").textContent = "일시정지";
      document.getElementById("pause-overlay").classList.add("hidden");
      G.world.realElapsed = G.world.realElapsed || 0;
      for (const n of G.world.npcs) {
        if (
          n.online &&
          !G.store.state.logs.sessions.some(
            (s) => s.session_id === n.session_id && !s.logout_at,
          )
        ) {
          G.logger.login(n, true);
        }
      }
      G.player.anim = "idle";
      G.player.pending = null;
      G.logger.login(G.player, false);
      G.store.state.activeCharacter = character.character_id;
      G.store.state.world = G.world;
      G.store.save();
      document.getElementById("speed").value = G.world.speed;
      G.showScreen("game");
      G.news(character.nickname + "님의 작은 모험이 시작되었습니다");
      this.running = true;
      this.last = performance.now();
      this.uiTick = 0;
      G.ui();
      document.getElementById("world").focus();
    },
    leave() {
      if (!this.running) return;
      G.logger.logout(G.player, "character_selection");
      for (const n of G.world.npcs)
        if (n.session_id) G.logger.logout(n, "world_closed");
      G.store.state.world = G.world;
      G.store.state.activeCharacter = null;
      G.store.save();
      this.running = false;
      this.keys.clear();
      G.showCharacters();
    },
    update(dt) {
      const w = G.world,
        p = G.player;
      if (w.paused) return;
      w.realElapsed += dt;
      const simdt = dt * w.speed;
      w.elapsed += simdt;
      w.clock += simdt * 1000;
      G.economy.update();
      for (const r of w.resources)
        if (!r.available && w.realElapsed >= r.respawn) r.available = true;
      for (const s of w.slimes) {
        if (s.hp <= 0) {
          if (w.realElapsed >= s.respawn) {
            s.hp = s.maxHp;
            G.logger.event(
              { user_id: "SYSTEM_WORLD", x: s.x, y: s.y },
              "monster_respawn",
              { metadata: { monster_id: s.id } },
            );
          }
          continue;
        }
        s.x = G.clamp(
          s.x + Math.sin(w.realElapsed * 0.7 + s.phase) * dt * 12,
          970,
          1245,
        );
        s.y = G.clamp(
          s.y + Math.cos(w.realElapsed * 0.8 + s.phase) * dt * 9,
          475,
          700,
        );
      }
      if (p.hp <= 0) {
        p.hp = 100;
        p.x = 265;
        p.y = 310;
        G.logger.event(p, "respawn");
        G.toast("마을의 달빛이 회복시켜 주었어요");
      }
      const inputBlocked = document.querySelector("dialog[open]");
      let dx = 0,
        dy = 0;
      if (!inputBlocked) {
        dx =
          (this.keys.has("d") || this.keys.has("arrowright") ? 1 : 0) -
          (this.keys.has("a") || this.keys.has("arrowleft") ? 1 : 0);
        dy =
          (this.keys.has("s") || this.keys.has("arrowdown") ? 1 : 0) -
          (this.keys.has("w") || this.keys.has("arrowup") ? 1 : 0);
      }
      if (dx || dy) {
        if (p.pending) {
          G.logger.event(p, "gather_cancel", { item_id: p.pending.item });
          p.pending = null;
        }
        const len = Math.hypot(dx, dy),
          speed = this.keys.has("shift") ? 220 : 125;
        Object.assign(
          p,
          G.validPosition(
            p.x + (dx / len) * speed * dt,
            p.y + (dy / len) * speed * dt,
          ),
        );
        p.walk = (p.walk || 0) + dt * 10;
        p.anim = "walk";
        p.facing = dx < 0 ? -1 : 1;
        this.moveTick += dt;
        if (this.moveTick >= 1) {
          G.logger.event(p, "move", {
            metadata: { dash: this.keys.has("shift") },
          });
          this.moveTick = 0;
        }
      } else if (p.pending) {
        p.anim = "gather";
        if (w.realElapsed >= p.pending.finish) {
          const r = w.resources.find((r) => r.id === p.pending.id);
          if (r?.available) G.gatherSuccess(p, r);
          else G.toast("다른 주민이 먼저 채집했어요");
          p.pending = null;
        }
      } else if ((p.animUntil || 0) < w.realElapsed) p.anim = "idle";
      if (G.zone(p.x, p.y).id === "LAKE_01" && !dx && !dy) {
        if (!p.resting && p.hp < 100)
          G.logger.event(p, "rest", {
            metadata: { venue: "moon_lake", hp: p.hp },
          });
        p.resting = true;
        p.hp = Math.min(100, p.hp + dt * 2);
      } else p.resting = false;
      G.npc.update(dt);
      this.uiTick += dt;
      this.saveTick += dt;
      if (this.uiTick > 0.3) {
        G.ui();
        this.uiTick = 0;
      }
      if (this.saveTick > 5) {
        this.save();
        this.saveTick = 0;
      }
    },
    save() {
      G.store.state.world = G.world;
      const ok = G.store.save();
      document.getElementById("save-status").textContent =
        ok && !G.store.warning
          ? "자동 저장됨 · " +
            new Date().toLocaleTimeString("ko-KR", {
              hour: "2-digit",
              minute: "2-digit",
            })
          : G.store.warning;
    },
    nearest() {
      const p = G.player,
        objects = [
          ...G.services.map((s) => ({ ...s, kind: "service" })),
          ...G.world.resources
            .filter((r) => r.available)
            .map((r) => ({ ...r, kind: "resource" })),
          ...G.world.slimes
            .filter((s) => s.hp > 0)
            .map((s) => ({ ...s, kind: "slime" })),
        ];
      return objects
        .filter((o) => Math.hypot(p.x - o.x, p.y - o.y) < 65)
        .sort(
          (a, b) =>
            Math.hypot(p.x - a.x, p.y - a.y) - Math.hypot(p.x - b.x, p.y - b.y),
        )[0];
    },
    interact(attackOnly = false) {
      if (
        !this.running ||
        G.world.paused ||
        document.querySelector("dialog[open]")
      )
        return;
      const p = G.player;
      if (attackOnly) {
        const s = G.world.slimes
          .filter((s) => s.hp > 0 && Math.hypot(p.x - s.x, p.y - s.y) < 65)
          .sort(
            (a, b) =>
              Math.hypot(p.x - a.x, p.y - a.y) -
              Math.hypot(p.x - b.x, p.y - b.y),
          )[0];
        if (s) this.hit(s);
        return;
      }
      const o = this.nearest();
      if (!o) {
        G.toast("조금 더 가까이 다가가세요");
        return;
      }
      if (o.kind === "service") G.openService(o.id);
      else if (o.kind === "slime")
        this.hit(G.world.slimes.find((s) => s.id === o.id));
      else if (!p.pending) {
        p.pending = {
          id: o.id,
          item: o.item,
          finish: G.world.realElapsed + 1.1,
        };
        G.logger.event(p, "gather_start", {
          item_id: o.item,
          metadata: { object_id: o.id },
        });
      }
    },
    hit(s) {
      if (G.world.realElapsed - (G.player.lastAttack ?? -10) < 0.55) return;
      if (G.player.combatTarget !== s.id) {
        G.player.combatTarget = s.id;
        G.logger.event(G.player, "combat_start", {
          metadata: { monster_id: s.id },
        });
      }
      G.attack(G.player, s);
      G.player.lastAttack = G.world.realElapsed;
    },
    pause() {
      G.world.paused = !G.world.paused;
      this.keys.clear();
      document.getElementById("pause").textContent = G.world.paused
        ? "다시 시작"
        : "일시정지";
      document
        .getElementById("pause-overlay")
        .classList.toggle("hidden", !G.world.paused);
      G.ui();
      this.save();
    },
  };
  G.questProgress = (q) => {
    const p = G.player,
      state = p.quests[q.id];
    if (!state) return 0;
    return Math.min(
      q.goal,
      q.id === "berries"
        ? p.inventory.berry
        : q.id === "slimes"
          ? p.kills - state.baseline
          : p.soldCrystals - state.baseline,
    );
  };
  G.acceptQuest = (id) => {
    const q = G.questDefs.find((q) => q.id === id);
    if (!q || G.player.quests[id]) return;
    G.player.quests[id] = {
      state: "active",
      baseline:
        id === "slimes"
          ? G.player.kills
          : id === "merchant"
            ? G.player.soldCrystals
            : 0,
    };
    G.logger.event(G.player, "quest_start", { metadata: { quest_id: id } });
    G.game.save();
    G.ui();
    G.openService("quest");
  };
  G.claimQuest = (id) => {
    const q = G.questDefs.find((q) => q.id === id),
      s = G.player.quests[id];
    if (!q || s?.state !== "active" || G.questProgress(q) < q.goal)
      return false;
    if (id === "berries") G.player.inventory.berry -= 6;
    s.state = "complete";
    G.economy.earn(G.player, q.reward);
    G.gainExp(G.player, q.exp);
    G.player.reputation += 5;
    G.logger.event(G.player, "quest_complete", {
      gold_delta: q.reward,
      metadata: { quest_id: id, exp: q.exp },
    });
    G.news(q.name + " 완료 · +" + q.reward + " G");
    G.game.save();
    G.ui();
    G.openService("quest");
    return true;
  };
})();
