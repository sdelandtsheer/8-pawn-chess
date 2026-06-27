(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.PawnTablebaseCore = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const WHITE = "w";
  const BLACK = "b";
  const FLAG_CAPTURE = 1;
  const FLAG_DOUBLE = 2;
  const FLAG_EN_PASSANT = 4;
  const FLAG_WINNING = 8;
  const FILES = "abcdefgh";
  const STRATEGY_MAGIC = "PWST";
  const STRATEGY_HEADER_BYTES = 16;
  const STRATEGY_KEY_BYTES = 17;
  const STRATEGY_RECORD_BYTES = 23;
  const STRATEGY_NO_MOVE = 0xffff;
  const STRATEGY_FLAG_ENGINE_TURN = 1;
  const STRATEGY_FLAG_TERMINAL = 2;

  function assertBoardWidth(boardWidth) {
    if (![2, 4, 6, 8].includes(boardWidth)) {
      throw new Error("boardWidth must be 2, 4, 6, or 8");
    }
  }

  function rowOf(index) {
    return Math.floor(index / 8);
  }

  function fileOf(index) {
    return index % 8;
  }

  function squareName(index) {
    return FILES[fileOf(index)] + String(8 - rowOf(index));
  }

  function uiToTablebaseSquare(index) {
    return (7 - rowOf(index)) * 8 + fileOf(index);
  }

  function tablebaseToUiSquare(square) {
    const file = square % 8;
    const rankIndex = Math.floor(square / 8);
    return (7 - rankIndex) * 8 + file;
  }

  function isActiveSquare(index, boardWidth) {
    assertBoardWidth(boardWidth);
    return fileOf(index) < boardWidth;
  }

  function sideOfPiece(piece) {
    if (piece === "P") return WHITE;
    if (piece === "p") return BLACK;
    return null;
  }

  function opposite(side) {
    return side === WHITE ? BLACK : WHITE;
  }

  function initialState(boardWidth) {
    assertBoardWidth(boardWidth);
    const board = new Array(64).fill(null);

    for (let file = 0; file < boardWidth; file++) {
      board[8 + file] = "p";
      board[48 + file] = "P";
    }

    return {
      board: board,
      turn: WHITE,
      epSquare: -1,
      winner: null,
      winReason: null
    };
  }

  function cloneState(state) {
    return {
      board: state.board.slice(),
      turn: state.turn,
      epSquare: state.epSquare,
      winner: state.winner,
      winReason: state.winReason || null
    };
  }

  function isGoalSquare(side, index) {
    const row = rowOf(index);
    return (side === WHITE && row === 0) || (side === BLACK && row === 7);
  }

  function normalizeEpSquare(state, boardWidth) {
    assertBoardWidth(boardWidth);
    if (state.epSquare === -1 || !isActiveSquare(state.epSquare, boardWidth)) return -1;

    const side = state.turn;
    const ownPiece = side === WHITE ? "P" : "p";
    const enemyPiece = side === WHITE ? "p" : "P";
    const capturedPawnSquare = side === WHITE ? state.epSquare + 8 : state.epSquare - 8;

    if (
      capturedPawnSquare < 0 ||
      capturedPawnSquare >= 64 ||
      state.board[capturedPawnSquare] !== enemyPiece
    ) {
      return -1;
    }

    const offsets = side === WHITE ? [7, 9] : [-7, -9];
    const epFile = fileOf(state.epSquare);

    for (const offset of offsets) {
      const from = state.epSquare + offset;
      if (from < 0 || from >= 64) continue;
      if (!isActiveSquare(from, boardWidth)) continue;
      if (Math.abs(fileOf(from) - epFile) !== 1) continue;
      if (state.board[from] === ownPiece) return state.epSquare;
    }

    return -1;
  }

  function stateKey(state, boardWidth) {
    assertBoardWidth(boardWidth);
    let white = 0n;
    let black = 0n;

    for (let index = 0; index < 64; index++) {
      const piece = state.board[index];
      if (!piece || !isActiveSquare(index, boardWidth)) continue;

      const bit = 1n << BigInt(uiToTablebaseSquare(index));
      if (piece === "P") {
        white |= bit;
      } else if (piece === "p") {
        black |= bit;
      }
    }

    const turn = state.turn === BLACK ? 1n : 0n;
    const epSquare = normalizeEpSquare(state, boardWidth);
    const epCode = epSquare === -1 ? 0n : BigInt(uiToTablebaseSquare(epSquare) + 1);

    return (white | (black << 64n) | (turn << 128n) | (epCode << 129n)).toString(16);
  }

  function generateLegalMoves(state, boardWidth) {
    assertBoardWidth(boardWidth);
    if (state.winner) return [];

    const moves = [];
    const side = state.turn;
    const ownPiece = side === WHITE ? "P" : "p";
    const enemyPiece = side === WHITE ? "p" : "P";
    const dir = side === WHITE ? -8 : 8;
    const startRow = side === WHITE ? 6 : 1;

    for (let from = 0; from < 64; from++) {
      if (state.board[from] !== ownPiece || !isActiveSquare(from, boardWidth)) continue;

      const row = rowOf(from);
      const file = fileOf(from);
      const one = from + dir;

      if (
        one >= 0 &&
        one < 64 &&
        isActiveSquare(one, boardWidth) &&
        state.board[one] === null
      ) {
        moves.push({
          from: from,
          to: one,
          capture: false,
          enPassant: false,
          doubleMove: false,
          winning: isGoalSquare(side, one)
        });

        const two = from + 2 * dir;

        if (
          row === startRow &&
          two >= 0 &&
          two < 64 &&
          isActiveSquare(two, boardWidth) &&
          state.board[two] === null
        ) {
          moves.push({
            from: from,
            to: two,
            capture: false,
            enPassant: false,
            doubleMove: true,
            winning: false
          });
        }
      }

      const captureOffsets = side === WHITE ? [-9, -7] : [7, 9];

      for (const offset of captureOffsets) {
        const to = from + offset;
        if (to < 0 || to >= 64 || !isActiveSquare(to, boardWidth)) continue;
        if (Math.abs(fileOf(to) - file) !== 1) continue;

        if (state.board[to] === enemyPiece) {
          moves.push({
            from: from,
            to: to,
            capture: true,
            enPassant: false,
            doubleMove: false,
            winning: isGoalSquare(side, to)
          });
        }

        if (to === state.epSquare) {
          const capturedPawnSquare = side === WHITE ? to + 8 : to - 8;

          if (
            capturedPawnSquare >= 0 &&
            capturedPawnSquare < 64 &&
            state.board[capturedPawnSquare] === enemyPiece
          ) {
            moves.push({
              from: from,
              to: to,
              capture: true,
              enPassant: true,
              doubleMove: false,
              winning: false
            });
          }
        }
      }
    }

    return moves;
  }

  function makeMove(state, move, boardWidth) {
    assertBoardWidth(boardWidth);
    const next = cloneState(state);
    const piece = next.board[move.from];
    const side = sideOfPiece(piece);
    const otherSide = opposite(side);

    next.board[move.from] = null;

    if (move.enPassant) {
      const capturedPawnSquare = side === WHITE ? move.to + 8 : move.to - 8;
      next.board[capturedPawnSquare] = null;
    }

    next.board[move.to] = piece;
    next.epSquare = move.doubleMove ? Math.floor((move.from + move.to) / 2) : -1;
    next.turn = otherSide;

    if (isGoalSquare(side, move.to)) {
      next.winner = side;
      next.winReason = "goal";
      return next;
    }

    if (generateLegalMoves(next, boardWidth).length === 0) {
      next.winner = side;
      next.winReason = "blocked";
    }

    return next;
  }

  function encodeMove(move) {
    const flags =
      (move.capture ? FLAG_CAPTURE : 0) |
      (move.doubleMove ? FLAG_DOUBLE : 0) |
      (move.enPassant ? FLAG_EN_PASSANT : 0) |
      (move.winning ? FLAG_WINNING : 0);

    return uiToTablebaseSquare(move.from) | (uiToTablebaseSquare(move.to) << 6) | (flags << 12);
  }

  function decodeMove(code) {
    const from = code & 0x3f;
    const to = (code >> 6) & 0x3f;
    const flags = (code >> 12) & 0x0f;

    return {
      from: tablebaseToUiSquare(from),
      to: tablebaseToUiSquare(to),
      capture: Boolean(flags & FLAG_CAPTURE),
      doubleMove: Boolean(flags & FLAG_DOUBLE),
      enPassant: Boolean(flags & FLAG_EN_PASSANT),
      winning: Boolean(flags & FLAG_WINNING),
      code: code
    };
  }

  function moveCoord(move) {
    return squareName(move.from) + squareName(move.to);
  }

  function parseJsonlTablebase(text, progressCallback) {
    const table = new Map();
    const lines = text.split(/\r?\n/);

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const row = JSON.parse(line);
      table.set(row.key, {
        outcome: row.outcome,
        dtm: row.dtm,
        bestMove: row.best_move
      });

      if (progressCallback && table.size % 50000 === 0) {
        progressCallback(table.size);
      }
    }

    return table;
  }

  function keyFromLittleEndianBytes(bytes, offset, length) {
    let value = 0n;

    for (let i = length - 1; i >= 0; i--) {
      value = (value << 8n) | BigInt(bytes[offset + i]);
    }

    return value.toString(16);
  }

  function parseStrategyBinary(arrayBuffer, progressCallback) {
    const bytes = new Uint8Array(arrayBuffer);

    if (bytes.length < STRATEGY_HEADER_BYTES) {
      throw new Error("Strategy file is too short.");
    }

    const magic = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
    if (magic !== STRATEGY_MAGIC) {
      throw new Error("Invalid strategy magic: " + magic);
    }

    const version = bytes[4];
    const boardWidth = bytes[5];
    const engineSideCode = bytes[6];
    const recordBytes = bytes[7];

    if (version !== 1) {
      throw new Error("Unsupported strategy version: " + version);
    }

    if (recordBytes !== STRATEGY_RECORD_BYTES) {
      throw new Error("Unsupported strategy record size: " + recordBytes);
    }

    const view = new DataView(arrayBuffer);
    const rows = Number(view.getBigUint64(8, true));
    const expectedBytes = STRATEGY_HEADER_BYTES + rows * recordBytes;

    if (bytes.length !== expectedBytes) {
      throw new Error("Strategy size mismatch: expected " + expectedBytes + ", got " + bytes.length);
    }

    const table = new Map();

    for (let row = 0; row < rows; row++) {
      const offset = STRATEGY_HEADER_BYTES + row * recordBytes;
      const key = keyFromLittleEndianBytes(bytes, offset, STRATEGY_KEY_BYTES);
      const dataOffset = offset + STRATEGY_KEY_BYTES;
      const bestMove = view.getUint16(dataOffset + 3, true);
      const flags = bytes[dataOffset + 5];

      table.set(key, {
        outcome: view.getInt8(dataOffset),
        dtm: view.getUint16(dataOffset + 1, true),
        bestMove: bestMove === STRATEGY_NO_MOVE ? -1 : bestMove,
        engineTurn: Boolean(flags & STRATEGY_FLAG_ENGINE_TURN),
        terminal: Boolean(flags & STRATEGY_FLAG_TERMINAL)
      });

      if (progressCallback && table.size % 50000 === 0) {
        progressCallback(table.size);
      }
    }

    table.boardWidth = boardWidth;
    table.engineSide = engineSideCode === 0 ? WHITE : BLACK;
    table.version = version;

    return table;
  }

  async function blobToTextMaybeGzip(blob, fileName) {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const isGzip =
      bytes.length >= 2 &&
      bytes[0] === 0x1f &&
      bytes[1] === 0x8b &&
      typeof DecompressionStream !== "undefined";

    if (isGzip) {
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      return new Response(stream).text();
    }

    if (
      bytes.length >= 2 &&
      bytes[0] === 0x1f &&
      bytes[1] === 0x8b &&
      typeof DecompressionStream === "undefined"
    ) {
      throw new Error("This browser cannot decompress gzip tablebases.");
    }

    return new TextDecoder().decode(bytes);
  }

  async function fetchTablebase(url, progressCallback) {
    const response = await fetch(url, { cache: "force-cache" });
    if (!response.ok) {
      throw new Error("Failed to load tablebase: HTTP " + response.status);
    }

    const text = await blobToTextMaybeGzip(await response.blob(), url);
    return parseJsonlTablebase(text, progressCallback);
  }

  async function fetchStrategy(url, progressCallback) {
    const response = await fetch(url, { cache: "force-cache" });
    if (!response.ok) {
      throw new Error("Failed to load strategy: HTTP " + response.status);
    }

    return parseStrategyBinary(await response.arrayBuffer(), progressCallback);
  }

  async function loadTablebaseFile(file, progressCallback) {
    const text = await blobToTextMaybeGzip(file, file.name);
    return parseJsonlTablebase(text, progressCallback);
  }

  async function loadStrategyFile(file, progressCallback) {
    return parseStrategyBinary(await file.arrayBuffer(), progressCallback);
  }

  function parseStrategyBase64(base64, progressCallback) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);

    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    return parseStrategyBinary(bytes.buffer, progressCallback);
  }

  return {
    BLACK,
    FLAG_CAPTURE,
    FLAG_DOUBLE,
    FLAG_EN_PASSANT,
    FLAG_WINNING,
    WHITE,
    decodeMove,
    encodeMove,
    fetchTablebase,
    fetchStrategy,
    generateLegalMoves,
    initialState,
    loadTablebaseFile,
    loadStrategyFile,
    makeMove,
    moveCoord,
    normalizeEpSquare,
    parseJsonlTablebase,
    parseStrategyBase64,
    parseStrategyBinary,
    squareName,
    stateKey,
    tablebaseToUiSquare,
    uiToTablebaseSquare
  };
});
