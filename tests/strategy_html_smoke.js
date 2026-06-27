const assert = require("assert");
const fs = require("fs");
const path = require("path");
const core = require("../browser/tablebase_core.js");

global.atob =
  global.atob ||
  function (base64) {
    return Buffer.from(base64, "base64").toString("binary");
  };

const htmlPath = path.join(__dirname, "..", "browser", "wix_width4_strategy.html");
const html = fs.readFileSync(htmlPath, "utf8");

function extractConstant(name) {
  const match = html.match(new RegExp('const ' + name + ' = "([^"]*)";'));
  assert(match, "missing constant " + name);
  assert(match[1].length > 0, "empty constant " + name);
  return match[1];
}

assert(!html.includes("__TABLEBASE_CORE_JS__"));
assert(!html.includes("__STRATEGY"));
assert(!html.includes("TABLEBASE_URL"));
assert(html.includes("PawnTablebaseCore"));
assert(html.includes("parseStrategyBase64"));
assert(html.includes("Position hors strategie certifiee."));
assert(html.includes("function tablebaseMood(entry)"));
assert(html.includes('return computerCanForceWin(entry) ? "'));

const whiteStrategy = core.parseStrategyBase64(extractConstant("STRATEGY_WHITE_BASE64"));
const blackStrategy = core.parseStrategyBase64(extractConstant("STRATEGY_BLACK_BASE64"));
const initial = core.initialState(4);
const initialKey = core.stateKey(initial, 4);
const whiteRoot = whiteStrategy.get(initialKey);
const blackRoot = blackStrategy.get(initialKey);

assert.strictEqual(whiteStrategy.boardWidth, 4);
assert.strictEqual(whiteStrategy.engineSide, "w");
assert.strictEqual(blackStrategy.boardWidth, 4);
assert.strictEqual(blackStrategy.engineSide, "b");
assert.strictEqual(whiteRoot.outcome, 1);
assert.strictEqual(whiteRoot.dtm, 21);
assert.strictEqual(whiteRoot.engineTurn, true);
assert.strictEqual(core.moveCoord(core.decodeMove(whiteRoot.bestMove)), "b2b4");
assert.strictEqual(blackRoot.outcome, 1);
assert.strictEqual(blackRoot.dtm, 21);
assert.strictEqual(blackRoot.engineTurn, false);
