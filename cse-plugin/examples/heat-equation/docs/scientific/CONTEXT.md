# Scientific context

## Question and intended use

This project asks what evidence distinguishes code correctness,
discretization error, stability, convergence, and numerical uncertainty for
FTCS and Crank-Nicolson applied to a single Fourier mode of the dimensionless
one-dimensional heat equation. It is a reproducible numerical-verification
tutorial, not a physical prediction.

## Shared vocabulary

| Term | Meaning |
| --- | --- |
| theta | Dimensionless temperature field. |
| xi | Dimensionless position on `0 <= xi <= 1`. |
| Fo | Dimensionless Fourier number. |
| Delta xi | Uniform dimensionless spatial increment. |
| Delta Fo | Uniform dimensionless time increment. |
| r | Diffusion number, `Delta Fo/(Delta xi)^2`. |
| continuous reference | `exp(-pi^2 Fo) sin(pi xi)` for the declared continuum problem. |
| semidiscrete reference | Exact-in-time first mode of the centered spatial operator. |
| discrete amplification oracle | Independently evaluated one-step Fourier-mode factor. |
| code verification | Evidence that code executes the declared discrete equations. |
| solution verification | Evidence that numerical solutions approach a reference under refinement. |
| model validation | Comparison with physical reality or experiments, which is out of scope. |
| numerical uncertainty | Effects of refinement, reference evaluation, linear solves, and floating point. |

## Numerical doctrine

- Require a uniform grid and an integer number of equal time steps ending
  exactly at the declared final `Fo`.
- Reject FTCS when `r = Delta Fo/(Delta xi)^2 > 0.5`.
- Keep the continuous analytic reference and exact-in-time centered-space
  reference separate from the FTCS and Crank-Nicolson amplification oracles.
- Report interior `L-infinity` and RMS field error, monotonic error reduction,
  observed order, and the linear residual where applicable.
- Use `abs(error) <= atol + rtol*abs(reference)` for direct value checks and
  explain both terms from scale, truncation, solver behavior, and floating
  point.

The retained study uses `Fo = 0.1`. Combined refinement holds `r = 0.4` for
`N = 10, 20, 40, 80, 160`; isolated temporal refinement holds `N = 20` and
uses 80 through 1280 steps. The finest-grid tolerance is a factor-two
Richardson estimate with a 1.25 safety factor plus a 64-epsilon floating
allowance. The order tolerance is twice the change between the two finest
observed orders plus propagated floating allowance.

## Scientific map

- [Formulation](formulation.tex)
- [Methods](methods.tex)
- [Verification and uncertainty](evidence.tex)
- [Retained analysis](../../analyses/heat_verification/README.md)
- [Research notebook](notebook/research-notebook.tex)
- [Tutorial manuscript](../latex/main.tex)
- [Writing style](writing/STYLE.md) and [rules](writing/RULES.md)

## Evidence authority

The continuous and semidiscrete references are project derivations. The
Crank-Nicolson historical record is:

    J. Crank and P. Nicolson, "A practical method for numerical evaluation
    of solutions of partial differential equations of the heat-conduction
    type," Mathematical Proceedings of the Cambridge Philosophical Society
    43(1), 50-67 (1947), DOI 10.1017/S0305004100023197.

Zotero parent `NPC9836V` owns the metadata. PDF child `R4GC8HTF` is the source
file, and linked Markdown child `I5DDQJH8` is a fallible extraction used for
navigation. Method III is located in Section 4, equation (16), printed pages
54-55. Its error-mode interpretation is in Section 7(b), printed page 59.
Claims are checked against the PDF, not promoted from extraction alone.

The generated project bibliography contains the cited record under
`crankPracticalMethodNumerical1947` and no local attachment fields.

## Data and uncertainty policy

The repository owns no external dataset. Git tracks package source, tests,
small CSV result tables, figure metadata, and curated SVG, PNG, and PDF
figures. The scripts regenerate every numerical value and plot. Numerical
uncertainty is represented by refinement, Richardson remaining-error
estimates, a safety factor, floating-point allowance, and the maximum
Crank-Nicolson linear residual.

## Claim boundary

Supported claims are limited to the declared dimensionless equation, initial
and boundary conditions, numerical methods, grid sequences, metrics, and
tolerances. The project cannot support dimensional temperatures, material
properties, experimental agreement, physical model validation, physical input
uncertainty, or model-form uncertainty.
