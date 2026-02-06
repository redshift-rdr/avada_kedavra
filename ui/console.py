# -*- coding: utf-8 -*-
"""Console UI management using Rich."""

from rich.console import Console
from rich.table import Table
from rich import box

# Global console instance
console = Console()


def create_results_table() -> Table:
    """Create the results display table.

    Returns:
        Configured Rich Table for displaying request results.
    """
    results_table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.SIMPLE
    )

    results_table.add_column("ID", style="dim", width=6, justify="right")
    results_table.add_column("Payload", max_width=30)
    results_table.add_column("Method", width=8)
    results_table.add_column("URL", max_width=50)
    results_table.add_column("Status", width=8, justify="center")
    results_table.add_column("Size (B)", width=10, justify="right")
    results_table.add_column("Time (s)", width=10, justify="right")
    results_table.add_column("Error/Conditions", max_width=50)

    return results_table
