# Building StarTrails AI

Build scripts need Python 3.11 or newer and internet access. The app version comes
from `pyproject.toml`; bundled Python and uv versions and uv checksums come from
`build/toolchain.json`. Build the model archive once in `out/models/`; the
platform builders use it by default. Both installers embed its SHA-256 and
download it during setup.
Platform builders verify the pinned uv download and check `uv.lock`.

## Model archive

Run this from the repository on macOS, Windows, or Linux:

```sh
python build/models.py
```

This writes `StarTrailsAI-<version>-models.zip` and `SHA256SUMS` to `out/models/`.
Pass `--output DIR` to use another directory. The command prints the archive's
absolute path for use below. Rebuild the archive when checked-in models change,
and keep published release assets immutable.

## macOS

Build on an Apple Silicon Mac running macOS 14 or newer:

```sh
.venv/bin/python build/models.py
./build/macos/build.sh --python .venv/bin/python
```

Each build gets a new directory under `out/macos/` containing the DMG, a copy of
the model ZIP, and `SHA256SUMS`. Use `--stage-only` to inspect the DMG contents
without creating an image. `--model-base-url https://host/path` changes the
model download location; the default is the GitHub Release tagged `v<version>`.
Both macOS scripts use the versioned archive in `out/models/` by default;
`--models-archive ZIP` selects another copy. Publish the model ZIP at that URL
before distributing the DMG.

The DMG's **Install StarTrails AI.command** installs to `~/Applications/` and
prepares an isolated runtime under `~/Library/Application Support/StarTrails/`.
Running it again repairs the installation and opens the app. Normal launches
use the prepared runtime without network access. To remove the app, move it to
the Trash. Projects under `~/Documents/Startrails/` and the runtime and cache
remain; `STARTRAILS_WORK_DIR` can change the project location. Setup logs are
in the installed release's `runtime/setup.log`.

Development DMGs from `build.sh` are unsigned. For a GitHub Release, import a
Developer ID Application certificate into the build Mac's keychain and save
notarization credentials with `xcrun notarytool store-credentials PROFILE`.
Set `MACOS_SIGNING_IDENTITY` to the exact Developer ID Application identity and
`MACOS_SIGNING_PROFILE` to that Keychain profile. If they are in the ignored
`.env` file, load and export only these two variables, then run:

```sh
source .env
export MACOS_SIGNING_IDENTITY MACOS_SIGNING_PROFILE
.venv/bin/python build/models.py
./build/macos/release.sh --python .venv/bin/python
```

`--identity` and `--keychain-profile` override the environment variables.
`MACOS_SIGNING_TEAM_ID` is only needed when creating the Keychain profile;
the app-specific password should be entered at the `notarytool` prompt, not
stored in `.env`.

`release.sh` stages the payload, signs bundled uv and the app with hardened
runtime and a secure timestamp, recalculates the release ID, signs the DMG,
submits it with `notarytool`, saves the submission ID, waits while preventing idle
sleep, staples and validates the ticket, then writes the final DMG checksum.
If the wait loses its connection, resume the existing submission without
rebuilding or uploading the DMG again:

```sh
./build/macos/release.sh --resume out/macos/release.XXXXXX
```

For a release created before submission IDs were saved, also pass
`--submission-id UUID` using the ID from the `notarytool` error or history.
Keep the Mac awake and connected; closing a laptop lid can still suspend it.
Publish the DMG, model ZIP, and `SHA256SUMS` from the
printed release directory under the `v<version>` GitHub Release. Signing and
notarization credentials stay in the Mac's keychain; the script does not accept
passwords. A downloaded Python runtime and native libraries are installed later
and are outside the DMG's notarization scan. Test a downloaded DMG under
Gatekeeper by double-clicking **Install StarTrails AI.command** in Finder,
including those downloaded components, installation, repair, upgrades,
Finder launch, and Dock identity on a clean Mac.

## Windows

Build on Windows x64 with [Inno Setup 6.7.1 or later](https://jrsoftware.org/isdl.php):

```powershell
python build/models.py
powershell -NoProfile -ExecutionPolicy Bypass -File build/windows/build.ps1
```

Each build gets a new directory under `out/windows/` containing the setup EXE,
a copy of the model ZIP, and `SHA256SUMS`. `-StageOnly` skips Inno compilation;
`-IsccPath` selects a nonstandard `ISCC.exe`; `-Python` selects the build
interpreter. `-ModelsArchive ZIP` selects another archive; the default is the
versioned ZIP in `out/models/`. `-ModelBaseUrl https://host/path` changes the
model download location. Publish the ZIP beside the installer at the embedded
URL before distribution. Staged `app/`, `application.zip`, and `build_config.iss` are build
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
errors may require the Microsoft Visual C++ x64 Redistributable.

For signed installers, use `release.ps1` with a code-signing certificate available to your
signing tool. Set `WINDOWS_SIGN_COMMAND` to an
[Inno signing command](https://jrsoftware.org/ishelp/topic_setup_signtool.htm),
or pass `-SignCommand` to override it. For example, with Windows SDK
[SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
on `PATH` and your certificate in the current user's certificate store:

```powershell
$env:WINDOWS_SIGN_COMMAND = 'signtool.exe sign /sha1 CERTIFICATE_THUMBPRINT /fd SHA256 /tr TIMESTAMP_URL /td SHA256 $f'
python build/models.py
powershell -NoProfile -ExecutionPolicy Bypass -File build/windows/release.ps1
```

Replace `CERTIFICATE_THUMBPRINT` with your certificate's thumbprint and
`TIMESTAMP_URL` with your signing provider's RFC 3161 timestamp URL. Use single
quotes in PowerShell to preserve Inno's `$f` filename placeholder; `$q` can
quote paths containing spaces, such as `$qC:\path to\signtool.exe$q`.
Keep signing credentials in your certificate store or signing provider.

`release.ps1` requires a signing command and forwards `-Python`,
`-ModelsArchive`, `-IsccPath`, and `-ModelBaseUrl` to the existing builder.
Inno signs both the installer and uninstaller. The builder verifies the final
installer's Authenticode signature before writing its checksum; signing or
verification failures stop the release. `build.ps1` still supports unsigned
development builds and optional `-SignCommand` signing.
Publish the setup EXE, model ZIP, and `SHA256SUMS` from the printed output
directory under the `v<version>` GitHub Release. Before publishing, test clean
Windows 10 and 11 installations, CPU and NVIDIA processing, offline launches,
interrupted downloads, upgrades, repair, and uninstall.
