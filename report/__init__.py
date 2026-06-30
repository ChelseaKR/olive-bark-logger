"""Report generation: aggregate events, render accessible HTML with charts.

The report is the deliverable. It must (1) be reproducible from the same event log,
(2) carry a methodology + limitations section, and (3) be accessible — every chart
has a data-table equivalent and nothing relies on color alone.
"""

from __future__ import annotations

__all__ = ["aggregate", "charts", "render"]
