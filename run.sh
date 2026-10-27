#!/bin/sh

exec /bin/bash "$(dirname "$0")/src/setup/setup.sh" --launch "$@"
