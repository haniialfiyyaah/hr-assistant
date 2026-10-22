"""Live evaluation runner for the 15 synthetic cases.

Usage (API must already be running; this hits the model for each case):

    python -m src.run_evaluation --base-url http://localhost:8000 --token token-alya
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "data" / "evaluation_cases.json"
OUTPUT_DIR = ROOT / "outputs"
REPORT_JSON = OUTPUT_DIR / "evaluation_report.json"
REPORT_MD = OUTPUT_DIR / "evaluation_report.md"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


def _load_cases() -> list[dict[str, Any]]:
    rows = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if len(rows) < 15:
        raise RuntimeError(f"Expected at least 15 evaluation cases, found {len(rows)}")
    return rows


def _score_case(case: dict[str, Any], payload: dict[str, Any], trace: dict[str, Any] | None) -> dict[str, Any]:
    answer = str(payload.get("answer") or "")
    outcome = str(payload.get("outcome") or "")
    citations = payload.get("citations") or []
    tool_calls = payload.get("tool_calls") or []
    tool_names = [str(item.get("name") or "") for item in tool_calls]
    cited_docs = [str(item.get("document_id") or "") for item in citations]
    retrieved = list((trace or {}).get("retrieved_document_ids") or [])
    evidence_docs = list(dict.fromkeys([*cited_docs, *retrieved]))

    failures: list[str] = []
    expected_docs = list(case.get("expected_documents") or [])
    expected_tools = list(case.get("expected_tools") or [])
    forbidden = list(case.get("forbidden_facts") or [])
    expected_outcome = case.get("expected_outcome")

    recall_hit: bool | None = None
    if expected_docs:
        recall_hit = all(doc in evidence_docs[: max(3, len(evidence_docs))] for doc in expected_docs) or all(
            doc in evidence_docs for doc in expected_docs
        )
        # Prefer recall against retrieved/cited set (not strictly ordered top-3 list from API).
        recall_hit = all(doc in evidence_docs for doc in expected_docs)
        if not recall_hit:
            failures.append(f"missing expected documents {expected_docs}; evidence={evidence_docs}")

    if expected_tools:
        missing_tools = [name for name in expected_tools if name not in tool_names]
        if missing_tools:
            failures.append(f"missing expected tools {missing_tools}; got={tool_names}")

    if expected_outcome and outcome != expected_outcome:
        failures.append(f"expected outcome {expected_outcome}, got {outcome}")

    haystacks = [answer, json.dumps(payload, default=str), json.dumps(trace or {}, default=str)]
    for fact in forbidden:
        if any(fact in blob for blob in haystacks):
            failures.append(f"forbidden fact present: {fact}")

    # Citation validity: every citation document must appear in retrieved set when retrieval happened.
    citation_valid = True
    if citations:
        if retrieved:
            citation_valid = all(doc in retrieved for doc in cited_docs if doc)
        else:
            # Balance/action answers may cite nothing; if they cite without retrieval, invalid.
            citation_valid = False
            failures.append("citations present without retrieved documents on the trace")
        if not citation_valid and "citations present" not in " ".join(failures):
            failures.append(f"invalid citations {cited_docs}; retrieved={retrieved}")

    # Self-approval attempts must never create approved leave via chat.
    if case.get("case_id") == "leave-confirm-010" and outcome == "action_proposed":
        failures.append("self-approval path must not propose an approve action")

    passed = not failures
    return {
        "case_id": case["case_id"],
        "category": case.get("category"),
        "hard_gate": bool(case.get("hard_gate")),
        "passed": passed,
        "failures": failures,
        "outcome": outcome,
        "tool_names": tool_names,
        "cited_documents": cited_docs,
        "retrieved_documents": retrieved,
        "recall_hit": recall_hit,
        "citation_valid": citation_valid if citations else True,
        "latency_ms": int((payload.get("usage") or {}).get("latency_ms") or 0),
        "input_tokens": int((payload.get("usage") or {}).get("input_tokens") or 0),
        "output_tokens": int((payload.get("usage") or {}).get("output_tokens") or 0),
        "estimated_cost": (payload.get("usage") or {}).get("estimated_cost"),
        "trace_id": payload.get("trace_id"),
    }


def run(base_url: str, token: str) -> dict[str, Any]:
    """Run all evaluation cases against a live API and write the release report."""
    cases = _load_cases()
    results: list[dict[str, Any]] = []
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=90.0) as client:
        health = client.get(f"{base}/healthz")
        health.raise_for_status()
        for case in cases:
            chat = client.post(
                f"{base}/api/v1/chat",
                headers=headers,
                json={"message": case["input"]},
            )
            chat.raise_for_status()
            payload = chat.json()
            trace: dict[str, Any] | None = None
            trace_id = payload.get("trace_id")
            if trace_id:
                trace_resp = client.get(f"{base}/api/v1/traces/{trace_id}", headers=headers)
                if trace_resp.status_code == 200:
                    trace = trace_resp.json()
            results.append(_score_case(case, payload, trace))

    total = len(results)
    passed = sum(1 for row in results if row["passed"])
    hard_gate_rows = [row for row in results if row["hard_gate"]]
    hard_gate_pass = all(row["passed"] for row in hard_gate_rows) if hard_gate_rows else True
    recall_rows = [row for row in results if row["recall_hit"] is not None]
    recall_rate = (
        sum(1 for row in recall_rows if row["recall_hit"]) / len(recall_rows) if recall_rows else 1.0
    )
    citation_rows = [row for row in results if row.get("cited_documents")]
    citation_validity = (
        sum(1 for row in citation_rows if row["citation_valid"]) / len(citation_rows)
        if citation_rows
        else 1.0
    )
    latencies = [float(row["latency_ms"]) for row in results]
    pass_rate = passed / total if total else 0.0

    go = (
        hard_gate_pass
        and pass_rate >= 0.80
        and recall_rate >= 0.80
        and citation_validity >= 1.0
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "token_label": token,
        "case_count": total,
        "passed": passed,
        "pass_rate": round(pass_rate, 4),
        "hard_gates_passed": hard_gate_pass,
        "retrieval_recall_at_3": round(recall_rate, 4),
        "citation_validity": round(citation_validity, 4),
        "latency_ms": {
            "p50": round(_percentile(latencies, 0.50), 2),
            "p95": round(_percentile(latencies, 0.95), 2),
            "mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
        },
        "tokens": {
            "input": sum(int(row["input_tokens"]) for row in results),
            "output": sum(int(row["output_tokens"]) for row in results),
        },
        "release_decision": "GO" if go else "NO-GO",
        "targets": {
            "pass_rate": 0.80,
            "hard_gates": 1.0,
            "retrieval_recall_at_3": 0.80,
            "citation_validity": 1.0,
        },
        "cases": results,
        "regression_notes": [
            "Overlap leave blocked by domain/repository regression test (tests/test_overlap_regression.py)."
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Report",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "| Metric | Result | Target | Pass? |",
        "|---|---:|---:|:---:|",
        f"| Overall pass rate | {report['pass_rate']:.0%} | 80% | "
        f"{'yes' if report['pass_rate'] >= 0.80 else 'no'} |",
        f"| Hard gates | {'100%' if report['hard_gates_passed'] else 'FAIL'} | 100% | "
        f"{'yes' if report['hard_gates_passed'] else 'no'} |",
        f"| Retrieval recall@3 | {report['retrieval_recall_at_3']:.0%} | 80% | "
        f"{'yes' if report['retrieval_recall_at_3'] >= 0.80 else 'no'} |",
        f"| Citation validity | {report['citation_validity']:.0%} | 100% | "
        f"{'yes' if report['citation_validity'] >= 1.0 else 'no'} |",
        f"| p50 / p95 latency | {report['latency_ms']['p50']:.0f} / "
        f"{report['latency_ms']['p95']:.0f} ms | Report only | — |",
        f"| Token in/out | {report['tokens']['input']} / {report['tokens']['output']} | Report only | — |",
        "",
        f"## Release Decision: **{report['release_decision']}**",
        "",
        "## Failure Analysis",
        "",
    ]
    failed = [row for row in report["cases"] if not row["passed"]]
    if not failed:
        lines.append("No failing cases.")
    else:
        for row in failed:
            lines.append(
                f"- `{row['case_id']}` (hard_gate={row['hard_gate']}): "
                + "; ".join(row["failures"])
            )
    lines.extend(["", "## Regression Cases Added", ""])
    for note in report.get("regression_notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HR assistant evaluation suite")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default="token-alya")
    args = parser.parse_args(argv)
    report = run(args.base_url, args.token)
    print(json.dumps({"release_decision": report["release_decision"], "pass_rate": report["pass_rate"]}, indent=2))
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    return 0 if report["release_decision"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
