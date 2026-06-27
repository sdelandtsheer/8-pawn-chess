import base64
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def replace_block(text: str, pattern: str, replacement: str) -> str:
    next_text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement for {pattern!r}, got {count}")
    return next_text


def read_strategy_base64(name: str) -> str:
    path = REPO / "dist" / "w4-strategy" / name
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def strategy_constants() -> str:
    constants = "\n".join(
        [
            'const STRATEGY_WHITE_URL = "";',
            'const STRATEGY_BLACK_URL = "";',
            f'const STRATEGY_WHITE_BASE64 = "{read_strategy_base64("strategy_white.bin")}";',
            f'const STRATEGY_BLACK_BASE64 = "{read_strategy_base64("strategy_black.bin")}";',
        ]
    )
    return textwrap.indent(constants, "  ")


def main() -> int:
    core = (ROOT / "tablebase_core.js").read_text(encoding="utf-8")
    html = (ROOT / "wix_width4_template.html").read_text(encoding="utf-8")
    html = html.replace("/* __TABLEBASE_CORE_JS__ */", core)
    html = html.replace("Charge la tablebase largeur 4.", "Charge la strategie largeur 4.")
    html = html.replace(
        'depthDisplayDiv.textContent = "Tablebase : " + tableText;',
        'depthDisplayDiv.textContent = "Strategie : " + tableText;',
    )
    html = html.replace(
        'updateEnginePanel("â€”", "tablebase non chargÃ©e", "â€”");',
        'updateEnginePanel("â€”", "strategie non chargee", "â€”");',
    )
    html = html.replace('const TABLEBASE_URL = "";', strategy_constants())
    html = html.replace(
        "let tablebase = null;",
        "let strategies = { w: null, b: null };\n  let tablebase = null;",
    )
    html = html.replace("function formatTablebaseRows", "function formatStrategyRows")
    html = html.replace("formatTablebaseRows", "formatStrategyRows")

    html = replace_block(
        html,
        (
            r"async function installTablebase\(loader\) \{.*?\n"
            r"  if \(TABLEBASE_URL\) \{.*?\n"
            r"  \} else \{\n"
            r"    updateStatus\(\"Configure TABLEBASE_URL\.\"\);\n"
            r"  \}"
        ),
        """
  async function loadOneStrategy(url, base64, progress) {
    if (base64) {
      return core.parseStrategyBase64(base64, progress);
    }
    if (url) {
      return core.fetchStrategy(url, progress);
    }
    return null;
  }

  async function installStrategies() {
    startButton.disabled = true;
    updateEnginePanel("chargement", "â€”", "â€”");

    strategies.w = await loadOneStrategy(
      STRATEGY_WHITE_URL,
      STRATEGY_WHITE_BASE64,
      function (rows) {
        updateEnginePanel(formatStrategyRows(rows), "chargement", "â€”");
      }
    );
    strategies.b = await loadOneStrategy(
      STRATEGY_BLACK_URL,
      STRATEGY_BLACK_BASE64,
      function (rows) {
        updateEnginePanel(formatStrategyRows(rows), "chargement", "â€”");
      }
    );

    if (!strategies.w || !strategies.b) {
      updateEnginePanel("erreur", "chargement impossible", "â€”");
      updateStatus("Configure les strategies.");
      return;
    }

    updateEnginePanel(formatStrategyRows(strategies.w.size + strategies.b.size), "prete", "â€”");
    updateStatus("Choisis ta couleur.");
    startButton.disabled = false;
  }

  installStrategies().catch(function () {
    updateEnginePanel("erreur", "chargement impossible", "â€”");
    updateStatus("Strategie indisponible.");
  });
""",
    )

    html = replace_block(
        html,
        r"function requestEngineMove\(\) \{.*?\n  function startGame\(\)",
        """
  function requestEngineMove() {
    if (!state || state.winner || state.turn !== engineSide) return;

    engineThinking = true;

    const lookup = tablebaseLookup(state);
    let move = null;

    if (lookup.entry && lookup.entry.engineTurn && lookup.entry.bestMove !== -1) {
      move = findLegalDecodedMove(core.decodeMove(lookup.entry.bestMove));
      updateEnginePanel(
        formatStrategyRows(tablebase.size),
        tablebaseMood(lookup.entry),
        String(lookup.entry.dtm)
      );
    }

    if (!move) {
      engineThinking = false;
      updateEnginePanel(formatStrategyRows(tablebase ? tablebase.size : 0), "miss", "â€”");
      updateStatus("Position hors strategie certifiee.");
      return;
    }

    engineThinking = false;

    addMoveToHistory(state, move);
    state = core.makeMove(state, move, BOARD_WIDTH);
    lastMove = { from: move.from, to: move.to };
    renderBoard();

    if (state.winner) {
      finishGame();
    } else {
      updateStatus("A toi de jouer.");
    }
  }

  function startGame()""",
    )

    html = replace_block(
        html,
        r"function startGame\(\) \{.*?\n  startButton\.addEventListener",
        """
  function startGame() {
    const sideInput = document.querySelector("input[name='side']:checked");
    humanSide = sideInput.value;
    engineSide = opposite(humanSide);
    tablebase = strategies[engineSide];

    if (!tablebase) {
      updateStatus("Charge la strategie avant de commencer.");
      return;
    }

    state = core.initialState(BOARD_WIDTH);
    selectedSquare = null;
    legalMovesForSelected = [];
    engineThinking = false;
    lastMove = null;
    moveHistory = [];

    resetPointerDrag();
    modal.style.display = "none";

    renderBoard();
    renderNotation();

    const lookup = tablebaseLookup(state);
    updateEnginePanel(
      formatStrategyRows(tablebase.size),
      tablebaseMood(lookup.entry),
      lookup.entry ? String(lookup.entry.dtm) : "â€”"
    );

    if (humanSide === "w") {
      updateStatus("A toi de jouer.");
    } else {
      updateStatus("L'ordinateur joue depuis la strategie...");
      setTimeout(requestEngineMove, 100);
    }
  }

  startButton.addEventListener""",
    )

    html = replace_block(
        html,
        (
            r"const lookup = tablebaseLookup\(state\);\n"
            r"    updateEnginePanel\(\n"
            r"      formatStrategyRows\(tablebase\.size\),\n"
            r"      tablebaseMood\(lookup\.entry\),\n"
            r"      lookup\.entry \? String\(lookup\.entry\.dtm\) : \".*?\"\n"
            r"    \);\n"
            r"    updateStatus\(\"L.*?ordinateur joue depuis la tablebase\.\.\.\"\);\n"
            r"    setTimeout\(requestEngineMove, 80\);"
        ),
        """
    const lookup = tablebaseLookup(state);
    updateEnginePanel(
      formatStrategyRows(tablebase.size),
      tablebaseMood(lookup.entry),
      lookup.entry ? String(lookup.entry.dtm) : "â€”"
    );

    if (!lookup.entry || !lookup.entry.engineTurn) {
      updateEnginePanel(formatStrategyRows(tablebase.size), "miss", "â€”");
      updateStatus("Position hors strategie certifiee.");
      return;
    }

    updateStatus("L'ordinateur joue depuis la strategie...");
    setTimeout(requestEngineMove, 80);""",
    )

    html = html.replace("tablebase non chargÃƒÂ©e", "strategie non chargee")
    html = html.replace("tablebase non chargÃ©e", "strategie non chargee")
    html = html.replace(
        "LÃ¢â\u201a¬â„¢ordinateur joue depuis la strategie",
        "L'ordinateur joue depuis la strategie",
    )
    html = html.replace("Ãƒâ\u201a¬ toi de jouer.", "A toi de jouer.")
    html = html.replace("Ã¢â\u201a¬â€", "â€”")
    html = html.replace("prÃƒÂªte", "prete")

    (ROOT / "wix_width4_strategy.html").write_text(html, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
