"""Tests for the self-contained Product Owner HTML report."""

import json

import report


def sample_metrics():
    methods = {}
    for method in report.METHOD_LABELS:
        methods[method] = {
            "mean": {"recall_at_10": 0.8, "ndcg_at_10": 0.7},
            "best_page_top_3_rate": 0.9 if method == "hybrid" else 0.8,
            "by_query_type": {
                query_type: {"best_page_top_3_rate": 0.5, "recall_at_10": 0.7, "ndcg_at_10": 0.6}
                for query_type in report.TYPE_LABELS
            },
        }
    return {"backend": "offline", "methods": methods}


def test_report_is_one_html_file_with_chart_table_and_product_insights(tmp_path):
    input_path = tmp_path / "metrics.json"
    output_path = tmp_path / "report.html"
    input_path.write_text(json.dumps(sample_metrics()), encoding="utf-8")

    report.write_report(input_path, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "Help search: product view" in html
    assert "Right page in top 3" in html
    assert "Finding:" in html
    assert "Recommendation:" in html
    assert "plotly" in html.lower()
