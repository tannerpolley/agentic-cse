# Disabled companion analysis notebook

Issue #51 retired the companion notebook, Quarto analysis site, and Summarize
stage so that review and manuscript promotion use retained analysis results
directly. This archive sits outside the installed plugin.

The paths below this directory mirror their former locations in `cse-plugin/`.
The lightweight tag `archive/analysis-notebook` preserves the complete pre-change
source, including the original shared scripts, routing, templates, and tests.

To restore the feature, move the archived files back to their original paths.
Use the tagged version to restore the notebook-specific parts of the shared
scripts, example pipelines, checks, and guidance. Re-add Summarize to the
skill inventory and routing, restore the notebook handoffs and Setup's site
route, and run `scripts/validate.sh` and the rendering integration tests.
