// Zero-dependency local server. Run: node server.cjs
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const root = path.join(__dirname, "game");
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".md": "text/plain; charset=utf-8",
  ".json": "application/json; charset=utf-8",
};
http
  .createServer((req, res) => {
    let filename;
    try {
      filename = path.resolve(
        root,
        "." + decodeURIComponent(req.url.split("?")[0]),
      );
    } catch {
      res.writeHead(400);
      res.end();
      return;
    }
    if (!filename.startsWith(root + path.sep) && filename !== root) {
      res.writeHead(403);
      res.end();
      return;
    }
    if (filename === root || req.url.split("?")[0].endsWith("/"))
      filename = path.join(filename, "index.html");
    fs.readFile(filename, (error, data) => {
      if (error) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }
      res.writeHead(200, {
        "Content-Type":
          types[path.extname(filename)] || "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(data);
    });
  })
  .listen(4173, "127.0.0.1", () =>
    console.log("Aetheria: http://127.0.0.1:4173"),
  );

