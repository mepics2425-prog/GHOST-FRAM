(() => {
  const G = GF;
  const rounded = (c, x, y, w, h, r, color) => {
    c.fillStyle = color;
    c.beginPath();
    c.roundRect(x, y, w, h, r);
    c.fill();
  };
  function ellipse(c, x, y, rx, ry, color) {
    c.fillStyle = color;
    c.beginPath();
    c.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    c.fill();
  }
  function star(c, x, y, size, color) {
    c.fillStyle = color;
    c.beginPath();
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI) / 4,
        r = i % 2 ? size * 0.3 : size;
      c.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
    }
    c.closePath();
    c.fill();
  }
  function bunny(
    c,
    x,
    y,
    scale,
    color = "#fff6ef",
    time = 0,
    anim = "idle",
    facing = 1,
  ) {
    c.save();
    c.translate(x, y);
    c.scale(scale * facing, scale);
    const bounce =
      anim === "walk" ? Math.sin(time * 10) * 3 : Math.sin(time * 2) * 1.4;
    const lean =
      anim === "attack"
        ? Math.sin(time * 20) * 0.16
        : anim === "gather"
          ? 0.15
          : 0;
    c.rotate(lean);
    ellipse(c, 0, 18, 18, 5, "#68736422");
    c.translate(0, bounce);
    const ear = Math.sin(time * 2) * 3;
    ellipse(c, -8, -28 + ear, 6, 20, color);
    ellipse(c, 8, -29 - ear, 6, 20, color);
    ellipse(c, -8, -29 + ear, 2.6, 13, "#efb8c7");
    ellipse(c, 8, -30 - ear, 2.6, 13, "#efb8c7");
    ellipse(c, 0, 6, 16, 19, color);
    ellipse(c, 0, -8, 22, 20, color);
    ellipse(c, -10, 0, 5, 3, "#f1b9c7");
    ellipse(c, 10, 0, 5, 3, "#f1b9c7");
    const blink = Math.sin(time * 0.8) > 0.991;
    if (blink) {
      rounded(c, -9, -9, 5, 2, 1, "#4d455a");
      rounded(c, 5, -9, 5, 2, 1, "#4d455a");
    } else {
      ellipse(c, -7, -9, 2.1, 3.2, "#4d455a");
      ellipse(c, 7, -9, 2.1, 3.2, "#4d455a");
      ellipse(c, -7.5, -10, 0.6, 0.8, "white");
      ellipse(c, 6.5, -10, 0.6, 0.8, "white");
    }
    ellipse(c, 0, -3, 2, 1.4, "#9d7688");
    c.strokeStyle = "#9d7688";
    c.lineWidth = 1;
    c.beginPath();
    c.moveTo(0, -2);
    c.lineTo(0, 1);
    c.stroke();
    rounded(c, -14, 6, 28, 8, 3, "#aebfd4");
    ellipse(c, -9, 23, 7, 4, color);
    ellipse(c, 9, 23, 7, 4, color);
    if (anim === "gather") {
      star(c, 26, 0, 6, "#eabd6b");
      ellipse(c, 23, 8, 5, 5, color);
    }
    if (anim === "attack") {
      c.strokeStyle = "#f8e49b";
      c.lineWidth = 4;
      c.beginPath();
      c.arc(8, -8, 35, -0.7, 0.9);
      c.stroke();
    }
    if (anim === "damaged") {
      star(c, 28, -15, 8, "#ec91ac");
    }
    c.restore();
  }
  function tree(c, x, y, s = 1) {
    c.save();
    c.translate(x, y);
    c.scale(s, s);
    ellipse(c, 0, 21, 30, 8, "#738c6420");
    rounded(c, -6, -7, 12, 32, 3, "#bca58c");
    ellipse(c, 0, -27, 30, 36, "#8bb69a");
    ellipse(c, -19, -13, 24, 27, "#a0c5a6");
    ellipse(c, 18, -15, 25, 28, "#96c09c");
    ellipse(c, -9, -36, 19, 22, "#b2d2ac");
    ellipse(c, 15, -26, 3, 3, "#e9d6a9");
    c.restore();
  }
  function house(c, x, y, w, color, roof) {
    ellipse(c, x + w / 2, y + 73, w * 0.58, 10, "#718b6920");
    rounded(c, x, y, w, 74, 12, color);
    c.fillStyle = roof;
    c.beginPath();
    c.moveTo(x - 12, y + 8);
    c.quadraticCurveTo(x + w / 2, y - 58, x + w + 12, y + 8);
    c.closePath();
    c.fill();
    rounded(c, x + w / 2 - 12, y + 34, 24, 40, 8, "#a49092");
    rounded(c, x + 12, y + 26, 19, 18, 5, "#fff3c6");
    rounded(c, x + w - 32, y + 26, 19, 18, 5, "#fff3c6");
    c.strokeStyle = "#ddcbbc";
    c.lineWidth = 2;
    c.beginPath();
    c.moveTo(x + 21, y + 26);
    c.lineTo(x + 21, y + 44);
    c.stroke();
    rounded(c, x + w / 2 - 32, y + 12, 64, 16, 5, "#fffaf1");
  }
  function crystal(c, x, y, s = 1) {
    c.save();
    c.translate(x, y);
    c.scale(s, s);
    ellipse(c, 0, 12, 18, 4, "#8685b12a");
    c.fillStyle = "#aaa9e3";
    c.beginPath();
    c.moveTo(-11, 0);
    c.lineTo(-3, -27);
    c.lineTo(9, -17);
    c.lineTo(14, 6);
    c.lineTo(0, 16);
    c.closePath();
    c.fill();
    c.fillStyle = "#d7d4fa";
    c.beginPath();
    c.moveTo(-3, -27);
    c.lineTo(0, 16);
    c.lineTo(-11, 0);
    c.closePath();
    c.fill();
    star(c, 18, -21, 5, "#fff3c2");
    c.restore();
  }
  function berry(c, x, y, s = 1) {
    c.save();
    c.translate(x, y);
    c.scale(s, s);
    ellipse(c, 0, 9, 25, 5, "#758e7320");
    ellipse(c, -9, -1, 19, 17, "#a0c58d");
    ellipse(c, 9, -5, 20, 19, "#b4d4a2");
    for (const [a, b] of [
      [-10, -7],
      [7, -14],
      [9, 4],
    ]) {
      ellipse(c, a, b, 7, 9, "#e799b4");
      ellipse(c, a - 2, b - 3, 2, 2, "#fce0dd");
      star(c, a, b - 9, 5, "#759976");
    }
    c.restore();
  }
  G.render = {
    bunny,
    crystal,
    berry,
    star,
    welcome(t) {
      const c = document.getElementById("welcome-canvas").getContext("2d");
      c.clearRect(0, 0, 650, 430);
      ellipse(c, 325, 363, 230, 37, "#8dadb02b");
      ellipse(c, 327, 350, 230, 36, "#d4e6d6");
      ellipse(c, 527, 84, 37, 37, "#f8e8b5");
      ellipse(c, 541, 75, 33, 34, "#edeaf5");
      for (let i = 0; i < 13; i++)
        star(
          c,
          65 + ((i * 113) % 540),
          45 + ((i * 67) % 230) + Math.sin(t + i) * 4,
          i % 3 ? 3 : 6,
          "#d4bd85",
        );
      tree(c, 140, 310, 1.2);
      tree(c, 523, 295, 0.95);
      tree(c, 95, 344, 0.65);
      berry(c, 446, 351, 1.35);
      crystal(c, 200, 353, 0.9);
      bunny(c, 330, 305, 2.8, "#fff6ef", t);
      for (let i = 0; i < 4; i++)
        ellipse(c, 235 + i * 50, 373 + Math.sin(t + i) * 2, 2, 2, "#f0b5c8");
    },
    world(t) {
      const canvas = document.getElementById("world"),
        c = canvas.getContext("2d"),
        w = G.world;
      c.clearRect(0, 0, 1280, 820);
      for (const z of G.zones) rounded(c, z.x, z.y, z.w, z.h, 0, z.color);
      // Each area is drawn from primitives; nothing is a background image.
      c.strokeStyle = "#d5c5ac";
      c.lineWidth = 58;
      c.lineCap = "round";
      c.beginPath();
      c.moveTo(230, 295);
      c.lineTo(670, 295);
      c.lineTo(1090, 520);
      c.moveTo(300, 295);
      c.lineTo(300, 550);
      c.lineTo(700, 640);
      c.lineTo(1100, 640);
      c.stroke();
      c.strokeStyle = "#efe3cc";
      c.lineWidth = 48;
      c.stroke();
      for (let i = 0; i < 180; i++) {
        const x = (i * 137 + 29) % 1270,
          y = (i * 83 + 55) % 810;
        const z = G.zone(x, y);
        if (z.id === "CAVE_01") continue;
        c.fillStyle = i % 5 === 0 ? "#eeb8c3" : "#8eab842f";
        ellipse(c, x, y, 2.5, 2.5, c.fillStyle);
        if (i % 5 === 0) ellipse(c, x + 4, y - 3, 2, 2, "#f8ecd5");
      }
      // Moon Lake, stepping stones, and a small wooden pier.
      ellipse(c, 190, 659, 153, 104, "#acd0db");
      ellipse(c, 190, 650, 143, 92, "#bcdae2");
      for (let i = 0; i < 9; i++) {
        c.strokeStyle = "#e7f4ef99";
        c.lineWidth = 2;
        c.beginPath();
        c.ellipse(
          90 + i * 22,
          640 + Math.sin(i + t * 0.4) * 27,
          18,
          3,
          0,
          0,
          Math.PI,
        );
        c.stroke();
      }
      rounded(c, 295, 591, 62, 23, 5, "#c8b497");
      for (let i = 0; i < 4; i++)
        rounded(c, 300 + i * 13, 585, 9, 48, 3, "#d4bea0");
      ellipse(c, 115, 683, 14, 6, "#9dbea0");
      ellipse(c, 229, 604, 12, 5, "#9dbea0");
      house(c, 100, 105, 120, "#f5e6d1", "#e9b5c6");
      house(c, 300, 92, 128, "#fff0d5", "#a4c7c7");
      house(c, 375, 240, 92, "#f1e6f3", "#c1b3d8");
      rounded(c, 320, 150, 88, 19, 4, "#fff9ee");
      c.fillStyle = "#877470";
      c.font = "11px sans-serif";
      c.fillText("POPO’S SHOP", 325, 163);
      // Village fountain and the guild gazebo.
      ellipse(c, 252, 365, 43, 22, "#c0ced0");
      ellipse(c, 252, 361, 35, 16, "#9fc7cf");
      ellipse(c, 252, 345, 15, 8, "#f4e9d7");
      rounded(c, 247, 328, 10, 22, 4, "#f4e9d7");
      star(c, 252, 317, 9, "#edcc83");
      rounded(c, 647, 531, 104, 83, 9, "#f6eada");
      for (const x of [656, 734]) rounded(c, x, 524, 9, 86, 3, "#ceb9ab");
      c.fillStyle = "#bfadcd";
      c.beginPath();
      c.moveTo(630, 535);
      c.lineTo(697, 485);
      c.lineTo(765, 535);
      c.closePath();
      c.fill();
      star(c, 697, 516, 10, "#ffe5a4");
      rounded(c, 659, 611, 78, 10, 3, "#c8b3a6");
      for (let i = 0; i < 9; i++) {
        const x = 963 + (i % 3) * 110,
          y = 447 + Math.floor(i / 3) * 142;
        ellipse(c, x, y, 24, 16, "#b6b0cb");
        ellipse(c, x - 4, y - 5, 16, 11, "#c4bdd8");
      }
      for (let i = 0; i < 26; i++) {
        let x = 560 + ((i * 173) % 705),
          y = 60 + ((i * 47) % 325);
        if (y > 145 && x > 570 && x < 1225) continue;
        tree(c, x, y, 0.85 + (i % 3) * 0.12);
      }
      for (const [x, y, s] of [
        [45, 90, 1],
        [470, 95, 0.8],
        [43, 412, 0.9],
        [433, 442, 0.75],
        [44, 540, 0.8],
        [436, 760, 1],
        [566, 742, 0.8],
        [869, 760, 0.8],
        [900, 450, 0.7],
      ])
        tree(c, x, y, s);
      // Map labels are discreet, and type labels never appear on the world.
      c.textAlign = "center";
      c.font = "600 15px sans-serif";
      for (const [label, x, y] of [
        ["MOONBERRY VILLAGE", 262, 55],
        ["MOONBERRY FOREST", 867, 51],
        ["STARLIGHT CAVE", 1102, 438],
        ["MOON LAKE", 180, 492],
        ["GUILD SQUARE", 714, 455],
      ]) {
        c.fillStyle = "#657666";
        c.fillText(label, x, y);
      }
      const drawables = [];
      for (const r of w.resources) {
        if (r.available)
          drawables.push({
            y: r.y,
            draw: () =>
              r.item === "berry" ? berry(c, r.x, r.y) : crystal(c, r.x, r.y),
          });
        else {
          ellipse(c, r.x, r.y, 10, 3, "#80947c30");
        }
      }
      for (const s of w.slimes)
        if (s.hp > 0)
          drawables.push({
            y: s.y,
            draw: () => {
              const bob = Math.sin(t * 3 + s.phase) * 3;
              ellipse(c, s.x, s.y + 15, 22, 5, "#77748822");
              ellipse(
                c,
                s.x,
                s.y + bob,
                23,
                18,
                s.hit && w.realElapsed - s.hit < 0.15 ? "#f8e9ee" : "#9eccb4",
              );
              ellipse(c, s.x - 7, s.y - 4 + bob, 2, 3, "#596c65");
              ellipse(c, s.x + 7, s.y - 4 + bob, 2, 3, "#596c65");
              ellipse(c, s.x - 11, s.y + 3 + bob, 4, 2, "#e9b7c2");
              ellipse(c, s.x + 11, s.y + 3 + bob, 4, 2, "#e9b7c2");
              ellipse(c, s.x - 5, s.y - 12 + bob, 8, 3, "#cde4cc");
              if (s.hp < s.maxHp) {
                rounded(c, s.x - 22, s.y - 30, 44, 4, 2, "#b8afc4");
                rounded(
                  c,
                  s.x - 22,
                  s.y - 30,
                  (44 * s.hp) / s.maxHp,
                  4,
                  2,
                  "#87b49d",
                );
              }
            },
          });
      for (const a of [
        ...G.services,
        ...w.npcs.filter((n) => n.online),
        G.player,
      ])
        drawables.push({
          y: a.y,
          draw: () => {
            const player = a === G.player,
              service = G.services.includes(a);
            if (player) {
              ellipse(c, a.x, a.y + 18, 25, 9, "#fffdf08f");
              c.strokeStyle = "#fff6d7";
              c.lineWidth = 2;
              c.beginPath();
              c.ellipse(a.x, a.y + 18, 25, 9, 0, 0, Math.PI * 2);
              c.stroke();
            }
            bunny(
              c,
              a.x,
              a.y,
              0.85,
              player ? "#fff6ef" : a.color,
              t,
              a.damageUntil > w.realElapsed ? "damaged" : a.anim || "idle",
              a.facing || 1,
            );
            c.font = player ? "bold 12px sans-serif" : "11px sans-serif";
            c.textAlign = "center";
            const name = service ? a.name : a.nickname,
              tw = c.measureText(name).width;
            rounded(
              c,
              a.x - tw / 2 - 5,
              a.y + 28,
              tw + 10,
              17,
              6,
              player ? "#fff9eced" : "#ffffffb8",
            );
            c.fillStyle = player ? "#73638c" : "#6b706e";
            c.fillText(name, a.x, a.y + 40);
            if (service) {
              c.font = "bold 19px sans-serif";
              c.fillStyle = "#b6985d";
              c.fillText(a.id === "quest" ? "!" : "✦", a.x, a.y - 48);
            }
          },
        });
      drawables.sort((a, b) => a.y - b.y).forEach((o) => o.draw());
      if (G.player.pending) {
        const remain = (G.player.pending.finish - w.realElapsed) / 1.1;
        rounded(c, G.player.x - 25, G.player.y - 62, 50, 5, 2, "#e3d6c9");
        rounded(
          c,
          G.player.x - 25,
          G.player.y - 62,
          50 * (1 - G.clamp(remain, 0, 1)),
          5,
          2,
          "#b99acb",
        );
      }
      c.textAlign = "left";
    },
    portrait() {
      const c = document.getElementById("portrait").getContext("2d");
      c.clearRect(0, 0, 96, 96);
      ellipse(c, 48, 48, 46, 46, "#f0e5f2");
      bunny(c, 48, 61, 1.15, "#fff6ef", 0);
    },
  };
})();
