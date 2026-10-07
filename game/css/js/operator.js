(() => {
  const G = GF,
    $ = (id) => document.getElementById(id);
  G.operator = {
    selected: null,
    update() {
      const w = G.world,
        l = G.store.state.logs;
      $("operator-summary").textContent =
        "세계 경과 " +
        (w.elapsed / 3600).toFixed(2) +
        "시간 · 온라인 " +
        w.npcs.filter((n) => n.online).length +
        "/36 · 이벤트 " +
        l.events.length +
        " · 거래 " +
        l.transactions.length +
        " · 세션 " +
        l.sessions.length;
      $("npc-table").innerHTML = w.npcs
        .map(
          (n) =>
            '<tr data-npc="' +
            n.user_id +
            '"><td>' +
            G.escape(n.nickname) +
            "<br><small>" +
            n.user_id +
            '</small></td><td><span class="type-tag">' +
            n.user_type.toUpperCase() +
            "</span></td><td>" +
            (n.online ? n.task?.action || "idle" : "offline") +
            "</td><td>" +
            n.gold +
            "</td><td>" +
            (n.earnedDay === G.logger.now().slice(0, 10)
              ? n.dailyGold || 0
              : 0) +
            "</td><td>" +
            n.received +
            "</td><td>" +
            n.sent +
            "</td><td>" +
            n.trades +
            "</td></tr>",
        )
        .join("");
      $("retention-note").textContent =
        "로컬 로그 상한: 이벤트 12,000 / 거래 6,000 / 세션 3,000. 초과 시 가장 오래된 기록부터 순환합니다. 제외된 행: " +
        JSON.stringify(l.dropped) +
        ". 장기 분석 전 주기적으로 Export 하세요.";
      if (this.selected) {
        const n = w.npcs.find((n) => n.user_id === this.selected);
        if (n) {
          const tx = l.transactions.filter(
              (t) => t.sender_id === n.user_id || t.receiver_id === n.user_id,
            ),
            partners = {};
          for (const t of tx) {
            const id = t.sender_id === n.user_id ? t.receiver_id : t.sender_id;
            partners[id] = (partners[id] || 0) + t.gold_amount;
          }
          $("npc-detail").innerHTML =
            "<strong>" +
            G.escape(n.nickname) +
            " · " +
            n.user_type.toUpperCase() +
            "</strong><br>User ID: " +
            n.user_id +
            "<br>Character: " +
            n.character_id +
            "<br>현재 골드: " +
            n.gold +
            " G<br>누적 획득 골드: " +
            n.earned +
            " G<br>오늘 획득 골드: " +
            (n.earnedDay === G.logger.now().slice(0, 10)
              ? n.dailyGold || 0
              : 0) +
            " G<br>거래량: " +
            tx.reduce((s, t) => s + t.gold_amount, 0) +
            " G<br>받은 골드: " +
            n.received +
            " G<br>보낸 골드: " +
            n.sent +
            " G<br>일일 접속 목표: " +
            (n.duration / 3600).toFixed(1) +
            "시간<br>Device: " +
            n.device_group +
            "<br>IP: " +
            n.ip_group +
            "<br>주요 거래 상대:<br>" +
            Object.entries(partners)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 4)
              .map(([id, v]) => id + " · " + v + " G")
              .join("<br>");
        }
      }
      this.graph();
    },
    graph() {
      const c = $("network").getContext("2d"),
        w = G.world;
      c.clearRect(0, 0, 760, 350);
      const positions = {},
        suspects = w.npcs.filter((n) =>
          ["farm", "mule", "hub"].includes(n.user_type),
        ),
        others = w.npcs.filter((n) => !suspects.includes(n));
      suspects
        .filter((n) => n.user_type === "farm")
        .forEach((n, i) => (positions[n.user_id] = { x: 64, y: 22 + i * 31 }));
      suspects
        .filter((n) => n.user_type === "mule")
        .forEach(
          (n, i) => (positions[n.user_id] = { x: 300, y: 104 + i * 142 }),
        );
      const hub = suspects.find((n) => n.user_type === "hub");
      positions[hub.user_id] = { x: 497, y: 176 };
      others.forEach(
        (n, i) =>
          (positions[n.user_id] = {
            x: 618 + (i % 3) * 47,
            y: 23 + Math.floor(i / 3) * 44,
          }),
      );
      const edges = {};
      for (const t of G.store.state.logs.transactions) {
        if (!positions[t.sender_id] || !positions[t.receiver_id]) continue;
        const key = t.sender_id + "|" + t.receiver_id;
        edges[key] = (edges[key] || 0) + t.gold_amount;
      }
      for (const [key, amount] of Object.entries(edges)) {
        const [from, to] = key.split("|"),
          a = positions[from],
          b = positions[to],
          bad =
            suspects.some((n) => n.user_id === from) &&
            suspects.some((n) => n.user_id === to);
        c.strokeStyle = bad ? "#d499b5aa" : "#c7c7c780";
        c.lineWidth = Math.min(9, Math.max(0.7, amount / 250));
        c.beginPath();
        c.moveTo(a.x, a.y);
        c.lineTo(b.x, b.y);
        c.stroke();
        const angle = Math.atan2(b.y - a.y, b.x - a.x),
          x = b.x - Math.cos(angle) * 12,
          y = b.y - Math.sin(angle) * 12;
        c.fillStyle = c.strokeStyle;
        c.beginPath();
        c.moveTo(x, y);
        c.lineTo(x - Math.cos(angle - 0.5) * 7, y - Math.sin(angle - 0.5) * 7);
        c.lineTo(x - Math.cos(angle + 0.5) * 7, y - Math.sin(angle + 0.5) * 7);
        c.fill();
      }
      for (const n of w.npcs) {
        const p = positions[n.user_id];
        c.fillStyle =
          n.user_type === "hub"
            ? "#b699ca"
            : n.user_type === "mule"
              ? "#d6afbc"
              : n.user_type === "farm"
                ? "#ebcad5"
                : "#d4d8d4";
        c.beginPath();
        c.arc(p.x, p.y, n.user_type === "hub" ? 17 : 9, 0, Math.PI * 2);
        c.fill();
        c.fillStyle = "#7e7188";
        c.font = "9px sans-serif";
        c.textAlign = "left";
        if (suspects.includes(n))
          c.fillText(
            n.user_type.toUpperCase() + " " + n.user_id.slice(-3),
            p.x + 13,
            p.y + 3,
          );
      }
      c.font = "10px sans-serif";
      c.fillStyle = "#ada0aa";
      c.fillText("기타 주민", 630, 343);
    },
  };
  $("operator-toggle").onclick = () => {
    $("operator-dialog").showModal();
    G.game.keys.clear();
    G.operator.update();
  };
  $("npc-table").onclick = (e) => {
    const r = e.target.closest("[data-npc]");
    if (r) {
      G.operator.selected = r.dataset.npc;
      G.operator.update();
    }
  };
  document.querySelectorAll("[data-export]").forEach(
    (b) =>
      (b.onclick = () => {
        G.game.save();
        const r = G.logger.export(b.dataset.export);
        G.toast(r.filename + " 다운로드");
      }),
  );
})();
