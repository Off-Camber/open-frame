# Resolve the interpreter used by Open Frame scripts.
# Prefer $VIRTUAL_ENV when it is set, otherwise <root>/.venv, otherwise python3.
openframe_python_bin() {
  local root="${1:-}"
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    printf '%s\n' "${VIRTUAL_ENV}/bin/python"
    return 0
  fi
  if [[ -n "${root}" && -x "${root}/.venv/bin/python" ]]; then
    printf '%s\n' "${root}/.venv/bin/python"
    return 0
  fi
  printf '%s\n' "python3"
}
