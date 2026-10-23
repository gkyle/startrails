#!/bin/bash

set -euo pipefail
bundle_contents=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
source "$bundle_contents/Resources/common.sh"
support_dir=$(startrails_support_dir)

if release_dir=$(startrails_current_release "$support_dir") &&
    [[ -x $release_dir/runtime/venv/bin/python ]]; then
    if /bin/bash "$release_dir/src/setup/setup.sh" --packaged --launch -- "$@"; then
        exit 0
    fi
fi
/usr/bin/osascript -e 'display alert "StarTrails AI could not start" message "Run the StarTrails AI installer again to repair it, then try again." as critical' >/dev/null 2>&1 || true
exit 1
