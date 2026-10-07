(() => {
  const G = GF,
    limits = { events: 12000, transactions: 6000, sessions: 3000 };
  G.logger = {
    now() {
      return new Date(G.world?.clock ?? Date.now()).toISOString();
    },
    append(kind, row) {
      const logs = G.store.state.logs;
      logs[kind].push(row);
      if (logs[kind].length > limits[kind]) {
        logs[kind].shift();
        logs.dropped[kind]++;
      }
      return row;
    },
    event(actor, action, extra = {}) {
      if (!actor) return;
      return this.append("events", {
        event_id: G.id("E"),
        timestamp: this.now(),
        user_id: actor.user_id,
        character_id: actor.character_id ?? null,
        session_id: actor.session_id ?? null,
        action_type: action,
        map_id: G.zone(actor.x ?? 0, actor.y ?? 0).id,
        x: Math.round(actor.x ?? 0),
        y: Math.round(actor.y ?? 0),
        target_user_id: null,
        item_id: null,
        quantity: 0,
        gold_delta: 0,
        metadata: {},
        ...extra,
      });
    },
    login(actor, synthetic = false) {
      const id = G.id("S");
      actor.session_id = id;
      this.append("sessions", {
        session_id: id,
        user_id: actor.user_id,
        character_id: actor.character_id,
        login_at: this.now(),
        logout_at: null,
        play_time: 0,
        device_group: synthetic ? actor.device_group : "local_browser",
        ip_group: synthetic ? actor.ip_group : "local_demo",
        synthetic,
      });
      this.event(actor, "login", { metadata: { synthetic } });
      return id;
    },
    logout(actor, reason = "logout") {
      if (!actor.session_id) return;
      this.event(actor, "logout", { metadata: { reason } });
      const s = G.store.state.logs.sessions.find(
        (s) => s.session_id === actor.session_id,
      );
      if (s) {
        s.logout_at = this.now();
        s.play_time = Math.max(
          0,
          (Date.parse(s.logout_at) - Date.parse(s.login_at)) / 1000,
        );
      }
      actor.session_id = null;
    },
    closeOpen() {
      for (const s of G.store.state.logs.sessions) {
        if (!s.logout_at) {
          s.logout_at = this.now();
          s.play_time = Math.max(
            0,
            (Date.parse(s.logout_at) - Date.parse(s.login_at)) / 1000,
          );
          s.close_reason = "page_reload_recovery";
        }
      }
    },
    export(kind) {
      const logs = G.store.state.logs;
      const sessions = logs.sessions.map((s) => ({
        ...s,
        play_time: s.logout_at
          ? s.play_time
          : Math.max(
              0,
              (Date.parse(this.now()) - Date.parse(s.login_at)) / 1000,
            ),
      }));
      let body, filename, mime;
      if (kind === "all") {
        body = JSON.stringify(
          {
            schema_version: 1,
            exported_at: new Date().toISOString(),
            world_time: this.now(),
            clock_scale: G.world?.speed,
            events: logs.events,
            transactions: logs.transactions,
            sessions,
            users: G.store.state.users.map(
              ({ user_id, email, created_at, last_login_at, mode }) => ({
                user_id,
                email,
                created_at,
                last_login_at,
                mode,
              }),
            ),
            ground_truth:
              G.world?.npcs.map((n) => ({
                user_id: n.user_id,
                character_id: n.character_id,
                user_type: n.user_type,
                device_group: n.device_group,
                ip_group: n.ip_group,
              })) ?? [],
            characters: G.store.state.characters,
            retention: { limits, dropped: logs.dropped },
          },
          null,
          2,
        );
        filename = "aetheria-all.json";
        mime = "application/json";
      } else {
        const fields = {
          events: [
            "event_id",
            "timestamp",
            "user_id",
            "character_id",
            "session_id",
            "action_type",
            "map_id",
            "x",
            "y",
            "target_user_id",
            "item_id",
            "quantity",
            "gold_delta",
            "metadata",
          ],
          transactions: [
            "transaction_id",
            "timestamp",
            "sender_id",
            "receiver_id",
            "gold_amount",
            "item_id",
            "quantity",
            "market_price",
            "trade_price",
            "transaction_type",
            "metadata",
          ],
          sessions: [
            "session_id",
            "user_id",
            "character_id",
            "login_at",
            "logout_at",
            "play_time",
            "device_group",
            "ip_group",
            "synthetic",
          ],
        }[kind];
        const cell = (v) =>
          '"' +
          String(
            v !== null && typeof v === "object" ? JSON.stringify(v) : (v ?? ""),
          ).replace(/"/g, '""') +
          '"';
        body =
          "\uFEFF" +
          [
            fields.join(","),
            ...(kind === "sessions" ? sessions : logs[kind]).map((row) =>
              fields.map((f) => cell(row[f])).join(","),
            ),
          ].join("\r\n");
        filename = "aetheria-" + kind + ".csv";
        mime = "text/csv;charset=utf-8";
      }
      const url = URL.createObjectURL(new Blob([body], { type: mime }));
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      return { filename, rows: kind === "all" ? null : logs[kind].length };
    },
  };
})();
