"""Create a self-contained Product Owner report from the saved evaluation results."""

import argparse
import html
import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "results" / "metrics.json"
DEFAULT_OUTPUT = ROOT / "results" / "report.html"

METHOD_LABELS = {
    "bm25": "Keyword match",
    "vector": "Meaning match",
    "hybrid": "Combined match",
    "hybrid_segment": "Combined + audience focus",
}
TYPE_LABELS = {
    "navigational": "Finding a known page",
    "informational": "Understanding a topic",
    "transactional": "Completing an action",
}


def load_metrics(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    """Read the version-controlled output of the evaluation step."""

    return json.loads(path.read_text(encoding="utf-8"))


def percentage(value: float) -> str:
    """Format a 0–1 score as a whole percentage for a non-technical reader."""

    return f"{value * 100:.0f}%"


def out_of_ten(value: float) -> str:
    """Express a rate as an easy-to-say number of searches out of ten."""

    rate = f"{value * 10:.1f}".rstrip("0").rstrip(".")
    return f"{rate} out of 10 searches"


def comparison_chart(methods: dict[str, Any]) -> str:
    """Build an inline Plotly chart; no browser connection is needed to view it."""

    method_ids = list(METHOD_LABELS)
    labels = [METHOD_LABELS[method] for method in method_ids]
    figure = go.Figure()
    figure.add_bar(
        name="Right page in top 3",
        x=labels,
        y=[methods[method]["best_page_top_3_rate"] * 100 for method in method_ids],
        marker_color="#007a78",
        hovertemplate="%{x}: %{y:.0f}%<extra></extra>",
    )
    figure.add_bar(
        name="Helpful pages shown",
        x=labels,
        y=[methods[method]["mean"]["recall_at_10"] * 100 for method in method_ids],
        marker_color="#5b6ee1",
        hovertemplate="%{x}: %{y:.0f}%<extra></extra>",
    )
    figure.update_layout(
        barmode="group",
        height=430,
        margin={"l": 50, "r": 30, "t": 55, "b": 95},
        title="How often people see useful help near the top",
        yaxis={"title": "Searches (%)", "range": [0, 100]},
        legend={"orientation": "h", "y": 1.13},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font={"family": "Arial, sans-serif", "color": "#172033"},
    )
    return figure.to_html(full_html=False, include_plotlyjs=True, config={"displayModeBar": False})


def query_type_rows(methods: dict[str, Any]) -> str:
    """Render the product-friendly query-type comparison table."""

    rows = []
    for query_type in ("navigational", "informational", "transactional"):
        for method in METHOD_LABELS:
            scores = methods[method]["by_query_type"][query_type]
            rows.append(
                "<tr>"
                f"<td>{html.escape(TYPE_LABELS[query_type])}</td>"
                f"<td>{html.escape(METHOD_LABELS[method])}</td>"
                f"<td>{out_of_ten(scores['best_page_top_3_rate'])}</td>"
                f"<td>{percentage(scores['recall_at_10'])}</td>"
                f"<td>{percentage(scores['ndcg_at_10'])}</td>"
                "</tr>"
            )
    return "\n".join(rows)


def insights(methods: dict[str, Any]) -> list[dict[str, str]]:
    """Create three evidence-based statements in Product Owner language."""

    best_method = max(
        METHOD_LABELS,
        key=lambda method: (
            methods[method]["best_page_top_3_rate"],
            methods[method]["mean"]["recall_at_10"],
        ),
    )
    weakest_type = min(
        TYPE_LABELS,
        key=lambda query_type: methods["hybrid"]["by_query_type"][query_type]["best_page_top_3_rate"],
    )
    combined_rate = methods["hybrid"]["best_page_top_3_rate"]
    audience_rate = methods["hybrid_segment"]["best_page_top_3_rate"]
    return [
        {
            "finding": (
                f"{METHOD_LABELS[best_method]} puts the right page in the top 3 for "
                f"{out_of_ten(methods[best_method]['best_page_top_3_rate'])}."
            ),
            "so_what": "People can reach the help they need with less scrolling and fewer retries.",
            "recommendation": "Use this approach as the default for the next prototype demo.",
        },
        {
            "finding": (
                f"{TYPE_LABELS[weakest_type]} is weakest: the right page is in the top 3 for only "
                f"{out_of_ten(methods['hybrid']['by_query_type'][weakest_type]['best_page_top_3_rate'])}."
            ),
            "so_what": "People looking for a specific destination may still need to scan several results.",
            "recommendation": "Make contact and destination pages easier to name and add prominent shortcuts for common requests.",
        },
        {
            "finding": (
                "Tailoring results for private or business customers changes the top-3 rate from "
                f"{out_of_ten(combined_rate)} to {out_of_ten(audience_rate)}."
            ),
            "so_what": "Extra tailoring can sometimes hide a generally useful page.",
            "recommendation": "Keep this tailoring optional for now and test it with more representative business and private scenarios.",
        },
    ]


def insight_cards(items: list[dict[str, str]]) -> str:
    """Render the finding → so what → recommendation structure as readable cards."""

    cards = []
    for item in items:
        cards.append(
            "<article class='insight'>"
            f"<p><strong>Finding:</strong> {html.escape(item['finding'])}</p>"
            f"<p><strong>So what:</strong> {html.escape(item['so_what'])}</p>"
            f"<p><strong>Recommendation:</strong> {html.escape(item['recommendation'])}</p>"
            "</article>"
        )
    return "\n".join(cards)


def build_html(metrics: dict[str, Any]) -> str:
    """Create the complete standalone HTML document from saved metrics only."""

    methods = metrics["methods"]
    chart = comparison_chart(methods)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Help search product report</title>
  <style>
    body {{ margin: 0; background: #f1f5f9; color: #172033; font-family: Arial, sans-serif; line-height: 1.5; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }}
    header {{ background: #073b4c; color: white; border-radius: 16px; padding: 28px 32px; }}
    h1 {{ margin: 0 0 6px; font-size: 30px; }} h2 {{ margin-top: 34px; font-size: 22px; }}
    .subtitle {{ margin: 0; opacity: .9; }} .panel {{ background: white; border-radius: 14px; padding: 24px; margin-top: 18px; }}
    .note {{ color: #475569; margin-top: 0; }} .insights {{ display: grid; gap: 14px; }}
    .insight {{ background: #eaf6f5; border-left: 5px solid #007a78; border-radius: 8px; padding: 14px 18px; }}
    .insight p {{ margin: 6px 0; }} table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #dbe4ee; padding: 11px 8px; text-align: left; }} th {{ background: #eef4f8; }}
    footer {{ color: #64748b; font-size: 13px; margin-top: 24px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Help search: product view</h1>
      <p class="subtitle">A plain-language view of {metrics['backend']} results from 25 fictional Dutch help searches.</p>
    </header>
    <section class="panel">
      <h2>Which approach helps people most?</h2>
      <p class="note">“Right page in top 3” is the plain-language companion to the quality score: it shows how often the best-rated page is close enough to see without scrolling far.</p>
      {chart}
    </section>
    <section class="panel">
      <h2>What this means for the product</h2>
      <div class="insights">{insight_cards(insights(methods))}</div>
    </section>
    <section class="panel">
      <h2>Results by search need</h2>
      <p class="note">“Helpful pages shown” means that useful pages appeared in the first ten results. “Overall result quality” rewards putting the best pages first.</p>
      <table>
        <thead><tr><th>Search need</th><th>Approach</th><th>Right page in top 3</th><th>Helpful pages shown</th><th>Overall result quality</th></tr></thead>
        <tbody>{query_type_rows(methods)}</tbody>
      </table>
    </section>
    <footer>Generated from results/metrics.json. All pages, queries, and labels are fictional.</footer>
  </main>
</body>
</html>
"""


def write_report(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Read metrics and write one HTML file that can be opened without a web server."""

    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(build_html(load_metrics(input_path)), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a self-contained Product Owner HTML report.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Evaluation JSON input path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="HTML output path.")
    arguments = parser.parse_args()
    try:
        path = write_report(arguments.input, arguments.output)
        print(f"Saved self-contained report: {path}")
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Report error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
