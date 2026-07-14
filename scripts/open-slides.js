#!/usr/bin/env node
// Opens the slide deck in the default browser. No npm packages required —
// just picks the right OS-native "open a file" command per platform.

const { spawn } = require("child_process");
const path = require("path");

const file = path.join(__dirname, "..", "slides", "loop-engineering-slides.html");

const [cmd, args] =
  process.platform === "darwin" ? ["open", [file]] :
  process.platform === "win32" ? ["cmd", ["/c", "start", "", file]] :
  ["xdg-open", [file]];

const child = spawn(cmd, args, { stdio: "ignore", detached: true });

child.on("error", () => {
  console.log(`Could not auto-open a browser. Open this file manually:\n  ${file}`);
});

child.unref();
console.log(`Opening slides: ${file}`);
