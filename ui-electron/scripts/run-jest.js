const fs = require("fs");
const path = require("path");

const rootDir = path.join(__dirname, "..", ".tmp");
fs.mkdirSync(rootDir, { recursive: true });
fs.mkdirSync(path.join(rootDir, "jest"), { recursive: true });

process.env.TEMP = rootDir;
process.env.TMP = rootDir;
process.env.TMPDIR = rootDir;

require("jest").run(["--passWithNoTests", "--runInBand", "--no-cache"]);