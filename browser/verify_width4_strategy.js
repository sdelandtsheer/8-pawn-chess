const fs = require("fs");
const path = require("path");
const core = require("./tablebase_core.js");

function loadStrategy(name) {
  const filePath = path.join(__dirname, "..", "dist", "w4-strategy", name);

  if (!fs.existsSync(filePath)) {
    console.error("Missing " + filePath + ". Run export_strategy.py for width 4 first.");
    process.exit(2);
  }

  const buffer = fs.readFileSync(filePath);
  const bytes = new Uint8Array(buffer);
  return core.parseStrategyBinary(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
}

function assertLegalStrategyMove(strategy, state, label) {
  const key = core.stateKey(state, 4);
  const entry = strategy.get(key);

  if (!entry) {
    throw new Error(label + ": missing strategy entry for " + key);
  }

  if (!entry.engineTurn) {
    throw new Error(label + ": expected engine-turn entry for " + key);
  }

  const decoded = core.decodeMove(entry.bestMove);
  const legalMove = core.generateLegalMoves(state, 4).find(function (move) {
    return move.from === decoded.from && move.to === decoded.to;
  });

  if (!legalMove) {
    throw new Error(label + ": strategy move is not legal: " + core.moveCoord(decoded));
  }

  return {
    entry: entry,
    move: legalMove
  };
}

const whiteStrategy = loadStrategy("strategy_white.bin");
const blackStrategy = loadStrategy("strategy_black.bin");
const initial = core.initialState(4);
const initialKey = core.stateKey(initial, 4);
const whiteRoot = whiteStrategy.get(initialKey);
const blackRoot = blackStrategy.get(initialKey);

if (!whiteRoot || whiteRoot.outcome !== 1 || whiteRoot.dtm !== 21 || !whiteRoot.engineTurn) {
  throw new Error("Unexpected white root entry: " + JSON.stringify(whiteRoot));
}

if (core.moveCoord(core.decodeMove(whiteRoot.bestMove)) !== "b2b4") {
  throw new Error("Unexpected white root move: " + core.moveCoord(core.decodeMove(whiteRoot.bestMove)));
}

if (!blackRoot || blackRoot.outcome !== 1 || blackRoot.dtm !== 21 || blackRoot.engineTurn) {
  throw new Error("Unexpected black root entry: " + JSON.stringify(blackRoot));
}

for (const humanMove of core.generateLegalMoves(initial, 4)) {
  const child = core.makeMove(initial, humanMove, 4);
  assertLegalStrategyMove(blackStrategy, child, "black reply after " + core.moveCoord(humanMove));
}

const whiteMove = assertLegalStrategyMove(whiteStrategy, initial, "white root").move;
const afterWhite = core.makeMove(initial, whiteMove, 4);
const afterWhiteEntry = whiteStrategy.get(core.stateKey(afterWhite, 4));

if (!afterWhiteEntry || afterWhiteEntry.engineTurn) {
  throw new Error("White strategy child should be a human-turn entry.");
}

console.log(
  JSON.stringify(
    {
      whiteRows: whiteStrategy.size,
      blackRows: blackStrategy.size,
      whiteRootMove: core.moveCoord(core.decodeMove(whiteRoot.bestMove)),
      blackInitialHumanReplies: core.generateLegalMoves(initial, 4).length
    },
    null,
    2
  )
);
