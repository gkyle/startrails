#!/bin/bash

create_dmg() {
    local output=$1
    local python=$2
    local version dmg
    version=$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$output/release.json")
    dmg="$output/StarTrailsAI-$version-macos-arm64.dmg"
    hdiutil create -ov -srcfolder "$output/dmg" -volname "StarTrails AI $version" -format UDZO "$dmg" >&2
    printf '%s\n' "$dmg"
}

append_dmg_checksum() {
    local output=$1
    local dmg=$2
    local dmg_hash
    dmg_hash=$(shasum -a 256 "$dmg" | awk '{print $1}')
    printf '%s  %s\n' "$dmg_hash" "${dmg##*/}" >>"$output/SHA256SUMS"
}
