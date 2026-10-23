# Building StarTrails AI

Build scripts need Python 3.11 or newer and internet access. The app version comes
from `pyproject.toml`; bundled Python and uv versions and uv checksums come from
`build/toolchain.json`. Build the model archive once, then pass that ZIP to either
platform builder. Both installers embed its SHA-256 and download it during setup.
Platform builders verify the pinned uv download and check `uv.lock`.

## Model archive

Run this from the repository on macOS, Windows, or Linux:

```sh
python build/models.py --output out/models
```

This writes `StarTrailsAI-<version>-models.zip` and `SHA256SUMS` to `out/models/`.
The command prints the archive's absolute path for use below. Rebuild the archive
when checked-in models change, and keep published release assets immutable.

## macOS

Build on an Apple Silicon Mac running macOS 14 or newer:

```sh
models_archive=$(.venv/bin/python build/models.py --output out/models)
./build/macos/build.sh --python .venv/bin/python --models-archive "$models_archive"
```

Each build gets a new directory under `out/macos/` containing the DMG, a copy of
the model ZIP, and `SHA256SUMS`. Use `--stage-only` to inspect the DMG contents
without creating an image. `--model-base-url https://host/path` changes the
model download location; the default is the GitHub Release tagged `v<version>`.
Publish the model ZIP at that URL before distributing the DMG.

The DMG's **Install StarTrails AI.command** installs to `~/Applications/` and
prepares an isolated runtime under `~/Library/Application Support/StarTrails/`.
Running it again repairs the installation and opens the app. Normal launches
use the prepared runtime without network access. To remove the app, move it to
the Trash. Projects under `~/Documents/Startrails/` and the runtime and cache
remain; `STARTRAILS_WORK_DIR` can change the project location. Setup logs are
in the installed release's `runtime/setup.log`.

Development DMGs are unsigned. Before public distribution, sign and notarize
the installer and executable payload, then test a downloaded DMG under
Gatekeeper, including downloaded Python and native libraries. Test installation,
repair, upgrades, Finder launch, and Dock identity on a clean Mac.

## Windows

Build on Windows x64 with [Inno Setup 6.7.1 or later](https://jrsoftware.org/isdl.php):

```powershell
$modelsArchive = python build/models.py --output out/models
powershell -NoProfile -ExecutionPolicy Bypass -File build/windows/build.ps1 -ModelsArchive $modelsArchive
```

Each build gets a new directory under `out/windows/` containing the setup EXE,
a copy of the model ZIP, and `SHA256SUMS`. `-StageOnly` skips Inno compilation;
`-IsccPath` selects a nonstandard `ISCC.exe`; `-Python` selects the build
interpreter. `-ModelBaseUrl https://host/path` changes the model download
location. Publish the ZIP beside the installer at the embedded URL before
distribution. Staged `app/`, `application.zip`, and `build_config.iss` are build
intermediates.

The installer supports Windows 10 22H2 and Windows 11 x64 and installs for the
current user. It bundles uv and prepares private Python and dependencies, so
users need neither preinstalled. Use **Repair StarTrails AI** in the Start menu
to rerun setup. Normal launches work offline with the bundled sky model;
selecting an online model downloads it separately. Uninstall removes the app
and preserves external projects. Setup logs are in the installed release's
`runtime/setup.log`.

NVIDIA acceleration needs a compatible driver; CuPy also needs matching CUDA
Toolkit components. CPU processing works without NVIDIA hardware. Native DLL
errors may require the Microsoft Visual C++ x64 Redistributable. For signed
installers, pass `-SignCommand` with an Inno signing command (`$f` is its filename
placeholder). Before publishing, test clean Windows 10 and 11 installations,
CPU and NVIDIA processing, offline launches, interrupted downloads, upgrades,
repair, and uninstall.
