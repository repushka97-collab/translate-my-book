from __future__ import annotations

import argparse
import json
import sys
import time
import subprocess
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

# Ensure repo root is on sys.path when running as "python tools/regression_runner.py"
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core_engine.orchestrator.pipeline import run_book_pipeline


@dataclass
class RunResult:
    source_pdf: str
    mode: str
    ok: bool
    book_id: str
    output_dir: str
    export_paths: Dict[str, str]
    qa_status: str
    qa_issues_total: int
    qa_issues_by_type: Dict[str, int]
    qa_issues_by_severity: Dict[str, int]
    paragraph_count: int
    docx_size_bytes: int | None
    json_size_bytes: int | None
    error: str | None
    duration_sec: float | None


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _file_size(path: str | None) -> int | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return p.stat().st_size
    except Exception:
        return None


def _summarize(result: Dict[str, Any], source_pdf: Path, mode: str) -> RunResult:
    book_id = str(result.get("book_id") or "")
    export_paths = dict(result.get("export_paths") or {})
    qa = dict(result.get("qa_report") or {})
    summary = dict(qa.get("summary") or {})

    paragraphs = result.get("paragraph_stream") or []
    paragraph_count = len(paragraphs) if isinstance(paragraphs, list) else 0

    json_path = export_paths.get("json")
    docx_path = export_paths.get("docx_main")

    return RunResult(
        source_pdf=str(source_pdf),
        mode=mode,
        ok=True,
        book_id=book_id,
        output_dir=str(Path("output") / book_id) if book_id else "",
        export_paths=export_paths,
        qa_status=str(qa.get("status") or ""),
        qa_issues_total=_safe_int(summary.get("issues_total"), 0),
        qa_issues_by_type=dict(summary.get("issues_by_type") or {}),
        qa_issues_by_severity=dict(summary.get("issues_by_severity") or {}),
        paragraph_count=paragraph_count,
        docx_size_bytes=_file_size(docx_path),
        json_size_bytes=_file_size(json_path),
        error=None,
        duration_sec=None,
    )


def _summarize_error(source_pdf: Path, mode: str, error: str) -> RunResult:
    return RunResult(
        source_pdf=str(source_pdf),
        mode=mode,
        ok=False,
        book_id="",
        output_dir="",
        export_paths={},
        qa_status="",
        qa_issues_total=0,
        qa_issues_by_type={},
        qa_issues_by_severity={},
        paragraph_count=0,
        docx_size_bytes=None,
        json_size_bytes=None,
        error=error,
        duration_sec=None,
    )


def _git_head() -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        out = (r.stdout or "").strip()
        return out or None
    except Exception:
        return None


def _env_stamp() -> Dict[str, Any]:
    stamp: Dict[str, Any] = {
        "repo_root": str(_REPO_ROOT),
        "python_executable": sys.executable,
        "git_head": _git_head(),
    }
    try:
        import torch  # type: ignore

        stamp["torch_cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            try:
                stamp["torch_cuda_device"] = torch.cuda.get_device_name(0)
            except Exception:
                stamp["torch_cuda_device"] = None
    except Exception as e:
        stamp["torch_cuda_available"] = None
        stamp["torch_error"] = repr(e)
    return stamp


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pipeline on PDFs and write a regression summary JSON."
    )
    parser.add_argument(
        "--pdf", action="append", default=[], help="Path to PDF. Can be repeated."
    )
    parser.add_argument(
        "--pdf-dir",
        action="append",
        default=[],
        help="Directory to scan for PDFs (non-recursive). Can be repeated.",
    )
    parser.add_argument(
        "--mode",
        choices=["dev", "fast", "full"],
        default="dev",
        help="dev is recommended for quick regressions (no translation).",
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        default=0,
        help="Limit number of PDFs to run (0 = no limit).",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately on first failure instead of continuing.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Path to write summary JSON. "
            "If omitted, writes to output/regression_summary_<timestamp>_<mode>.json"
        ),
    )
    args = parser.parse_args()

    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path("output") / f"regression_summary_{ts}_{args.mode}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    pdf_paths: List[Path] = []
    for p in args.pdf:
        pdf_paths.append(Path(p))

    for d in args.pdf_dir:
        dir_path = Path(d)
        if not dir_path.exists():
            raise FileNotFoundError(f"PDF dir not found: {dir_path}")
        for p in sorted(dir_path.glob("*.pdf")):
            # ignore macOS resource-fork files like ._Book1.pdf
            if p.name.startswith("._"):
                continue
            pdf_paths.append(p)

    # de-dup + stable order
    unique: Dict[str, Path] = {}
    for p in pdf_paths:
        unique[str(p)] = p
    pdf_paths = list(unique.values())

    if not pdf_paths:
        raise ValueError("No PDFs provided. Use --pdf and/or --pdf-dir.")

    if args.max_pdfs and args.max_pdfs > 0:
        pdf_paths = pdf_paths[: args.max_pdfs]

    runs: List[RunResult] = []
    env = _env_stamp()
    for idx, pdf_path in enumerate(pdf_paths, start=1):
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        try:
            # ASCII-only log (Windows consoles may choke on Unicode)
            print(f"[REGRESSION] [{idx}/{len(pdf_paths)}] {pdf_path} (mode={args.mode})")
            t0 = time.time()
            result = run_book_pipeline(pdf_path, mode=args.mode)
            rr = _summarize(result, pdf_path, args.mode)
            rr.duration_sec = round(time.time() - t0, 3)
            runs.append(rr)
        except Exception as e:
            rr = _summarize_error(pdf_path, args.mode, repr(e))
            rr.duration_sec = None
            runs.append(rr)
            if args.stop_on_error:
                break

        # Write partial progress so interruptions don't lose everything
        payload = {"mode": args.mode, "env": env, "runs": [r.__dict__ for r in runs]}
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(out_path)

    payload = {"mode": args.mode, "env": env, "runs": [r.__dict__ for r in runs]}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[REGRESSION] Wrote summary: {out_path}")


if __name__ == "__main__":
    main()
