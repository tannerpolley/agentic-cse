#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
validation_python="${CSE_VALIDATION_PYTHON:-$(command -v python3 || true)}"
if [[ "$validation_python" != */* ]]; then
  validation_python="$(command -v "$validation_python" || true)"
fi
if [[ "$validation_python" == */* && ! -x "$validation_python" && -x "$repository_root/$validation_python" ]]; then
  validation_python="$repository_root/$validation_python"
fi

missing=()
if [[ -z "$validation_python" ]]; then
  missing+=("Python >=3.11 executable (set CSE_VALIDATION_PYTHON or prepare .venv)")
else
  if ! python_details="$("$validation_python" -c '
import sys
try:
    import yaml
    import numpy
except ImportError as exc:
    raise SystemExit(f"PyYAML or NumPy is unavailable: {exc}")
if sys.version_info < (3, 11):
    raise SystemExit(f"Python >=3.11 is required (found {sys.version.split()[0]})")
print(f"Python {sys.version.split()[0]} with PyYAML {yaml.__version__} and NumPy {numpy.__version__}")
' 2>&1)"; then
    missing+=("$python_details")
  fi
fi
for command in git bash rg; do
  command -v "$command" >/dev/null 2>&1 || missing+=("$command executable")
done
if (( ${#missing[@]} )); then
  printf 'CSE validation prerequisites unavailable:\n' >&2
  printf '  - %s\n' "${missing[@]}" >&2
  printf 'Prepare .venv with: uv venv .venv --python 3.11 && uv pip install --python .venv/bin/python -r requirements-validation.txt\n' >&2
  printf 'Validation itself does not invoke uv, pip, package installers, or resolvers.\n' >&2
  exit 1
fi

export CSE_VALIDATION_PYTHON="$validation_python"
export PATH="$(dirname "$validation_python"):$PATH"
export PYTHONDONTWRITEBYTECODE=1

"$validation_python" "$repository_root/scripts/package_inventory.py" check cse
"$validation_python" -m unittest discover -s "$repository_root/tests" -p 'test_*.py' -v
"$validation_python" "$repository_root/plugin/scripts/workflow/install_cse_hooks.py" --check

prose_paths=("$repository_root/plugin/.codex-plugin" "$repository_root/plugin/.claude-plugin" "$repository_root/plugin/skills")
for optional in references assets README.md AGENTS.md; do
  [[ ! -e "$repository_root/plugin/$optional" ]] || prose_paths+=("$repository_root/plugin/$optional")
done
"$validation_python" "$repository_root/plugin/scripts/workflow/check_prose.py" "${prose_paths[@]}"

if rg -n '\[TODO|TODO:' --glob '!scripts/validate.sh' "$repository_root/plugin"; then
  printf 'Unresolved placeholder found.\n' >&2
  exit 1
fi

bash -n "$repository_root/scripts/validate.sh" "$repository_root/scripts/sync-live.sh" \
  "$repository_root/plugin/scripts/visualize/cache-latex-manuals.sh" \
  "$repository_root/plugin/scripts/visualize/check-latex-toolchain.sh" \
  "$repository_root/plugin/assets/visualize/project/quarto/render.sh"
printf 'CSE family validation passed.\n'
