"""
Natural-language search parser for the Fund Explorer.

Translates free-text queries like:
    "avg 3 year rolling returns over 10"
    "sortino more"
    "alpha more"
    "upcapture higher than 100 and downcapture lower than 100"

into structured metric filters + sort preferences that the metrics
endpoint can apply directly. Fully rule-based — no external API.
"""

import re
from typing import Optional

# Metric column -> list of phrase synonyms (longest/most-specific first).
# The parser strips the matched synonym from the clause before looking for a
# threshold number, so embedded numbers (e.g. the "3" in "3 year rolling
# return") are NOT mistaken for the comparison value.
METRIC_SYNONYMS: dict[str, list[str]] = {
    "rolling_return_avg": [
        "3 years rolling returns", "3 year rolling returns",
        "3 years rolling return", "3 year rolling return",
        "3yr rolling return", "3y rolling return",
        "avg rolling return", "average rolling return",
        "rolling returns", "rolling return", "rolling ret",
    ],
    "sharpe_ratio": ["sharpe ratio", "sharpe"],
    "sortino_ratio": ["sortino ratio", "sortino"],
    "alpha": ["alpha"],
    "beta": ["beta"],
    "up_capture": [
        "upside capture ratio", "upside capture", "up capture ratio",
        "up capture", "upcapture", "up cap", "upside",
    ],
    "down_capture": [
        "downside capture ratio", "downside capture", "down capture ratio",
        "down capture", "downcapture", "down cap", "downside",
    ],
    "fund_cagr": ["cagr", "annualized return", "annualised return"],
}

# Operator phrases (longest first so multi-word phrases win).
# "gte" => >=, "lte" => <=, "eq" => ==
OPERATOR_PHRASES: list[tuple[str, str]] = [
    ("greater than or equal to", "gte"),
    ("less than or equal to", "lte"),
    ("no less than", "gte"),
    ("no more than", "lte"),
    ("at least", "gte"),
    ("at most", "lte"),
    ("greater than", "gte"),
    ("more than", "gte"),
    ("higher than", "gte"),
    ("lower than", "lte"),
    ("less than", "lte"),
    ("equal to", "eq"),
    ("equals", "eq"),
    ("minimum", "gte"),
    ("maximum", "lte"),
    ("above", "gte"),
    ("below", "lte"),
    ("under", "lte"),
    ("over", "gte"),
    ("exactly", "eq"),
    ("higher", "gte"),
    ("greater", "gte"),
    ("lower", "lte"),
    ("more", "gte"),
    ("less", "lte"),
    ("high", "gte"),
    ("good", "gte"),
    ("strong", "gte"),
    ("low", "lte"),
    (">=", "gte"),
    ("<=", "lte"),
    (">", "gte"),
    ("<", "lte"),
    ("=", "eq"),
]

# Metrics where a lower value is better — used to pick a sensible default
# direction when the user gives a number but no explicit operator.
LOWER_IS_BETTER = {"down_capture", "beta"}

_OP_SYMBOL = {"gte": "≥", "lte": "≤", "eq": "="}

_METRIC_LABEL = {
    "rolling_return_avg": "Rolling Return",
    "sharpe_ratio": "Sharpe",
    "sortino_ratio": "Sortino",
    "alpha": "Alpha",
    "beta": "Beta",
    "up_capture": "Up Capture",
    "down_capture": "Down Capture",
    "fund_cagr": "CAGR",
}

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_CLAUSE_SPLIT_RE = re.compile(r"\s+and\s+|\s+but\s+|\s+with\s+|[,;&+]")


def _find_metric(clause: str) -> Optional[tuple[str, str]]:
    """Return (column, matched_synonym) for the first metric found, longest first."""
    candidates: list[tuple[int, str, str]] = []
    for column, synonyms in METRIC_SYNONYMS.items():
        for syn in synonyms:
            if re.search(rf"\b{re.escape(syn)}\b", clause):
                candidates.append((len(syn), column, syn))
    if not candidates:
        return None
    # Prefer the longest (most specific) synonym match.
    _, column, syn = max(candidates, key=lambda c: c[0])
    return column, syn


def _find_operator(text: str) -> Optional[str]:
    """Return the operator type (gte/lte/eq) for the first phrase found."""
    for phrase, op in OPERATOR_PHRASES:
        # Symbols won't have word boundaries; alpha phrases do.
        if phrase.isalpha() or " " in phrase and phrase.replace(" ", "").isalpha():
            pattern = rf"\b{re.escape(phrase)}\b"
        else:
            pattern = re.escape(phrase)
        if re.search(pattern, text):
            return op
    return None


def parse_query(q: str) -> dict:
    """
    Parse a natural-language query into structured filters and sorts.

    Returns a dict:
        {
          "filters": [{"column", "op", "value"}],
          "sorts":   [{"column", "direction"}],
          "search":  Optional[str],          # fallback text search
          "interpreted": [str, ...],         # human-readable summary
          "matched": bool                    # whether anything was understood
        }
    """
    result = {
        "filters": [],
        "sorts": [],
        "search": None,
        "interpreted": [],
        "matched": False,
    }
    if not q or not q.strip():
        return result

    raw = q.strip()
    clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(raw.lower()) if c.strip()]

    for clause in clauses:
        metric = _find_metric(clause)
        if not metric:
            continue
        column, syn = metric
        result["matched"] = True

        # Remove the metric phrase so its embedded numbers don't pollute parsing.
        remainder = re.sub(rf"\b{re.escape(syn)}\b", " ", clause, count=1)

        op = _find_operator(remainder)
        numbers = _NUMBER_RE.findall(remainder)
        label = _METRIC_LABEL[column]

        if numbers:
            value = float(numbers[0])
            if op is None:
                # No explicit operator but a number is present: pick a sensible
                # default based on whether higher or lower is better.
                op = "lte" if column in LOWER_IS_BETTER else "gte"
            result["filters"].append({"column": column, "op": op, "value": value})
            value_str = f"{value:g}"
            result["interpreted"].append(f"{label} {_OP_SYMBOL[op]} {value_str}")
        else:
            # No number -> treat as a sort/ranking preference.
            if op == "lte":
                direction = "asc"
                arrow = "low→high"
            elif op == "gte":
                direction = "desc"
                arrow = "high→low"
            else:
                # Bare metric mention with no direction: default to "more is better"
                # except for lower-is-better metrics.
                if column in LOWER_IS_BETTER:
                    direction, arrow = "asc", "low→high"
                else:
                    direction, arrow = "desc", "high→low"
            result["sorts"].append({"column": column, "direction": direction})
            result["interpreted"].append(f"Sort by {label} ({arrow})")

    # If nothing was understood as a metric, fall back to plain text search so
    # the box still works for fund / AMC names.
    if not result["matched"]:
        result["search"] = raw

    return result
