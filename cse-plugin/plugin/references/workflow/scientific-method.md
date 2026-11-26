# Scientific method

## Design the question

For substantive work, establish:

- the scientific question and intended use;
- the governing equations, correlations, or conceptual model;
- symbols, units, bases, conventions, and validity bounds;
- assumptions and excluded phenomena;
- inputs, data sources, and source locators;
- the numerical or analytical method;
- reference cases and independent comparisons;
- metrics, tolerances and their origin for correctness checks, and comparisons for agreement with data;
- sensitivity, convergence, uncertainty, and comparison studies;
- claims the work may support and claims it cannot support;
- known limitations and unresolved questions.

Do not turn uncertainty into implementation tasks before the formulation is clear enough to test. Use a small calculation or disposable prototype when it can resolve a method choice more cheaply than discussion.

## Equation doctrine

Give each durable equation or correlation a stable identifier. Record its source, exact locator, status, symbols, units or basis, assumptions, validity domain, and implementation and test links. Preserve alternate conventions as named alternatives. Never overwrite one basis or standard state with another.

Separate three documents when the project needs them:

- `docs/scientific/formulation.md` for governing equations, correlations, symbols, assumptions, and validity domains;
- `docs/scientific/methods.md` for discretization, algorithms, initialization, iteration, stopping tests, failure modes, and outputs;
- `docs/scientific/evidence.md` for code verification, solution verification, model validation, uncertainty, and comparisons.

Create no empty documents to satisfy a shape.

## Verification, validation, and uncertainty

- Code verification asks whether the implementation represents the stated mathematics.
- Solution verification estimates numerical error for the solved case through refinement, convergence, residuals, conservation, or comparable evidence.
- Model validation compares the model with physical observations for its intended use.
- Uncertainty analysis traces input, parameter, measurement, model-form, and numerical uncertainty into reported quantities.

Keep these questions distinct. Agreement with an experiment does not prove the code, and convergence does not prove the physical model.

**Calibration is not validation** (AIAA definitions as quoted by Oberkampf and Trucano 2002): fitting parameters to data is calibration; validation compares the model with data it was not fitted to, for a stated use and range. When every data set was fitted, say so.

## Model adoption and comparison

Weigh candidates in this order:

1. Qualitative physics: signs, extrema locations, phase behavior, and limiting behavior.
2. Errors where the model is used, such as the relevant composition, temperature,
   and pressure ranges, against data scatter and literature models.
3. Aggregate metrics.

Run a cheap downstream test that would settle the choice before closing a
candidate. State the recommendation as a physical tradeoff.

Label each reported deviation as **correlation, prediction, or extrapolation**
by its relation to the fit (Kontogeorgis et al. 2021). A predictive claim rests
only on data the model never saw, compared on the same points with the same
statistic. Under **identifiability** (Raue et al. 2009), a fitted parameter is a
result only if the data determine it; report its correlation or a joint region
instead of independent ± values ([sources](scientific-writing.md#sources)).

A fit is **converged for reporting** when further iterations cannot change any
reported parameter by more than a small fraction of its standard error, or any
prediction at its printed precision. An optimizer stopping tolerance is a
setting, not an acceptance criterion; missing it is reported only if the
parameters or predictions are still moving on that scale
([fitness for purpose](numerical-testing.md#fitness-for-purpose)).

## Sources

Prefer primary sources, standards, accepted experiments, analytic solutions, and trusted independent implementations. Identify secondary synthesis as synthesis. Record exact page, section, equation, table, figure, or row locators for claims that drive equations, parameters, data, tolerances, or interpretation.

Search Zotero and Zotero Companion before the web when configured. Do not treat source metadata, a paper, or a Companion note as a validated project conclusion without checking applicability.
