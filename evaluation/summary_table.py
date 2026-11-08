"""
evaluation/summary_table.py - Programmatic score calculation and table generation.

Ingests raw MatchResult or LocalMatchResult objects and computes exact:
- Match points (WIN=1.0, CHOP=0.5, LOSS=0.0)
- Paired BB/deal means, sample standard deviations (ddof=1), and 95% CIs
- Win/Chop/Loss records
- Auto-formatted Markdown and plain text benchmark tables
"""

from __future__ import annotations

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class MatchSummary:
    opponent: str
    verdict: str
    points: float
    mean_bb: float
    ci_low: float
    ci_high: float
    std_bb: float
    stderr_bb: float
    time_seconds: float
    errors: int


def summarize_results(results_dict: Dict[str, Any]) -> List[MatchSummary]:
    """Extract structured summaries directly from match results."""
    summaries = []
    for opp, res in results_dict.items():
        verdict = res.verdict
        if verdict == "AGENT1_WIN":
            pts = 1.0
        elif verdict == "CHOP":
            pts = 0.5
        elif verdict == "AGENT2_WIN":
            pts = 0.0
        elif verdict == "BOTH_FORFEIT":
            pts = 0.0
        else:
            pts = 0.0

        summaries.append(MatchSummary(
            opponent=opp,
            verdict=verdict,
            points=pts,
            mean_bb=res.mean_bb,
            ci_low=res.ci[0],
            ci_high=res.ci[1],
            std_bb=res.std_bb,
            stderr_bb=res.stderr_bb,
            time_seconds=getattr(res, "elapsed_seconds", 0.0),
            errors=getattr(res, "agent1_errors", 0),
        ))
    return summaries


def format_markdown_table(candidate_name: str, summaries: List[MatchSummary]) -> str:
    """Format summaries into a standardized Markdown table with verified totals."""
    total_pts = sum(s.points for s in summaries)
    max_pts = float(len(summaries))
    wins = sum(1 for s in summaries if s.points == 1.0)
    chops = sum(1 for s in summaries if s.points == 0.5)
    losses = sum(1 for s in summaries if s.points == 0.0)

    lines = []
    lines.append(f"### Performance Summary: {candidate_name}")
    lines.append(f"**Record**: {wins} Wins, {chops} Chops, {losses} Losses | **Total Points**: {total_pts:.1f} / {max_pts:.1f} ({total_pts/max_pts*100:.1f}%)\n")
    lines.append("| Opponent | Verdict | Points | Mean BB / deal | 95% Confidence Interval | Std Dev | Time (s) |")
    lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|")

    for s in summaries:
        ci_str = f"[{s.ci_low:+.2f}, {s.ci_high:+.2f}]"
        lines.append(f"| `{s.opponent}` | {s.verdict} | {s.points:.1f} | {s.mean_bb:+.3f} | {ci_str} | {s.std_bb:.2f} | {s.time_seconds:.2f} |")

    return "\n".join(lines)

