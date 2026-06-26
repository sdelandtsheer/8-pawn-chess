const fs = require("fs");
const path = require("path");
const core = require("./tablebase_core.js");

const tablePath = path.join(__dirname, "..", "dist", "w4", "tablebase.jsonl");

if (!fs.existsSync(tablePath)) {
  console.error("Missing dist/w4/tablebase.jsonl. Run the width 4 export first.");
  process.exit(2);
}

const text = fs.readFileSync(tablePath, "utf8");
const table = core.parseJsonlTablebase(text, function (rows) {
  if (rows % 250000 === 0) {
    console.error("loaded=" + rows);
  }
});

const state = core.initialState(4);
const initialKey = core.stateKey(state, 4);
const initialEntry = table.get(initialKey);

if (!initialEntry) {
  throw new Error("Initial width 4 position is missing from the tablebase.");
}

if (initialEntry.outcome !== 1 || initialEntry.dtm !== 21) {
  throw new Error(
    "Unexpected initial result: " + JSON.stringify(initialEntry)
  );
}

const bestMove = core.decodeMove(initialEntry.bestMove);
if (core.moveCoord(bestMove) !== "b2b4") {
  throw new Error("Unexpected best move: " + core.moveCoord(bestMove));
}

const legalBestMove = core.generateLegalMoves(state, 4).find(function (move) {
  return move.from === bestMove.from && move.to === bestMove.to;
});

if (!legalBestMove) {
  throw new Error("Decoded best move is not legal in the initial position.");
}

const child = core.makeMove(state, legalBestMove, 4);
const childEntry = table.get(core.stateKey(child, 4));

if (!childEntry) {
  throw new Error("Child after best move is missing from the tablebase.");
}

if (childEntry.outcome !== -1 || childEntry.dtm !== 20) {
  throw new Error("Unexpected child result: " + JSON.stringify(childEntry));
}

console.log(
  JSON.stringify(
    {
      rows: table.size,
      initialKey: initialKey,
      outcome: initialEntry.outcome,
      dtm: initialEntry.dtm,
      bestMove: core.moveCoord(bestMove),
      childOutcome: childEntry.outcome,
      childDtm: childEntry.dtm
    },
    null,
    2
  )
);
