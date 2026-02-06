# -*- coding: utf-8 -*-
"""Result export functionality for saving fuzzing results."""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models.condition import ConditionResult


class ResultExporter:
    """Export fuzzing results to various formats."""

    def __init__(self, results: List[Dict[str, Any]]):
        """Initialize exporter with results.

        Args:
            results: List of result dictionaries containing request/response data.
        """
        self.results = results

    def to_json(self, filepath: Path, pretty: bool = True) -> None:
        """Export results as JSON.

        Args:
            filepath: Path to output JSON file.
            pretty: Whether to format JSON with indentation.
        """
        filepath = Path(filepath)

        with open(filepath, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(self.results, f, indent=2, default=str)
            else:
                json.dump(self.results, f, default=str)

    def to_csv(self, filepath: Path) -> None:
        """Export results as CSV.

        Args:
            filepath: Path to output CSV file.
        """
        if not self.results:
            return

        filepath = Path(filepath)

        # Define CSV columns
        fieldnames = [
            'id',
            'payload',
            'method',
            'url',
            'status_code',
            'content_length',
            'response_time',
            'error',
            'conditions_matched'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in self.results:
                # Flatten result for CSV
                row = {
                    'id': result.get('id', ''),
                    'payload': result.get('payload', ''),
                    'method': result.get('method', ''),
                    'url': result.get('url', ''),
                    'status_code': result.get('status_code', ''),
                    'content_length': result.get('content_length', ''),
                    'response_time': result.get('response_time', ''),
                    'error': result.get('error', ''),
                    'conditions_matched': result.get('conditions_matched', '')
                }
                writer.writerow(row)

    def to_html(self, filepath: Path) -> None:
        """Export results as HTML report.

        Args:
            filepath: Path to output HTML file.
        """
        filepath = Path(filepath)

        html_content = self._generate_html_report()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _generate_html_report(self) -> str:
        """Generate HTML report content.

        Returns:
            HTML string with formatted results.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Avada Kedavra Fuzzing Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .info {{ background: #fff; padding: 15px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background: #6b21a8; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f9f9f9; }}
        .status-200 {{ color: #16a34a; font-weight: bold; }}
        .status-300 {{ color: #ca8a04; font-weight: bold; }}
        .status-400 {{ color: #dc2626; font-weight: bold; }}
        .status-500 {{ color: #991b1b; font-weight: bold; }}
        .conditions {{ color: #16a34a; font-weight: bold; }}
        .error {{ color: #dc2626; }}
    </style>
</head>
<body>
    <h1>🧙‍♂️ Avada Kedavra Fuzzing Report</h1>
    <div class="info">
        <strong>Generated:</strong> {timestamp}<br>
        <strong>Total Requests:</strong> {len(self.results)}
    </div>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Payload</th>
                <th>Method</th>
                <th>URL</th>
                <th>Status</th>
                <th>Size (B)</th>
                <th>Time (s)</th>
                <th>Conditions/Error</th>
            </tr>
        </thead>
        <tbody>
"""

        for result in self.results:
            status_code = result.get('status_code', '')
            status_class = ''
            if status_code:
                if 200 <= int(status_code) < 300:
                    status_class = 'status-200'
                elif 300 <= int(status_code) < 400:
                    status_class = 'status-300'
                elif 400 <= int(status_code) < 500:
                    status_class = 'status-400'
                elif int(status_code) >= 500:
                    status_class = 'status-500'

            conditions = result.get('conditions_matched', '')
            error = result.get('error', '')

            condition_error_cell = ''
            if conditions:
                condition_error_cell = f'<span class="conditions">✓ {conditions}</span>'
            elif error:
                condition_error_cell = f'<span class="error">{error}</span>'

            html += f"""            <tr>
                <td>{result.get('id', '')}</td>
                <td>{result.get('payload', '')[:50]}</td>
                <td>{result.get('method', '')}</td>
                <td>{result.get('url', '')[:60]}</td>
                <td class="{status_class}">{status_code}</td>
                <td>{result.get('content_length', '')}</td>
                <td>{result.get('response_time', '')}</td>
                <td>{condition_error_cell}</td>
            </tr>
"""

        html += """        </tbody>
    </table>
</body>
</html>
"""
        return html


def export_results(results: List[Dict[str, Any]], output_path: str, format: str = 'json') -> None:
    """Export results to specified format.

    Args:
        results: List of result dictionaries.
        output_path: Path to output file.
        format: Export format ('json', 'csv', or 'html').
    """
    exporter = ResultExporter(results)
    output_file = Path(output_path)

    if format == 'json':
        exporter.to_json(output_file)
    elif format == 'csv':
        exporter.to_csv(output_file)
    elif format == 'html':
        exporter.to_html(output_file)
    else:
        raise ValueError(f"Unsupported export format: {format}")
