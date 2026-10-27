#!/bin/bash

set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
payload=$(cd "$script_dir/../../../.payload" && pwd -P)
source "$payload/common.sh"
models_archive=
if (($#)); then
    if [[ $# != 2 || $1 != --models-archive ]]; then
        printf 'Usage: %s [--models-archive path]\n' "$0" >&2
        exit 2
    fi
    models_archive=$2
fi

if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    printf 'StarTrails AI requires an Apple Silicon Mac.\n' >&2
    exit 1
fi
source "$payload/release.conf"
macos_version=$(sw_vers -productVersion)
macos_major=${macos_version%%.*}
macos_minor=${macos_version#*.}
macos_minor=${macos_minor%%.*}
min_major=${macos_min_version%%.*}
min_minor=${macos_min_version#*.}
min_minor=${min_minor%%.*}
if (( macos_major < min_major || (macos_major == min_major && macos_minor < min_minor) )); then
    printf 'StarTrails AI requires macOS %s or newer.\n' "$macos_min_version" >&2
    exit 1
fi

if [[ ! $release_id =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{12}$ ]]; then
    printf 'Invalid release identifier.\n' >&2
    exit 1
fi
support_dir=$(startrails_support_dir)
release_dir="$support_dir/releases/$release_id"
applications_dir="$HOME/Applications"
app="$applications_dir/StarTrails AI.app"
mkdir -p "$support_dir/releases" "$applications_dir"
lock_dir="$support_dir/.install-lock"
if ! mkdir "$lock_dir" 2>/dev/null; then
    printf 'Another installation is running. If it stopped unexpectedly, remove %s and retry.\n' "$lock_dir" >&2
    exit 1
fi
trap 'rmdir "$lock_dir"' EXIT

repair=false
if [[ -d $app && -f $support_dir/current && $(cat "$support_dir/current") == "$release_id" ]]; then
    repair=true
fi
if $repair; then
    printf 'Repairing StarTrails AI %s...\n' "$version"
else
    printf 'Preparing StarTrails AI %s...\n' "$version"
fi
mkdir -p "$release_dir"
ditto "$payload" "$release_dir"
if $repair || [[ ! -f $release_dir/runtime/models.sha256 ||
    $(cat "$release_dir/runtime/models.sha256") != "$models_sha256" ]]; then
    mkdir -p "$release_dir/runtime"
    reused_models=false
    if ! $repair && [[ -z $models_archive && -f $support_dir/current ]]; then
        previous_release_id=$(cat "$support_dir/current")
        previous_release="$support_dir/releases/$previous_release_id"
        if [[ $previous_release_id =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{12}$ &&
            $previous_release_id != "$release_id" &&
            -d $previous_release/models &&
            -f $previous_release/runtime/models.sha256 &&
            $(cat "$previous_release/runtime/models.sha256") == "$models_sha256" ]]; then
            printf 'Reusing models from the installed release...\n'
            rm -rf "$release_dir/models"
            ditto "$previous_release/models" "$release_dir/models"
            printf '%s\n' "$models_sha256" >"$release_dir/runtime/models.sha256"
            reused_models=true
        fi
    fi
    if ! $reused_models; then
        archive="$release_dir/runtime/models.zip.partial"
        if [[ -n $models_archive ]]; then
            cp "$models_archive" "$archive"
        else
            printf 'Downloading models...\n'
            curl --fail --location --retry 3 --output "$archive" "$models_url"
        fi
        actual_hash=$(shasum -a 256 "$archive" | awk '{print $1}')
        if [[ $actual_hash != "$models_sha256" ]]; then
            printf 'Model archive failed SHA-256 verification.\n' >&2
            exit 1
        fi
        rm -f "$release_dir/runtime/models.sha256"
        ditto -x -k "$archive" "$release_dir"
        printf '%s\n' "$models_sha256" >"$release_dir/runtime/models.sha256"
        rm -f "$archive"
    fi
fi

setup_args=(--packaged)
if $repair; then setup_args+=(--repair); fi
/bin/bash "$release_dir/src/setup/setup.sh" "${setup_args[@]}"

new_app="$applications_dir/.StarTrails AI.new.app"
old_app="$applications_dir/.StarTrails AI.old.app"
if [[ ! -e $app && -e $old_app ]]; then mv "$old_app" "$app"; fi
rm -rf "$new_app"
ditto "$payload/StarTrails AI.app" "$new_app"
rm -rf "$old_app"
if [[ -e $app ]]; then mv "$app" "$old_app"; fi
if ! mv "$new_app" "$app"; then
    if [[ -e $old_app ]]; then mv "$old_app" "$app"; fi
    exit 1
fi
printf '%s\n' "$release_id" >"$support_dir/current.tmp"
if ! mv -f "$support_dir/current.tmp" "$support_dir/current"; then
    rm -rf "$app"
    if [[ -e $old_app ]]; then mv "$old_app" "$app"; fi
    exit 1
fi
rm -rf "$old_app"
rm -f "$applications_dir/Repair StarTrails AI.command" "$applications_dir/Uninstall StarTrails AI.command"
for existing_release in "$support_dir/releases/"*; do
    if [[ -d $existing_release && $(basename "$existing_release") != "$release_id" ]]; then
        rm -rf "$existing_release"
    fi
done
if $repair; then
    printf 'Repaired StarTrails AI. Opening the app...\n'
else
    printf 'Installed StarTrails AI. Opening the app...\n'
fi
if ! open "$app"; then
    printf 'Open StarTrails AI from your Applications folder.\n' >&2
fi
