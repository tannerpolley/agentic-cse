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
- metrics, tolerances, and their rationale;
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

## Sources

Prefer primary sources, standards, accepted experiments, analytic solutions, and trusted independent implementations. Identify secondary synthesis as synthesis. Record exact page, section, equation, table, figure, or row locators for claims that drive equations, parameters, data, tolerances, or interpretation.

Search Zotero and Zotero Companion before the web when configured. Do not treat source metadata, a paper, or a Companion note as a validated project conclusion without checking applicability.
