(() => {
  const G = GF;
  const names = [
    "밀크",
    "바닐라",
    "버터",
    "솜솜",
    "코코",
    "피치",
    "두부",
    "푸딩",
    "모찌",
    "라떼",
    "밤비",
    "포리",
    "멜로",
    "치즈",
    "루루",
    "민트",
    "살구",
    "단추",
    "호두",
    "쿠키",
    "봉봉",
    "오트",
    "새벽",
    "안개",
    "별빛",
    "이슬",
    "꽃잎",
    "노을",
    "초승",
    "달콩",
    "눈꽃",
    "파랑",
    "구름",
    "토리",
    "리본",
    "비누",
  ];
  G.npc = {
    create() {
      const types = [
        ...Array(10).fill("normal"),
        ...Array(4).fill("hardcore"),
        ...Array(6).fill("guild"),
        ...Array(3).fill("bot"),
        ...Array(10).fill("farm"),
        ...Array(2).fill("mule"),
        "hub",
      ];
      return types.map((type, i) => ({
        user_id: "SYN_U" + String(i + 1).padStart(3, "0"),
        character_id: "SYN_C" + String(i + 1).padStart(3, "0"),
        nickname: names[i],
        user_type: type,
        x: G.random(200, 420),
        y: G.random(260, 390),
        gold: type === "hub" ? 100 : type === "mule" ? 80 : 400,
        inventory: {
          berry: 2,
          crystal: 1,
          gel: 1,
          token: type === "farm" && i === 23 ? 1 : 0,
        },
        level: type === "hardcore" ? 24 : 3,
        hp: 100,
        exp: 0,
        reputation: 0,
        online: false,
        session_id: null,
        loginDue:
          type === "guild"
            ? 180 + (i - 14) * 12
            : type === "farm"
              ? G.random(60, 300)
              : G.random(0, 200),
        duration:
          {
            normal: G.random(2, 5),
            hardcore: G.random(14, 18),
            guild: 3,
            bot: 22,
            farm: G.random(6, 11),
            mule: G.random(4, 8),
            hub: 8,
          }[type] * 3600,
        nextAction: 0,
        nextTransfer: G.random(1800, 3600),
        earned: 0,
        sent: 0,
        received: 0,
        trades: 0,
        task: null,
        device_group:
          type === "farm"
            ? "shared_pc_" + (i % 3)
            : type === "bot"
              ? "bot_device_" + i
              : "device_" + i,
        ip_group: ["farm", "mule", "hub"].includes(type)
          ? "synthetic_subnet_A"
          : type === "guild"
            ? "guild_cafe"
            : "synthetic_ip_" + i,
        color: ["#eee5dd", "#f4dbe4", "#dce8f3", "#e9e2f4"][i % 4],
        walk: 0,
        anim: "idle",
      }));
    },
    point(zone) {
      const z = G.zones.find((z) => z.id === zone);
      return {
        x: G.random(z.x + 60, z.x + z.w - 60),
        y: G.random(z.y + 65, z.y + z.h - 65),
      };
    },
    decide(n) {
      const t = G.world.elapsed;
      const type = n.user_type;
      let action;
      if (["mule", "hub"].includes(type)) {
        const dest =
          type === "mule"
            ? G.world.npcs.find((a) => a.user_type === "hub")
            : null;
        if (dest && n.gold > 150 && t >= n.nextTransfer) {
          n.task = {
            action: "transfer",
            targetId: dest.user_id,
            x: dest.x,
            y: dest.y,
          };
          return;
        }
        action = Math.random() < 0.75 ? "rest" : "wander";
      } else if (type === "farm" && n.gold > 200 && t >= n.nextTransfer) {
        const mule = G.world.npcs.filter((a) => a.user_type === "mule")[
          Number(n.user_id.slice(-3)) % 2
        ];
        n.task = {
          action: "transfer",
          targetId: mule.user_id,
          x: mule.x,
          y: mule.y,
        };
        return;
      } else
        action =
          type === "bot"
            ? "hunt"
            : type === "guild"
              ? ["guild_hunt", "guild_hunt", "guild_rest", "gather"][
                  Math.floor(t / 1200) % 4
                ]
              : type === "hardcore"
                ? G.pick([
                    "hunt",
                    "hunt",
                    "gather",
                    "sell",
                    "quest",
                    "rest",
                    "market",
                  ])
                : G.pick([
                    "gather",
                    "hunt",
                    "quest",
                    "sell",
                    "rest",
                    "wander",
                    "market",
                  ]);
      if (action === "hunt" || action === "guild_hunt") {
        const alive = G.world.slimes.filter((s) => s.hp > 0),
          slime =
            type === "bot"
              ? G.world.slimes[Number(n.user_id.slice(-3)) % 3]
              : G.pick(alive);
        if (slime && slime.hp > 0)
          n.task = {
            action: "hunt",
            object_id: slime.id,
            x: slime.x,
            y: slime.y,
          };
        else n.task = { action: "rest", ...this.point("CAVE_01") };
      } else if (action === "gather") {
        const r = G.pick(G.world.resources.filter((r) => r.available));
        n.task = r
          ? { action: "gather", object_id: r.id, x: r.x, y: r.y }
          : { action: "rest", ...this.point("FOREST_01") };
      } else if (
        action === "sell" ||
        action === "quest" ||
        action === "market"
      ) {
        n.task = {
          action,
          x: action === "sell" ? 360 : action === "market" ? 435 : 175,
          y: action === "sell" ? 190 : action === "market" ? 330 : 215,
        };
      } else if (action === "guild_rest")
        n.task = {
          action: "rest",
          x: 690 + (Number(n.user_id.slice(-3)) % 3) * 25,
          y: 610,
        };
      else
        n.task = {
          action,
          ...this.point(action === "rest" ? "LAKE_01" : G.pick(G.zones).id),
        };
      if (type === "guild" && action === "guild_hunt") {
        // A shared route creates benign movement synchrony.
        n.task.x = 1070 + (Number(n.user_id.slice(-3)) % 3) * 18;
        n.task.y = 530;
        n.task.waypoint = true;
      }
    },
    update(dt) {
      const w = G.world,
        t = w.elapsed;
      for (const n of w.npcs) {
        if (!n.online) {
          if (t < n.loginDue) continue;
          n.online = true;
          n.sessionStart = t;
          n.logoutDue = t + n.duration;
          G.logger.login(n, true);
          n.nextAction = t + 20;
        }
        if (t >= n.logoutDue) {
          G.logger.logout(n, "scheduled_logout");
          n.online = false;
          n.task = null;
          n.loginDue =
            Math.floor(t / 86400 + 1) * 86400 +
            (n.user_type === "guild" ? 180 : G.random(60, 300));
          continue;
        }
        if (n.hp <= 0) {
          n.hp = 100;
          n.x = 300;
          n.y = 310;
          G.logger.event(n, "respawn");
        }
        if (!n.task) {
          n.anim = "idle";
          if (t >= n.nextAction) this.decide(n);
          else continue;
        }
        const task = n.task;
        if (!task) continue;
        if (task.action === "transfer") {
          const a = G.economy.actor(task.targetId);
          if (a) {
            task.x = a.x;
            task.y = a.y;
          }
        }
        if (task.action === "hunt") {
          const s = w.slimes.find((s) => s.id === task.object_id);
          if (task.waypoint && Math.hypot(n.x - task.x, n.y - task.y) < 30)
            task.waypoint = false;
          if (s && s.hp > 0 && !task.waypoint) {
            task.x = s.x;
            task.y = s.y;
          }
        }
        const dx = task.x - n.x,
          dy = task.y - n.y,
          dist = Math.hypot(dx, dy);
        if (dist > 25) {
          const step = Math.min(
            dist,
            dt * (n.user_type === "hardcore" ? 88 : 68),
          );
          const p = G.validPosition(
            n.x + (dx / dist) * step,
            n.y + (dy / dist) * step,
          );
          n.x = p.x;
          n.y = p.y;
          n.anim = "walk";
          n.walk += dt * 9;
          if (t - (n.moveLog || 0) > 120) {
            G.logger.event(n, "move");
            n.moveLog = t;
          }
          continue;
        }
        n.anim = "idle";
        let done = true;
        if (task.action === "gather") {
          const r = w.resources.find((r) => r.id === task.object_id);
          if (r?.available) {
            if (!task.started) {
              task.started = w.realElapsed;
              G.logger.event(n, "gather_start", {
                item_id: r.item,
                metadata: { object_id: r.id },
              });
            }
            n.anim = "gather";
            if (w.realElapsed - task.started < 0.8) done = false;
            else {
              G.gatherSuccess(n, r);
            }
          }
        } else if (task.action === "hunt") {
          const s = w.slimes.find((s) => s.id === task.object_id);
          if (s?.hp > 0) {
            if (!task.started) {
              task.started = true;
              G.logger.event(n, "combat_start", {
                metadata: { monster_id: s.id },
              });
            }
            if (w.realElapsed - (n.lastAttack || 0) > 0.7) {
              G.attack(n, s);
              n.lastAttack = w.realElapsed;
            }
            done = s.hp <= 0;
            n.anim = "attack";
          }
        } else if (task.action === "transfer") {
          const a = G.economy.actor(task.targetId);
          if (
            a?.online &&
            G.economy.transfer(n, a, Math.floor(n.gold * 0.78))
          ) {
            G.news(n.nickname + "님이 주민에게 골드를 전송했어요");
          }
          n.nextTransfer = t + G.random(1800, 4200);
        } else if (task.action === "sell") {
          const item = G.pick(
            Object.keys(n.inventory).filter(
              (i) => n.inventory[i] > 0 && i !== "token",
            ),
          );
          if (item) {
            if (Math.random() < 0.4 && w.listings.length < 40)
              G.economy.list(n, item, 1, w.prices[item]);
            else G.economy.shopSell(n, item, n.inventory[item]);
          }
        } else if (task.action === "market") {
          const listing = G.pick(
            w.listings.filter(
              (l) =>
                l.seller_id !== n.user_id &&
                (!l.target_user_id || l.target_user_id === n.user_id) &&
                l.unit_price * l.quantity <= n.gold,
            ),
          );
          if (listing) G.economy.buy(n, listing.listing_id);
        } else if (task.action === "quest") {
          G.logger.event(n, "quest_start", {
            metadata: { quest_id: "synthetic_supply" },
          });
          if (n.inventory.berry >= 2) {
            n.inventory.berry -= 2;
            G.economy.earn(n, 35);
            G.logger.event(n, "quest_complete", {
              item_id: "berry",
              quantity: 2,
              gold_delta: 35,
              metadata: { quest_id: "synthetic_supply" },
            });
          }
        } else if (task.action === "rest") {
          n.hp = G.clamp(n.hp + 15, 0, 100);
          G.logger.event(n, "rest");
        } else G.logger.event(n, "visit");
        if (done) {
          n.task = null;
          n.nextAction =
            n.user_type === "guild"
              ? (Math.floor(t / 600) + 1) * 600
              : t + (n.user_type === "bot" ? 180 : G.random(120, 780));
        }
      }
      // Genuine escrowed low-price sale; the buyer pays and receives the token.
      if (!w.anomalyDone) {
        const seller = w.npcs.find(
            (n) => n.user_type === "farm" && n.inventory.token > 0,
          ),
          buyer = w.npcs.find((n) => n.user_type === "mule");
        if (seller?.online && buyer?.online && t > 2400 && buyer.gold >= 500) {
          const l = G.economy.list(seller, "token", 1, 500, buyer.user_id);
          if (l && G.economy.buy(buyer, l.listing_id)) w.anomalyDone = true;
        }
      }
      if (t > (w.nextNormalTrade || 900)) {
        const donors = w.npcs.filter(
          (n) =>
            n.online &&
            ["normal", "guild", "hardcore"].includes(n.user_type) &&
            n.gold > 80,
        );
        if (donors.length > 1) {
          const a = G.pick(donors),
            b = G.pick(donors.filter((n) => n !== a));
          G.economy.transfer(a, b, Math.floor(G.random(5, 25)));
        }
        w.nextNormalTrade = t + G.random(500, 1500);
      }
    },
  };
})();
