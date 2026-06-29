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

# Phrases that signal "group the results by scheme category".
_GROUP_BY_CATEGORY_RE = re.compile(
    r"\b(?:per category|in each category|for each category|in every category|"
    r"each category|by category|category[-\s]?wise|categorywise|"
    r"across categories|based on (?:the )?(?:scheme )?categor(?:y|ies)|"
    r"in (?:the )?category)\b"
)
# A 'group/split/organize ... category' phrase, allowing words in between, e.g.
# "group top 5 mutual funds based on category".
_GROUP_VERB_RE = re.compile(
    r"\b(?:group|grouped|grouping|split|segment|organi[sz]e|bucket|categori[sz]e)\b"
    r".{0,40}?\bcategor(?:y|ies)\b"
)
# "top 3" / "best 5" -> rank limit per group.
_TOP_N_RE = re.compile(r"\b(?:top|best|leading|highest)\s+(\d+)\b")
_DEFAULT_TOP_N = 3


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
        "group_by": None,
        "top_n": None,
        "interpreted": [],
        "matched": False,
    }
    if not q or not q.strip():
        return result

    raw = q.strip()
    working = raw.lower()

    # Global modifiers (grouping / top-N) are detected and stripped first so
    # their numbers and keywords don't leak into per-metric clause parsing.
    #
    # Detect 'top N' BEFORE stripping any grouping phrase: a phrase like
    # "group top 5 ... based on category" contains the count, so stripping the
    # group phrase first would swallow it and wrongly fall back to the default.
    top_match = _TOP_N_RE.search(working)
    if top_match:
        result["top_n"] = int(top_match.group(1))
        result["matched"] = True
        working = _TOP_N_RE.sub(" ", working)

    grouped = False
    if _GROUP_BY_CATEGORY_RE.search(working):
        grouped = True
        working = _GROUP_BY_CATEGORY_RE.sub(" ", working)
    if _GROUP_VERB_RE.search(working):
        grouped = True
        working = _GROUP_VERB_RE.sub(" ", working)
    if grouped:
        result["group_by"] = "scheme_category"
        result["matched"] = True
        # Grouping with no explicit count defaults to top 3 per category.
        if result["top_n"] is None:
            result["top_n"] = _DEFAULT_TOP_N

    clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(working) if c.strip()]

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

    # Surface the grouping intent in the human-readable summary (prepended so it
    # reads naturally before the metric conditions).
    if result["group_by"] == "scheme_category":
        result["interpreted"].insert(0, f"Top {result['top_n']} per Category")

    # If nothing was understood at all, fall back to plain text search so the box
    # still works for fund / AMC names.
    if not result["matched"]:
        result["search"] = raw

    return result
