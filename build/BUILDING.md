# Building StarTrails AI

The build scripts need Python 3.11 or newer; release builds normally need
internet access. The app version comes from `pyproject.toml`. Python and uv
versions and the uv archive checksums are pinned in `build/toolchain.json`.
Platform builds check the uv download, `uv.lock`, and the published model archive.
Both installers embed the model archive's SHA-256 and download that archive
during setup.

## Release sequence

Create and push the `v<version>` Git tag from the final release commit before
syncing assets.

Build the shared model ZIP once on macOS, Windows, or Linux:

```sh
python build/models.py
```

The command writes the ZIP and `SHA256SUMS` to `out/models/`. If authenticated
`gh` is available, it asks before syncing. After confirmation, a missing
GitHub Release is published without **Latest** or **Prerelease** status. Its
Git tag must already exist remotely. If `gh` is absent or you decline, the files
remain local for manual upload. Keep the model asset unchanged for a given
version; publish changed models under a new version. Default platform builds
need the model ZIP on the tagged release.

Build and validate both signed installers using the platform steps below. With
`gh` available, each release script asks before uploading its installer and
merging its hash into the release's `SHA256SUMS`. Replacing an existing asset
requires separate confirmation. If the release is already **Latest**, the
script asks before converting it to a prerelease. After verifying the uploads,
manually mark an unlabeled release **Prerelease**. Later mark it **Latest**
when ready to offer the update to installed apps.

By default, both platform builders fetch the model ZIP by tag and verify
GitHub's asset SHA-256. Use `python build/models.py --download` to fetch and
verify it separately. To use a local model archive, pass `--models-archive ZIP`
on macOS or `-ModelsArchive ZIP` on Windows. An installer for distribution must
point to the same verified ZIP at its embedded model URL.

## macOS

Build on an Apple Silicon Mac running macOS 14 or newer with Xcode's Swift
compiler. This command produces an unsigned development DMG under `out/macos/`:

```sh
./build/macos/build.sh --python .venv/bin/python
```

`--stage-only` skips DMG creation; `--models-archive`, `--uv-archive`, and
`--model-base-url` override the corresponding downloads.

For a signed release, import a Developer ID Application certificate and save
notarization credentials with `xcrun notarytool store-credentials PROFILE`.
Export the signing identity and saved profile, then run:

```sh
export MACOS_SIGNING_IDENTITY='Developer ID Application: ...'
export MACOS_SIGNING_PROFILE='PROFILE'
./build/macos/release.sh --python .venv/bin/python
```

`release.sh` signs, notarizes, staples, and validates the DMG before offering
to sync it. If notarization waiting is interrupted, resume the saved output
with `./build/macos/release.sh --python .venv/bin/python --resume DIR`.
Pass `--submission-id UUID` if the submission ID was not saved. Signing
credentials stay in the keychain.

Test a downloaded DMG on a clean Mac: Gatekeeper installation, repair, offline
first launch, upgrades, Finder launch, and Dock identity. Setup logs are in the
installed release's `runtime/setup.log`.

## Windows

Build an unsigned development installer on Windows x64 with
[Inno Setup 6.7.1 or later](https://jrsoftware.org/isdl.php):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build/windows/build.ps1
```

Output is under `out/windows/build-<id>/`. `-StageOnly` skips Inno compilation;
`-Python`, `-IsccPath`, `-ModelsArchive`, and `-ModelBaseUrl` select build inputs.

For a signed release with Azure Artifact Signing, use a **Public Trust**
certificate profile and grant your account the **Artifact Signing Certificate
Profile Signer** role. Install the Azure CLI, Windows SDK SignTool, and
[Artifact Signing Client Tools](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations).
Sign in with `az login`. Add the following to the repository's ignored `.env`:

```dotenv
WINDOWS_SIGNING_ENDPOINT='https://eus.codesigning.azure.net'
WINDOWS_SIGNING_ACCOUNT='<account name>'
WINDOWS_SIGNING_PROFILE='<certificate profile name>'
```

Use your account's regional endpoint; the example is East US. The script
discovers the installed tools. For nonstandard locations, set
`WINDOWS_SIGNTOOL_PATH`, `WINDOWS_SIGNING_DLIB_PATH`, or
`WINDOWS_AZURE_CLI_PATH` in `.env`. Process environment values override
`.env`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build/windows/release.ps1
```

The release script signs the installer and uninstaller, verifies Authenticode,
writes the checksum, then offers to sync the installer. For another provider,
set `WINDOWS_SIGN_COMMAND` in `.env` or the process environment to a complete
[Inno signing command](https://jrsoftware.org/ishelp/topic_setup_signtool.htm)
or pass `-SignCommand`; include Inno's `$f` filename placeholder. Signing
credentials belong with the provider.

Test clean Windows 10 and 11 installs, CPU and NVIDIA processing, offline
launches, repair, upgrades, and uninstall. Setup logs are in the installed
release's `runtime/setup.log`.
