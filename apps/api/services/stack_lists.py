"""
Stack property lists: find properties appearing on 2+ uploaded Excel/CSV files.

Given multiple lists (lis pendens, code violations, tax delinquent, etc.) this
service normalises addresses and returns only the properties present on two or
more lists — the most motivated sellers.
"""

import io
import logging
import re

logger = logging.getLogger("api.services.stack_lists")

# USPS standard street suffix abbreviations
_STREET_TYPES: dict[str, str] = {
    "alley": "aly", "aly": "aly",
    "avenue": "ave", "ave": "ave",
    "boulevard": "blvd", "blvd": "blvd",
    "circle": "cir", "cir": "cir",
    "court": "ct", "ct": "ct",
    "cove": "cv", "cv": "cv",
    "crossing": "xing", "xing": "xing",
    "drive": "dr", "dr": "dr",
    "expressway": "expy", "expy": "expy",
    "freeway": "fwy", "fwy": "fwy",
    "highway": "hwy", "hwy": "hwy",
    "lane": "ln", "ln": "ln",
    "loop": "loop",
    "parkway": "pkwy", "pkwy": "pkwy",
    "place": "pl", "pl": "pl",
    "plaza": "plz", "plz": "plz",
    "road": "rd", "rd": "rd",
    "route": "rte", "rte": "rte",
    "run": "run",
    "square": "sq", "sq": "sq",
    "street": "st", "st": "st",
    "terrace": "ter", "ter": "ter",
    "trail": "trl", "trl": "trl",
    "way": "way",
}

# Directional abbreviations
_DIRECTIONS: dict[str, str] = {
    "north": "n", "n": "n",
    "south": "s", "s": "s",
    "east": "e", "e": "e",
    "west": "w", "w": "w",
    "northeast": "ne", "ne": "ne",
    "northwest": "nw", "nw": "nw",
    "southeast": "se", "se": "se",
    "southwest": "sw", "sw": "sw",
}

# Strip secondary unit designators (USPS standard)
_UNIT_RE = re.compile(
    r"\s*,?\s*\b(?:apt|apartment|unit|ste|suite|#|lot|room|rm|fl|floor|building|bldg)"
    r"\.?\s*[a-z0-9\-]+\b",
    re.IGNORECASE,
)

# Ordered patterns for address column detection (most → least specific)
_ADDRESS_COL_PATTERNS: list[str] = [
    r"^property\s*address$",
    r"^full\s*address$",
    r"^street\s*address$",
    r"^site\s*address$",
    r"^mailing\s*address$",
    r"^situs\s*address$",
    r"^address\s*1$",
    r"^address$",
    r"^addr$",
    r"^street$",
    r"^location$",
]


def normalize_address(addr: str) -> str:
    """Return a canonical lowercase address string suitable for comparison."""
    if not isinstance(addr, str):
        return ""
    addr = addr.lower().strip()

    # Remove secondary unit designators
    addr = _UNIT_RE.sub("", addr)

    # Strip commas and periods
    addr = re.sub(r"[,.]", " ", addr)

    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr).strip()

    tokens = addr.split()
    normalised: list[str] = []
    for token in tokens:
        clean = token.rstrip(".")
        if clean in _DIRECTIONS:
            normalised.append(_DIRECTIONS[clean])
        elif clean in _STREET_TYPES:
            normalised.append(_STREET_TYPES[clean])
        else:
            normalised.append(clean)

    return " ".join(normalised)


def _detect_address_column(df) -> str | None:
    """Return the column name most likely to contain property addresses."""
    for col in df.columns:
        col_lower = col.lower().strip()
        for pattern in _ADDRESS_COL_PATTERNS:
            if re.match(pattern, col_lower):
                return col

    # Heuristic: column where most values look like "123 Main St"
    for col in df.columns:
        sample = df[col].dropna().head(10).astype(str).tolist()
        addr_hits = sum(
            1 for s in sample if re.search(r"\b\d{1,5}\s+[a-zA-Z]", s)
        )
        if sample and addr_hits >= max(2, len(sample) // 2):
            return col

    return None


def process_stack_lists(
    files: list[dict],
) -> tuple[io.BytesIO, dict]:
    """
    Identify properties appearing on 2+ uploaded property lists.

    Parameters
    ----------
    files
        List of ``{"filename": str, "data": bytes}``.
        Must contain at least 2 spreadsheet entries.

    Returns
    -------
    (excel_buf, summary)
        ``excel_buf`` — seeked-to-start BytesIO of the output workbook.
        ``summary``   — dict with overlap_count, total_rows, lists_processed.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required for the stack lists feature") from exc

    if len(files) < 2:
        raise ValueError(f"At least 2 files required; got {len(files)}")

    # ── Parse files ──────────────────────────────────────────────────────────
    parsed: list[tuple[str, object, str]] = []  # (filename, df, addr_col)
    for file in files:
        filename: str = file["filename"]
        data: bytes = file["data"]
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

        try:
            if ext in ("xlsx", "xls"):
                df = pd.read_excel(io.BytesIO(data), dtype=str)
            elif ext == "csv":
                df = pd.read_csv(io.BytesIO(data), dtype=str)
            else:
                raise ValueError(
                    f"Unsupported format '{ext}' in '{filename}' — use .xlsx, .xls, or .csv"
                )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not read '{filename}': {exc}") from exc

        df = df.dropna(how="all").reset_index(drop=True)

        addr_col = _detect_address_column(df)
        if addr_col is None:
            raise ValueError(
                f"No address column found in '{filename}'. "
                "Expected a column named 'Address', 'Property Address', 'Street', etc."
            )

        logger.info("'%s': %d rows, address column='%s'", filename, len(df), addr_col)
        parsed.append((filename, df, addr_col))

    # ── Find overlap ──────────────────────────────────────────────────────────
    addr_sources: dict[str, set[int]] = {}
    for idx, (filename, df, addr_col) in enumerate(parsed):
        for raw in df[addr_col].astype(str):
            norm = normalize_address(raw)
            if norm:
                addr_sources.setdefault(norm, set()).add(idx)

    overlap: set[str] = {
        addr for addr, sources in addr_sources.items() if len(sources) >= 2
    }
    logger.info(
        "Overlap: %d unique addresses appear in 2+ of %d lists",
        len(overlap),
        len(parsed),
    )

    # ── Build list summaries ──────────────────────────────────────────────────
    list_summaries: list[dict] = []

    if not overlap:
        for filename, df, addr_col in parsed:
            list_summaries.append({
                "filename": filename,
                "total_rows": len(df),
                "matched_rows": 0,
                "address_column": addr_col,
            })
        summary = {
            "overlap_count": 0,
            "total_rows": 0,
            "lists_processed": list_summaries,
        }
        buf_out = io.BytesIO()
        no_overlap_df = pd.DataFrame({
            "Result": ["No overlapping properties found across the uploaded lists"],
            "Lists Checked": [", ".join(f for f, _, _ in parsed)],
        })
        with pd.ExcelWriter(buf_out, engine="openpyxl") as writer:
            no_overlap_df.to_excel(writer, index=False, sheet_name="No Overlap Found")
        buf_out.seek(0)
        return buf_out, summary

    # ── Collect matching rows ─────────────────────────────────────────────────
    result_frames: list = []
    for filename, df, addr_col in parsed:
        df_copy = df.copy()
        df_copy["_norm"] = df_copy[addr_col].astype(str).apply(normalize_address)
        matched = df_copy[df_copy["_norm"].isin(overlap)].drop(columns=["_norm"]).copy()
        matched.insert(0, "Source List", filename)
        list_summaries.append({
            "filename": filename,
            "total_rows": len(df),
            "matched_rows": len(matched),
            "address_column": addr_col,
        })
        result_frames.append(matched)

    result = pd.concat(result_frames, ignore_index=True).sort_values("Source List")

    summary = {
        "overlap_count": len(overlap),
        "total_rows": len(result),
        "lists_processed": list_summaries,
    }

    # ── Write output workbook ─────────────────────────────────────────────────
    buf_out = io.BytesIO()
    with pd.ExcelWriter(buf_out, engine="openpyxl") as writer:
        result.to_excel(writer, index=False, sheet_name="Overlapping Properties")

        # Auto-fit columns on main sheet
        ws = writer.sheets["Overlapping Properties"]
        for col_cells in ws.columns:
            max_width = max(
                (len(str(cell.value or "")) for cell in col_cells),
                default=10,
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_width + 2, 60)

        # Summary tab
        summary_df = pd.DataFrame(list_summaries)
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        ws_sum = writer.sheets["Summary"]
        for col_cells in ws_sum.columns:
            max_width = max(
                (len(str(cell.value or "")) for cell in col_cells),
                default=10,
            )
            ws_sum.column_dimensions[col_cells[0].column_letter].width = min(max_width + 2, 50)

    buf_out.seek(0)
    return buf_out, summary
