(() => {
  const G = GF;
  async function derive(password, salt) {
    if (!crypto.subtle)
      throw Error(
        "계정 인증에는 안전한 브라우저 환경이 필요합니다. localhost로 실행하거나 게스트로 체험하세요.",
      );
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(password),
      "PBKDF2",
      false,
      ["deriveBits"],
    );
    const bits = await crypto.subtle.deriveBits(
      {
        name: "PBKDF2",
        salt: new TextEncoder().encode(salt),
        iterations: 120000,
        hash: "SHA-256",
      },
      key,
      256,
    );
    return Array.from(new Uint8Array(bits), (v) =>
      v.toString(16).padStart(2, "0"),
    ).join("");
  }
  G.auth = {
    get remote() {
      return Boolean(G.config.supabaseUrl && G.config.supabaseAnonKey);
    },
    async request(path, body, token) {
      const response = await fetch(
        G.config.supabaseUrl.replace(/\/$/, "") + "/auth/v1/" + path,
        {
          method: body ? "POST" : "GET",
          headers: {
            apikey: G.config.supabaseAnonKey,
            "Content-Type": "application/json",
            ...(token ? { Authorization: "Bearer " + token } : {}),
          },
          ...(body ? { body: JSON.stringify(body) } : {}),
        },
      );
      const data = await response.json();
      if (!response.ok)
        throw Error(
          data.msg ||
            data.error_description ||
            data.message ||
            "인증 요청 실패",
        );
      return data;
    },
    async signIn(email, password, signup = false) {
      email = email.trim().toLowerCase();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || password.length < 8)
        throw Error("올바른 이메일과 8자 이상 비밀번호를 입력하세요.");
      let user;
      if (this.remote) {
        const data = await this.request(
          signup ? "signup" : "token?grant_type=password",
          { email, password },
        );
        if (!data.access_token)
          throw Error("가입 요청을 보냈습니다. 이메일 인증 후 로그인하세요.");
        sessionStorage.setItem("aetheria.token", data.access_token);
        user = G.store.state.users.find((u) => u.user_id === data.user.id);
        if (!user) {
          user = {
            user_id: data.user.id,
            email: data.user.email,
            created_at: data.user.created_at,
            last_login_at: new Date().toISOString(),
            mode: "supabase",
          };
          G.store.state.users.push(user);
        }
      } else {
        user = G.store.state.users.find(
          (u) => u.email === email && u.mode === "local",
        );
        if (signup) {
          if (user) throw Error("이미 가입한 이메일입니다. 로그인해주세요.");
          const salt = G.id("salt");
          user = {
            user_id: G.id("U"),
            email,
            created_at: new Date().toISOString(),
            last_login_at: null,
            mode: "local",
            salt,
            password_hash: await derive(password, salt),
          };
          G.store.state.users.push(user);
        } else if (
          !user ||
          user.password_hash !== (await derive(password, user.salt))
        )
          throw Error("이메일 또는 비밀번호가 일치하지 않습니다.");
      }
      user.last_login_at = new Date().toISOString();
      G.store.state.activeUser = user.user_id;
      G.logger.event(user, "login", {
        map_id: null,
        x: null,
        y: null,
        metadata: { scope: "authentication", mode: user.mode },
      });
      G.store.save();
      return user;
    },
    guest() {
      let user = G.store.state.users.find((u) => u.mode === "guest");
      if (!user) {
        user = {
          user_id: G.id("U"),
          email: null,
          mode: "guest",
          created_at: new Date().toISOString(),
          last_login_at: null,
        };
        G.store.state.users.push(user);
      }
      user.last_login_at = new Date().toISOString();
      G.store.state.activeUser = user.user_id;
      G.logger.event(user, "login", {
        map_id: null,
        x: null,
        y: null,
        metadata: { scope: "authentication", mode: "guest" },
      });
      G.store.save();
      return user;
    },
    async restore() {
      const user = G.store.state.users.find(
        (u) => u.user_id === G.store.state.activeUser,
      );
      if (user?.mode === "supabase") {
        try {
          const token = sessionStorage.getItem("aetheria.token");
          if (!token) throw Error("토큰 없음");
          await this.request("user", null, token);
        } catch {
          G.store.state.activeUser = null;
          G.store.save();
          return null;
        }
      }
      return user;
    },
    logout() {
      const user = G.store.state.users.find(
        (u) => u.user_id === G.store.state.activeUser,
      );
      if (user)
        G.logger.event(user, "logout", {
          map_id: null,
          x: null,
          y: null,
          metadata: { scope: "authentication" },
        });
      G.store.state.activeUser = null;
      G.store.state.activeCharacter = null;
      sessionStorage.removeItem("aetheria.token");
      G.store.save();
    },
  };
})();
