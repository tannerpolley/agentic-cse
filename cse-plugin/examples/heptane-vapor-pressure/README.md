# Heptane vapor pressure against real measurements

Compare an unchanged published Antoine correlation with independent published
measurements. Heptane is a familiar hydrocarbon separation component, and it
was selected because both primary papers could be opened and read in full,
their tables give explicit units, and the retained values have documented
redistribution terms. The comparison covers every measurement inside the
correlation's stated temperature range, with no parameter fitting.

## Reproduce

Use Python 3.11 or newer with NumPy (`python3 -m pip install numpy` in your own
environment). From **this example directory**, one command regenerates the
retained result table, model sweep, summary, notebook includes, and one figure:

```bash
python3 analyses/vapor-pressure/scripts/run.py
```

No network access, SciPy solver, owner-specific packages, plotting package,
Zotero, LaTeX, Snakemake, or hooks are needed. The only third-party numerical
dependency is NumPy; the standard library writes the SVG. An optional positional
output directory lets you reproduce into scratch space without changing the
retained outputs. For example: `python3 analyses/vapor-pressure/scripts/run.py /tmp/heptane-run`.

## Walk through the study

1. **`cse:design` — define the comparison.** Read
   [scientific context](docs/scientific/CONTEXT.md) for question, intended use,
   VP-1, domain, assumptions, metric, the 0.55 kPa allowance,
   and claim boundaries. This is a physical validation exercise for teaching.
2. **`cse:build` — implement the fixed model.** Inspect
   [run.py](analyses/vapor-pressure/scripts/run.py) and
   [model.json](analyses/vapor-pressure/inputs/model.json). Trace K to °C,
   base-10 pressure in mmHg, and mmHg to kPa. No fitting occurs.
3. **`cse:analyze` — run and retain the evidence.** Execute the command above.
   [Input provenance](analyses/vapor-pressure/inputs/provenance.md) identifies
   every measurement's paper, table, row, units, licence, and retrieved-file hash.
   `results/comparison.csv` carries each selected measurement, prediction,
   residual, and uncertainty with units in the headers; `model-curve.csv`
   carries all line coordinates. `summary.json` reports agreement as found.
4. **`cse:summarize` — interpret retained results.** Read
   [notebook.qmd](analyses/vapor-pressure/notebook.qmd). Rendering cannot run
   the model: the notebook has no executable cells. `present.py` can separately
   refresh the figure and includes from retained CSVs. If Quarto is installed,
   `quarto render analyses/vapor-pressure/notebook.qmd --to html` produces its
   presentation view; HTML is an optional, ignored build output.
5. **`cse:review` — independently inspect support.** Check the source tables,
   coefficient conventions, exclusion of the below-range point, residuals,
   figure, tolerance rationale, and limitations together. Independent acceptance
   is pending with the orchestrator; this notebook is not promoted for manuscript
   use. Agreement at four states does not establish a design property package.

## The one result-level test

From `cse-plugin/`, run:

```bash
agent-heavy python3 -m unittest discover -s tests -p test_heptane_example.py -v
```

It runs the full study into a temporary directory and compares predictions
with the four independent measured pressures. It also requires all four source
rows and their published coordinates. The oracle and allowance are described in
the scientific context. To demonstrate the falsifier, temporarily change `mmHg_to_kPa`
from `0.1333224` to `1.333224` in `inputs/model.json`, rerun the test, then
restore the file and rerun. Do not retain altered results. The delivery report
records the observed failing and restored runs. During preparation the tenfold
conversion error failed at Table 2 row 2: absolute residual 70.0127845205767 kPa
exceeded 0.55 kPa. Restoring the conversion made the same test pass. The test
writes only temporary outputs, so the retained results were never overwritten
by the deliberately broken run.

## Attribution

Measurements are transcribed and adapted from Busch, Kasterke, Brands, Bardow,
and Flake (2026), DOI [10.1021/acs.jced.5c00843](https://doi.org/10.1021/acs.jced.5c00843),
Table 2, heptane rows 1–5, under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Preserve that
attribution and licence with the CSV. Parameters come from Willingham, Taylor,
Pignocco, and Rossini (1945), DOI
[10.6028/jres.035.009](https://doi.org/10.6028/jres.035.009), Table 3, n-Heptane
row. See the provenance record for the NIST public-domain finding, conversion
sources, full downloaded-file hashes, and exact locators. No paper is committed.
