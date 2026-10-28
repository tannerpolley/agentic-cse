"""Copyable LaTeX table helper. Inputs are trusted LaTeX; load booktabs and siunitx.

For long tables also load longtable. Numeric None is an absent term.
Rows are sequences, or strings for full-width sub-headers.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    label: str
    kind: str  # label, number, or citation
    unit: str = ""
    precision: int = 2


def table(columns: list[Column], rows: list, caption: str, note: str = "", long: bool = False) -> str:
    if not columns or any(c.kind not in ("label", "number", "citation") or c.precision < 0 for c in columns):
        raise ValueError("columns must have a supported kind and nonnegative precision")
    environment = "longtable" if long else "tabular"
    spec = " ".join("S" if c.kind == "number" else "l" for c in columns)
    heading = " & ".join("{" + c.label + (" (" + c.unit + ")" if c.unit else "") + "}" for c in columns)
    caption_text = caption + (" " + note if note else "")
    lines = [] if long else [r"\begin{table}"]
    if not long:
        lines.append(r"\caption{" + caption_text + "}")
    lines.append(r"\begin{" + environment + "}{" + spec + "}")
    if long:
        lines.append(r"\caption{" + caption_text + r"}\\")
    lines.extend([r"\toprule", heading + r" \\", r"\midrule"])
    for row in rows:
        if isinstance(row, str):
            lines.append(r"\multicolumn{" + str(len(columns)) + r"}{l}{" + row + r"} \\")
            continue
        if len(row) != len(columns):
            raise ValueError("row length must match columns")
        cells = [("{--}" if value is None else f"{value:.{col.precision}f}") if col.kind == "number" else str(value) for col, value in zip(columns, row)]
        lines.append(" & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{" + environment + "}"])
    if not long:
        lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"
