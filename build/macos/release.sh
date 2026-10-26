#!/bin/bash

set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repository_dir=$(cd "$script_dir/../.." && pwd -P)
source "$script_dir/package.sh"

python=python3
models_archive=
identity=${MACOS_SIGNING_IDENTITY:-}
keychain_profile=${MACOS_SIGNING_PROFILE:-}
model_base_url=
uv_archive=
resume_output=
submission_id=
while (($#)); do
    case "$1" in
        --python) python=$2; shift ;;
        --models-archive) models_archive=$2; shift ;;
        --identity) identity=$2; shift ;;
        --keychain-profile) keychain_profile=$2; shift ;;
        --model-base-url) model_base_url=$2; shift ;;
        --uv-archive) uv_archive=$2; shift ;;
        --resume) resume_output=$2; shift ;;
        --submission-id) submission_id=$2; shift ;;
        *) printf 'Unknown release option: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done
if [[ -z $keychain_profile || ( -z $resume_output && -z $identity ) ]]; then
    printf 'Set MACOS_SIGNING_PROFILE and, for a new release, MACOS_SIGNING_IDENTITY; or pass --keychain-profile and --identity.\n' >&2
    printf 'Usage: %s [--identity "Developer ID Application: ..."] [--keychain-profile PROFILE] [--models-archive ZIP] [--python PYTHON] [--model-base-url URL] [--uv-archive TAR.GZ] [--resume DIR [--submission-id UUID]]\n' "$0" >&2
    exit 2
fi
if [[ -z $resume_output && $identity != "Developer ID Application: "* && ! $identity =~ ^[[:xdigit:]]{40}$ ]]; then
    printf 'Use a Developer ID Application identity (or its SHA-1 hash) for macOS releases.\n' >&2
    exit 2
fi
if [[ -z $resume_output && -n $submission_id ]]; then
    printf '%s\n' '--submission-id requires --resume.' >&2
    exit 2
fi
if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    printf 'Build the macOS release on an Apple Silicon Mac.\n' >&2
    exit 1
fi

if [[ -n $resume_output ]]; then
    if [[ ! -f $resume_output/release.json ]]; then
        printf 'No release.json found in %s.\n' "$resume_output" >&2
        exit 2
    fi
    output=$(cd "$resume_output" && pwd -P)
    version=$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$output/release.json")
    dmg="$output/StarTrailsAI-$version-macos-arm64.dmg"
    if [[ ! -f $dmg ]]; then
        printf 'No signed DMG found at %s.\n' "$dmg" >&2
        exit 2
    fi
    if [[ ! -d "$output/dmg/Install StarTrails AI.app" ]]; then
        printf 'This release lacks the signed installer app; build a new release.\n' >&2
        exit 2
    fi
    codesign --verify --strict --verbose=2 "$dmg"
    hdiutil verify "$dmg"
    if [[ -n $submission_id ]]; then
        "$python" -c 'import json,sys; json.dump({"id": sys.argv[1]}, open(sys.argv[2], "w"))' \
            "$submission_id" "$output/notarization-submission.json"
    elif [[ -s $output/notarization-submission.json ]]; then
        submission_id=$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$output/notarization-submission.json")
    else
        printf 'No saved submission ID in %s; pass --submission-id UUID.\n' "$output" >&2
        exit 2
    fi
else
    mkdir -p "$repository_dir/out/macos"
    output=$(mktemp -d "$repository_dir/out/macos/release.XXXXXX")
    build_args=(--python "$python" --output "$output" --stage-only)
    if [[ -n $models_archive ]]; then build_args+=(--models-archive "$models_archive"); fi
    if [[ -n $model_base_url ]]; then build_args+=(--model-base-url "$model_base_url"); fi
    if [[ -n $uv_archive ]]; then build_args+=(--uv-archive "$uv_archive"); fi
    "$script_dir/build.sh" "${build_args[@]}"

    payload="$output/dmg/.payload"
    codesign --force --options runtime --timestamp --sign "$identity" "$payload/tools/uv"
    codesign --force --options runtime --timestamp --sign "$identity" "$payload/StarTrails AI.app"
    codesign --force --options runtime --timestamp --sign "$identity" "$output/dmg/Install StarTrails AI.app"
    codesign --verify --strict --verbose=2 "$payload/tools/uv"
    codesign --verify --strict --verbose=2 "$payload/StarTrails AI.app"
    codesign --verify --strict --verbose=2 "$output/dmg/Install StarTrails AI.app"

    # Signing changes the payload and therefore the installed release identifier.
    "$python" "$script_dir/prepare.py" --finalize-output "$output"
    dmg=$(create_dmg "$output" "$python")
    codesign --force --timestamp --sign "$identity" "$dmg"
    codesign --verify --strict --verbose=2 "$dmg"
    hdiutil verify "$dmg"

    printf 'Submitting %s for notarization...\n' "${dmg##*/}"
    if ! caffeinate -i xcrun notarytool submit "$dmg" --keychain-profile "$keychain_profile" \
        --output-format json >"$output/notarization-submission.json"; then
        printf 'Notarization upload failed. Release files remain in %s.\n' "$output" >&2
        exit 1
    fi
    submission_id=$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$output/notarization-submission.json")
fi

printf 'Waiting for Apple to notarize submission %s...\n' "$submission_id"
if ! caffeinate -i xcrun notarytool wait "$submission_id" --keychain-profile "$keychain_profile" \
    --output-format json >"$output/notarization.json"; then
    printf 'Notarization wait interrupted. Resume with: %s --resume %q --submission-id %q\n' \
        "$0" "$output" "$submission_id" >&2
    exit 1
fi
read -r result_id status <<<"$("$python" -c 'import json,sys; result=json.load(open(sys.argv[1])); print(result["id"], result["status"])' "$output/notarization.json")"
if [[ $result_id != "$submission_id" ]]; then
    printf 'Notarization response ID does not match submission %s.\n' "$submission_id" >&2
    exit 1
fi
if [[ $status != Accepted ]]; then
    xcrun notarytool log "$submission_id" "$output/notarization.log" --keychain-profile "$keychain_profile"
    printf 'Notarization status: %s. See %s/notarization.log.\n' "$status" "$output" >&2
    exit 1
fi
xcrun stapler staple "$dmg"
xcrun stapler validate "$dmg"
codesign --verify --strict --verbose=2 "$dmg"
spctl --assess --type open --context context:primary-signature --verbose "$dmg"
spctl --assess --type execute --verbose "$output/dmg/Install StarTrails AI.app"
append_dmg_checksum "$output" "$dmg"
printf 'Release output: %s\n' "$output"
