(() => {
  const G = GF,
    $ = (id) => document.getElementById(id);
  G.toast = (message) => {
    $("toast").textContent = message;
    $("toast").classList.remove("hidden");
    clearTimeout(G.toastTimer);
    G.toastTimer = setTimeout(() => $("toast").classList.add("hidden"), 3200);
  };
  G.showScreen = (screen) => {
    for (const id of ["auth", "characters", "game"])
      $(id + "-screen").classList.toggle("hidden", id !== screen);
  };
  G.showCharacters = () => {
    G.showScreen("characters");
    const user = G.store.state.users.find(
      (u) => u.user_id === G.store.state.activeUser,
    );
    const chars = G.store.state.characters.filter(
      (c) => c.user_id === user?.user_id,
    );
    $("character-list").innerHTML = chars
      .map(
        (c) =>
          '<article class="character-card"><canvas width="96" height="110" data-character-art="' +
          c.character_id +
          '"></canvas><h2>' +
          G.escape(c.nickname) +
          "</h2><small>Lv." +
          c.level +
          ' · Moonberry Village</small><button class="primary" data-start="' +
          c.character_id +
          '">모험 시작</button></article>',
      )
      .join("");
    document.querySelectorAll("[data-character-art]").forEach((cv, i) => {
      G.render.bunny(
        cv.getContext("2d"),
        48,
        66,
        1.3,
        ["#fff6ef", "#e5e9f5", "#f7dde6"][i % 3],
        0,
      );
    });
  };
  G.itemIcon = (id) => {
    const color = G.items[id].color;
    const shapes = {
      berry:
        '<path d="M8 6 Q1 6 3 13 Q8 24 13 13 Q15 6 8 6" fill="' +
        color +
        '"/><path d="M4 6 L8 2 L12 6 L8 8Z" fill="#94b189"/><circle cx="6" cy="11" r="1" fill="#fff4e4"/>',
      crystal:
        '<path d="M8 1 L14 8 L10 19 L3 13 L4 5Z" fill="' +
        color +
        '"/><path d="M8 1 L7 16 L3 13 L4 5Z" fill="#d7d1f1"/>',
      gel:
        '<path d="M2 15 Q0 3 8 3 Q17 4 15 15Z" fill="' +
        color +
        '"/><circle cx="6" cy="9" r="1" fill="#657b70"/><circle cx="11" cy="9" r="1" fill="#657b70"/>',
      token:
        '<circle cx="9" cy="10" r="8" fill="' +
        color +
        '"/><path d="M9 4 L11 8 L15 10 L11 12 L9 16 L7 12 L3 10 L7 8Z" fill="#fff6d9"/>',
    };
    return (
      '<span class="item-icon"><svg viewBox="0 0 18 20" aria-hidden="true">' +
      shapes[id] +
      "</svg></span>"
    );
  };
  G.ui = () => {
    if (!G.player || !G.world) return;
    const p = G.player,
      w = G.world;
    $("player-name").textContent = p.nickname;
    $("level").textContent = "Lv." + p.level + " · 평판 " + p.reputation;
    $("gold").textContent = p.gold.toLocaleString() + " G";
    $("hp-text").textContent = Math.ceil(p.hp) + " / 100";
    $("hp").value = p.hp;
    $("exp-text").textContent = p.exp + " / " + p.level * 100;
    $("exp").max = p.level * 100;
    $("exp").value = p.exp;
    $("online").textContent =
      w.npcs.filter((n) => n.online).length + 1 + "명 온라인";
    $("clock").textContent =
      "세계 " +
      new Date(w.clock).toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
      }) +
      " · " +
      w.speed +
      "×";
    $("zone-name").textContent = G.zone(p.x, p.y).name;
    $("inventory").innerHTML = Object.entries(G.items)
      .map(
        ([id, item]) =>
          '<div class="inventory-row">' +
          G.itemIcon(id) +
          "<span>" +
          item.item_name +
          "</span><strong>" +
          p.inventory[id] +
          "</strong></div>",
      )
      .join("");
    $("prices").innerHTML = Object.entries(G.items)
      .map(
        ([id, item]) =>
          '<div class="price-row">' +
          G.itemIcon(id) +
          "<span>" +
          item.item_name +
          "</span><strong>" +
          w.prices[id].toLocaleString() +
          " G</strong></div>",
      )
      .join("");
    $("quests").innerHTML = G.questDefs
      .map((q) => {
        const state = p.quests[q.id],
          done = state?.state === "complete",
          value = G.questProgress(q);
        return (
          '<div class="quest"><h4>' +
          q.name +
          "</h4><p>" +
          q.description +
          '</p><progress max="' +
          q.goal +
          '" value="' +
          (done ? q.goal : value) +
          '"></progress><div class="quest-bottom"><span>' +
          q.reward +
          " G · " +
          q.exp +
          " EXP</span><span>" +
          (done ? "완료" : state ? value + " / " + q.goal : "모모에게 수락") +
          "</span></div></div>"
        );
      })
      .join("");
    $("activity").innerHTML =
      G.messages
        .map(
          (m) =>
            '<div class="activity-line"><time>' +
            new Date(m.time).toLocaleTimeString("ko-KR", {
              hour: "2-digit",
              minute: "2-digit",
            }) +
            "</time><span>" +
            G.escape(m.text) +
            "</span></div>",
        )
        .join("") || "<small>마을의 소식이 이곳에 도착합니다.</small>";
    const l = G.store.state.logs;
    $("log-count").textContent =
      "이벤트 " +
      l.events.length.toLocaleString() +
      " · 거래 " +
      l.transactions.length.toLocaleString();
    const nearest = G.game.nearest();
    $("interaction-hint").textContent = p.pending
      ? "채집 중… 움직이면 취소됩니다"
      : nearest
        ? nearest.kind === "service"
          ? "E · " + nearest.name
          : nearest.kind === "slime"
            ? "E / Space · 슬라임 공격"
            : "E · " + G.items[nearest.item].item_name + " 채집"
        : "WASD 이동 · 주민 클릭으로 거래";
    if ($("operator-dialog").open) G.operator.update();
  };
  G.dialog = (html) => {
    $("dialog-content").innerHTML = html;
    if (!$("interaction-dialog").open) $("interaction-dialog").showModal();
    G.game.keys.clear();
  };
  G.openService = (id) => {
    if (G.world.paused) return;
    const p = G.player;
    if (id === "quest") {
      G.dialog(
        '<div class="eyebrow">MOMO’S QUEST BOARD</div><h2>모모의 작은 부탁</h2><p>함께 돌보면 더 따뜻한 마을이 될 거예요.</p>' +
          G.questDefs
            .map((q) => {
              const s = p.quests[q.id],
                done = s?.state === "complete",
                ready = G.questProgress(q) >= q.goal;
              return (
                '<div class="shop-row"><div><strong>' +
                q.name +
                "</strong><p>" +
                q.description +
                "</p></div><button " +
                (done ? "disabled" : "") +
                ' data-quest="' +
                q.id +
                '" data-claim="' +
                Boolean(s) +
                '">' +
                (done
                  ? "완료"
                  : s
                    ? ready
                      ? "보상 받기"
                      : G.questProgress(q) + " / " + q.goal
                    : "수락") +
                "</button></div>"
              );
            })
            .join(""),
      );
    } else if (id === "shop") {
      G.dialog(
        '<div class="eyebrow">POPO’S LITTLE SHOP</div><h2>포포의 작은 상점</h2><p>채집한 물품을 시세의 80%로 매입해요. 현재 ' +
          p.gold +
          " G</p>" +
          Object.entries(G.items)
            .map(
              ([item, def]) =>
                '<div class="shop-row"><span>' +
                G.itemIcon(item) +
                " " +
                def.item_name +
                " × " +
                p.inventory[item] +
                '</span><button data-sell="' +
                item +
                '" ' +
                (p.inventory[item] ? "" : "disabled") +
                ">1개 판매 · " +
                Math.round(G.world.prices[item] * 0.8) +
                " G</button></div>",
            )
            .join("") +
          "<button data-heal " +
          (p.gold < 25 || p.hp >= 100 ? "disabled" : "") +
          ">달빛 차 · HP 회복 · 25 G</button>",
      );
    } else if (id === "forest")
      G.dialog(
        '<div class="eyebrow">FOREST KEEPER</div><h2>새싹의 숲 안내</h2><p>분홍 열매가 달빛딸기예요. 가까이에서 E를 눌러 잠시 기다리세요. 보랏빛 별결정도 채집할 수 있어요. 오브젝트는 18초 뒤 다시 자랍니다.</p><p>동굴의 슬라임은 E 또는 Space로 공격해요. HP가 낮으면 호숫가에서 쉬거나 포포의 달빛 차를 마셔 보세요.</p>',
      );
    else if (id === "market") {
      const listings = G.world.listings.filter(
        (l) =>
          !l.target_user_id ||
          l.target_user_id === p.user_id ||
          l.seller_id === p.user_id,
      );
      G.dialog(
        '<div class="eyebrow">LUNA’S MOON MARKET</div><h2>달빛 거래소</h2><p>보유 ' +
          p.gold +
          ' G · 아이템은 등록 시 가방에서 보관됩니다.</p><form id="listing-form"><label for="listing-item">등록할 아이템</label><select id="listing-item">' +
          Object.entries(G.items)
            .map(
              ([id, item]) =>
                '<option value="' +
                id +
                '">' +
                item.item_name +
                " (" +
                p.inventory[id] +
                ")</option>",
            )
            .join("") +
          '</select><div class="input-row"><input id="listing-quantity" aria-label="등록 수량" type="number" min="1" max="999" value="1" required><input id="listing-price" aria-label="개당 판매 가격" type="number" min="1" max="1000000" value="20" required></div><button class="primary">아이템 등록</button></form><h3>주민의 매물</h3>' +
          listings
            .slice(-20)
            .map((l) => {
              const own = l.seller_id === p.user_id;
              const otherCharacter =
                own &&
                l.seller_character_id &&
                l.seller_character_id !== p.character_id;
              return (
                '<div class="listing"><div>' +
                G.items[l.item_id].item_name +
                " × " +
                l.quantity +
                "<small>" +
                G.escape(
                  G.economy.actor(l.seller_id, l.seller_character_id)
                    ?.nickname || "주민",
                ) +
                " · 개당 " +
                l.unit_price +
                " G</small></div><button " +
                (otherCharacter ? "disabled " : "") +
                (own ? "data-cancel" : "data-buy") +
                '="' +
                l.listing_id +
                '">' +
                (otherCharacter
                  ? "다른 캐릭터의 매물"
                  : own
                    ? "등록 취소"
                    : l.quantity * l.unit_price + " G 구매") +
                "</button></div>"
              );
            })
            .join("") +
          (listings.length
            ? ""
            : "<small>아직 등록된 매물이 없어요. 첫 매물을 등록해 보세요.</small>"),
      );
    }
  };
  G.openTrade = (n) => {
    if (G.world.paused) return;
    G.dialog(
      '<div class="eyebrow">A LITTLE GIFT</div><h2>' +
        G.escape(n.nickname) +
        "님에게 골드 보내기</h2><p>현재 보유 " +
        G.player.gold +
        ' G · 골드는 즉시 전달됩니다.</p><form id="trade-form" data-target="' +
        n.user_id +
        '"><label for="trade-amount">보낼 골드</label><input id="trade-amount" type="number" min="1" max="' +
        G.player.gold +
        '" required value="10"><button class="primary">골드 전송</button></form>',
    );
  };
  async function authenticate(signup) {
    if (!$("auth-form").reportValidity()) return;
    const btns = $("auth-form").querySelectorAll("button");
    btns.forEach((b) => (b.disabled = true));
    try {
      await G.auth.signIn($("email").value, $("password").value, signup);
      $("password").value = "";
      $("auth-message").textContent = "";
      G.showCharacters();
    } catch (e) {
      $("auth-message").textContent = e.message;
    } finally {
      btns.forEach((b) => (b.disabled = false));
    }
  }
  $("auth-form").onsubmit = (e) => {
    e.preventDefault();
    authenticate(false);
  };
  $("signup").onclick = () => authenticate(true);
  $("guest").onclick = () => {
    G.auth.guest();
    G.showCharacters();
  };
  $("account-logout").onclick = () => {
    G.auth.logout();
    G.showScreen("auth");
  };
  $("character-form").onsubmit = (e) => {
    e.preventDefault();
    const name = $("nickname").value.trim();
    if (!name) return;
    const chars = G.store.state.characters.filter(
      (c) => c.user_id === G.store.state.activeUser,
    );
    if (chars.length >= 8) {
      $("character-message").textContent =
        "계정당 최대 8개의 캐릭터를 만들 수 있어요.";
      return;
    }
    const user = G.store.state.users.find(
      (u) => u.user_id === G.store.state.activeUser,
    );
    G.store.character(user, name);
    $("nickname").value = "";
    G.showCharacters();
  };
  $("character-list").onclick = (e) => {
    const b = e.target.closest("[data-start]");
    if (b) {
      const c = G.store.state.characters.find(
        (c) =>
          c.character_id === b.dataset.start &&
          c.user_id === G.store.state.activeUser,
      );
      if (c) G.game.start(c);
    }
  };
  $("pause").onclick = () => G.game.pause();
  $("leave").onclick = () => G.game.leave();
  $("speed").onchange = (e) => {
    if (G.world.paused) return;
    G.world.speed = Number(e.target.value);
    G.logger.event(G.player, "simulation_speed", {
      metadata: { speed: G.world.speed },
    });
    G.game.save();
  };
  document.querySelectorAll(".dialog-close").forEach(
    (b) =>
      (b.onclick = () => {
        b.closest("dialog").close();
        $("world").focus();
      }),
  );
  $("dialog-content").onclick = (e) => {
    if (G.world.paused) return;
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.quest) {
      if (b.dataset.claim === "true") {
        if (!G.claimQuest(b.dataset.quest))
          G.toast("부탁을 모두 완료한 뒤 찾아오세요");
      } else G.acceptQuest(b.dataset.quest);
    } else if (b.dataset.sell) {
      if (G.economy.shopSell(G.player, b.dataset.sell, 1)) {
        G.news(G.items[b.dataset.sell].item_name + "을 판매했어요");
        G.game.save();
        G.ui();
        G.openService("shop");
      }
    } else if (b.hasAttribute("data-heal")) {
      G.economy.heal(G.player);
      G.game.save();
      G.ui();
      G.openService("shop");
    } else if (b.dataset.buy) {
      if (!G.economy.buy(G.player, b.dataset.buy))
        G.toast("골드가 부족하거나 매물이 이미 판매되었습니다");
      G.game.save();
      G.ui();
      G.openService("market");
    } else if (b.dataset.cancel) {
      G.economy.cancel(G.player, b.dataset.cancel);
      G.game.save();
      G.ui();
      G.openService("market");
    }
  };
  $("dialog-content").onsubmit = (e) => {
    e.preventDefault();
    if (G.world.paused) return;
    if (e.target.id === "trade-form") {
      const n = G.economy.actor(e.target.dataset.target);
      if (G.economy.transfer(G.player, n, Number($("trade-amount").value))) {
        G.news(n.nickname + "님에게 골드를 보냈어요");
        G.toast("골드가 전달되었습니다");
        $("interaction-dialog").close();
        G.game.save();
        G.ui();
      } else G.toast("잔액과 전송 금액을 확인해주세요");
    } else if (e.target.id === "listing-form") {
      if (
        G.economy.list(
          G.player,
          $("listing-item").value,
          Number($("listing-quantity").value),
          Number($("listing-price").value),
        )
      ) {
        G.game.save();
        G.ui();
        G.openService("market");
      } else G.toast("보유 수량과 가격을 확인해주세요");
    }
  };
  $("world").onclick = (e) => {
    if (!G.game.running) return;
    const rect = e.target.getBoundingClientRect(),
      x = ((e.clientX - rect.left) * 1280) / rect.width,
      y = ((e.clientY - rect.top) * 820) / rect.height;
    const n = G.world.npcs
      .filter((n) => n.online)
      .find((n) => Math.hypot(n.x - x, n.y - y) < 28);
    if (n) G.openTrade(n);
  };
  window.addEventListener("keydown", (e) => {
    if (
      !G.game.running ||
      /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) ||
      document.querySelector("dialog[open]")
    )
      return;
    const key = e.key.toLowerCase();
    if (
      [
        "w",
        "a",
        "s",
        "d",
        "shift",
        "e",
        " ",
        "arrowup",
        "arrowdown",
        "arrowleft",
        "arrowright",
      ].includes(key)
    )
      e.preventDefault();
    G.game.keys.add(key);
    if (!e.repeat && (key === "e" || key === " ")) G.game.interact(key === " ");
  });
  window.addEventListener("keyup", (e) =>
    G.game.keys.delete(e.key.toLowerCase()),
  );
  window.addEventListener("blur", () => G.game.keys.clear());
  document.addEventListener("visibilitychange", () => {
    G.game.keys.clear();
    if (G.game.running) G.game.save();
  });
  window.addEventListener("pagehide", () => {
    if (G.game.running) {
      G.logger.logout(G.player, "page_closed");
      for (const n of G.world.npcs)
        if (n.session_id) G.logger.logout(n, "page_closed");
      G.game.save();
    }
  });
  let frame = performance.now();
  function animate(now) {
    const dt = Math.min(0.05, Math.max(0, (now - frame) / 1000));
    frame = now;
    if (G.game.running) {
      G.game.update(dt);
      G.render.world(G.world.realElapsed);
    } else if (!$("auth-screen").classList.contains("hidden"))
      G.render.welcome(now / 1000);
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
  async function boot() {
    G.store.load();
    G.world = G.store.state.world;
    G.logger.closeOpen();
    $("auth-mode").textContent = G.auth.remote
      ? "Supabase Auth · 게임 데이터는 로컬 저장"
      : "Local Demo Mode · 이 브라우저에 저장됩니다";
    G.render.portrait();
    const user = await G.auth.restore();
    if (G.store.warning) $("auth-message").textContent = G.store.warning;
    if (user) {
      const c = G.store.state.characters.find(
        (c) =>
          c.character_id === G.store.state.activeCharacter &&
          c.user_id === user.user_id,
      );
      if (c) G.game.start(c);
      else G.showCharacters();
    }
  }
  boot().catch((e) => {
    $("auth-message").textContent = e.message;
    console.error(e);
  });
})();
