#!/usr/bin/env bash
set -euo pipefail
android_failure() {
  local check_status="$1"
  python - <<'PY'
from pathlib import Path
path=Path('android-gradle.log')
detail='\n'.join(path.read_text(errors='replace').splitlines()[-75:]) if path.exists() else 'Consulte o log da compilação Android.'
print('::error title=Diagnóstico Android::'+detail.replace('%','%25').replace('\r','%0D').replace('\n','%0A'))
PY
  exit "$check_status"
}
trap 'android_failure $?' ERR
gradle -p android --no-daemon "$@" 2>&1 | tee android-gradle.log
