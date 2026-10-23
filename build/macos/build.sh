#!/bin/bash

set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repository_dir=$(cd "$script_dir/../.." && pwd -P)
python=python3
stage_only=false
model_base_url=
uv_archive_override=
while (($#)); do
    case "$1" in
        --python) python=$2; shift ;;
        --model-base-url) model_base_url=$2; shift ;;
        --uv-archive) uv_archive_override=$2; shift ;;
        --stage-only) stage_only=true ;;
        *) printf 'Unknown build option: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    printf 'Build the macOS installer on an Apple Silicon Mac.\n' >&2
    exit 1
fi

read -r uv_version uv_hash <<<"$("$python" "$script_dir/prepare.py" --toolchain)"
downloads_dir="$repository_dir/out/macos/downloads"
mkdir -p "$downloads_dir"
archive="$downloads_dir/uv-$uv_version-aarch64-apple-darwin.tar.gz"
if [[ -n $uv_archive_override ]]; then
    cp "$uv_archive_override" "$archive"
elif [[ ! -f $archive ]]; then
    curl --fail --location --retry 3 --output "$archive" \
        "https://github.com/astral-sh/uv/releases/download/$uv_version/uv-aarch64-apple-darwin.tar.gz"
fi
actual_hash=$(shasum -a 256 "$archive" | awk '{print $1}')
if [[ $actual_hash != "$uv_hash" ]]; then
    printf 'Bundled uv archive failed SHA-256 verification: %s\n' "$archive" >&2
    exit 1
fi
uv_dir="$downloads_dir/uv-$uv_version"
mkdir -p "$uv_dir"
tar -xzf "$archive" -C "$uv_dir"
uv=$(find "$uv_dir" -type f -name uv -print -quit)
if [[ -z $uv || $("$uv" --version) != "uv $uv_version "* ]]; then
    printf 'Bundled uv does not match the pinned toolchain.\n' >&2
    exit 1
fi
license_dir=$(dirname "$uv")
for license_name in LICENSE-MIT LICENSE-APACHE; do
    if [[ ! -f $license_dir/$license_name ]]; then
        curl --fail --location --retry 3 --output "$license_dir/$license_name" \
            "https://raw.githubusercontent.com/astral-sh/uv/$uv_version/$license_name"
    fi
done
cd "$repository_dir"
UV_CACHE_DIR="$downloads_dir/cache" "$uv" lock --check --offline

output=$(mktemp -d "$repository_dir/out/macos/build.XXXXXX")
prepare_args=(--output "$output" --uv-executable "$uv")
if [[ -n $model_base_url ]]; then prepare_args+=(--model-base-url "$model_base_url"); fi
"$python" "$script_dir/prepare.py" "${prepare_args[@]}"
if ! $stage_only; then
    version=$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$output/release.json")
    dmg="$output/StarTrailsAI-$version-macos-arm64.dmg"
    hdiutil create -ov -srcfolder "$output/dmg" -volname "StarTrails AI $version" -format UDZO "$dmg"
    dmg_hash=$(shasum -a 256 "$dmg" | awk '{print $1}')
    printf '%s  %s\n' "$dmg_hash" "${dmg##*/}" >>"$output/SHA256SUMS"
fi
printf 'Build output: %s\n' "$output"
