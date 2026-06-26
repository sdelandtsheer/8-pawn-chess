from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    core = (ROOT / "tablebase_core.js").read_text(encoding="utf-8")
    template = (ROOT / "wix_width4_template.html").read_text(encoding="utf-8")
    output = template.replace("/* __TABLEBASE_CORE_JS__ */", core)
    (ROOT / "wix_width4_tablebase.html").write_text(output, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
