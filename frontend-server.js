const http = require("http");
const fs = require("fs");
const path = require("path");
const port = process.env.PORT || 3000;
const root = __dirname;
const types = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8" };
http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const requested = url.pathname === "/" ? "/index.html" : url.pathname;
  const target = path.resolve(root, "." + requested);
  if (!target.startsWith(root)) { res.writeHead(403); return res.end("Forbidden"); }
  fs.readFile(target, (error, content) => {
    if (error) { res.writeHead(404); return res.end("Not found"); }
    res.writeHead(200, { "Content-Type": types[path.extname(target)] || "application/octet-stream" });
    res.end(content);
  });
}).listen(port, () => console.log(`AgriBridge frontend: http://localhost:${port}`));
