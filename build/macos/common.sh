#!/bin/bash

startrails_support_dir() {
    printf '%s/Library/Application Support/StarTrails\n' "$HOME"
}

startrails_current_release() {
    local release_id
    release_id=$(cat "$1/current") || return 1
    [[ $release_id =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9a-f]{12}$ ]] || return 1
    printf '%s/releases/%s\n' "$1" "$release_id"
}
