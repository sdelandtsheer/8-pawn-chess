const assert = require("assert");
const core = require("../browser/tablebase_core.js");

const state = core.initialState(4);
assert.strictEqual(core.stateKey(state, 4), "f0000000000000000000000000f00");

const rootMoves = core.generateLegalMoves(state, 4).map(core.moveCoord);
assert.deepStrictEqual(rootMoves, [
  "a2a3",
  "a2a4",
  "b2b3",
  "b2b4",
  "c2c3",
  "c2c4",
  "d2d3",
  "d2d4"
]);

const decoded = core.decodeMove(9801);
assert.strictEqual(core.moveCoord(decoded), "b2b4");

const table = core.parseJsonlTablebase(
  '{"key":"f0000000000000000000000000f00","outcome":1,"dtm":21,"best_move":9801}\n'
);
const entry = table.get(core.stateKey(state, 4));
assert.strictEqual(entry.outcome, 1);
assert.strictEqual(entry.dtm, 21);
assert.strictEqual(core.moveCoord(core.decodeMove(entry.bestMove)), "b2b4");

const next = core.makeMove(state, decoded, 4);
assert.strictEqual(next.turn, "b");

function computerCanForceWin(entryForPosition, turn, engineSide) {
  if (turn === engineSide) return entryForPosition.outcome === 1;
  return entryForPosition.outcome === -1;
}

assert.strictEqual(computerCanForceWin(entry, "w", "b"), false);
assert.strictEqual(computerCanForceWin({ outcome: -1 }, "w", "b"), true);
assert.strictEqual(computerCanForceWin({ outcome: 1 }, "b", "b"), true);
assert.strictEqual(computerCanForceWin({ outcome: -1 }, "b", "b"), false);
