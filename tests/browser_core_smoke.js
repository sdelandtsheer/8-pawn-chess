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

const strategyBytes = new Uint8Array(16 + 23);
strategyBytes[0] = "P".charCodeAt(0);
strategyBytes[1] = "W".charCodeAt(0);
strategyBytes[2] = "S".charCodeAt(0);
strategyBytes[3] = "T".charCodeAt(0);
strategyBytes[4] = 1;
strategyBytes[5] = 4;
strategyBytes[6] = 0;
strategyBytes[7] = 23;
new DataView(strategyBytes.buffer).setBigUint64(8, 1n, true);

let key = BigInt("0x" + core.stateKey(state, 4));
for (let i = 0; i < 17; i++) {
  strategyBytes[16 + i] = Number(key & 0xffn);
  key >>= 8n;
}

const dataOffset = 16 + 17;
const strategyView = new DataView(strategyBytes.buffer);
strategyView.setInt8(dataOffset, 1);
strategyView.setUint16(dataOffset + 1, 21, true);
strategyView.setUint16(dataOffset + 3, 9801, true);
strategyBytes[dataOffset + 5] = 1;

const strategy = core.parseStrategyBinary(strategyBytes.buffer);
const strategyEntry = strategy.get(core.stateKey(state, 4));
assert.strictEqual(strategy.boardWidth, 4);
assert.strictEqual(strategy.engineSide, "w");
assert.strictEqual(strategyEntry.outcome, 1);
assert.strictEqual(strategyEntry.dtm, 21);
assert.strictEqual(strategyEntry.bestMove, 9801);
assert.strictEqual(strategyEntry.engineTurn, true);
assert.strictEqual(strategyEntry.terminal, false);

function computerCanForceWin(entryForPosition, turn, engineSide) {
  if (turn === engineSide) return entryForPosition.outcome === 1;
  return entryForPosition.outcome === -1;
}

assert.strictEqual(computerCanForceWin(entry, "w", "b"), false);
assert.strictEqual(computerCanForceWin({ outcome: -1 }, "w", "b"), true);
assert.strictEqual(computerCanForceWin({ outcome: 1 }, "b", "b"), true);
assert.strictEqual(computerCanForceWin({ outcome: -1 }, "b", "b"), false);
