# CSE heat-equation example

This repository is a complete CSE dogfood project for numerical
verification of FTCS and Crank-Nicolson on a dimensionless one-dimensional heat
equation.

## Scientific question

What evidence distinguishes code correctness, discretization error, stability,
convergence, and numerical uncertainty when two finite-difference schemes are
compared with known continuous and discrete reference cases?

The declared problem is

    partial theta / partial Fo = partial^2 theta / partial xi^2

on `0 < xi < 1`, with zero boundary values and
`theta(xi, 0) = sin(pi xi)`. The continuous reference is
`exp(-pi^2 Fo) sin(pi xi)`.

## Reproduce

```bash
uv sync
uv run python scripts/validate_project.py full
```

The full command runs package tests, regenerates and validates retained CSV
results, renders all SVG, PNG, and PDF figures, checks the project-only Zotero
bibliography, and builds the scientific records and tutorial manuscript.

The shorter routine gate is:

```bash
uv run python scripts/validate_project.py quick
```

## Project map

- [Scientific context](docs/scientific/CONTEXT.md)
- [Mathematical formulation](docs/scientific/formulation.tex)
- [Numerical methods](docs/scientific/methods.tex)
- [Verification and uncertainty](docs/scientific/evidence.tex)
- [Retained analysis](analyses/heat_verification/README.md)
- [Research notebook](docs/scientific/notebook/research-notebook.tex)
- [Tutorial manuscript](docs/latex/main.tex)
- [Ten-skill evaluation](evaluation/README.md)

## Retained findings

At `Fo = 0.1`, both methods show second-order combined refinement when
`r = 0.4` is fixed. On the two finest grids, observed `L-infinity` orders are
2.00023 for FTCS and 1.99975 for Crank-Nicolson. With centered-space error
removed by the semidiscrete reference, the observed temporal orders are
1.00047 and 2.00000, respectively. All finest results satisfy their
Richardson-derived value bounds.

The worst-grid-mode oracle distinguishes stability from monotonicity. FTCS
crosses its stability boundary at `r = 0.5`. Crank-Nicolson remains within the
linear amplification bound for positive `r`, but its factor is negative above
`r = 0.5`, so high-frequency components can alternate in sign.

## Bibliography and evidence

Zotero is authoritative. The project cites the Crank and Nicolson record under
`crankPracticalMethodNumerical1947`, DOI
`10.1017/S0305004100023197`. Its historical Method III appears in Section 4,
equation (16), printed pages 54-55; the error-damping discussion is in Section
7(b), printed page 59.

`scripts/sync_bibliography.sh` generates the one-record, path-sanitized
`docs/latex/references.bib` snapshot from the canonical Zotero Better BibTeX
export. The snapshot is never edited by hand.

## Claim boundary

This project supports code and solution verification only. It makes no claim
about material properties, experiments, dimensional prediction, physical
model validation, physical input uncertainty, or model-form uncertainty.

## License

MIT. See [LICENSE](LICENSE).
