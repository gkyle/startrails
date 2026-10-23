# Building StarTrails AI

## Building the Windows installer

Requirements: Windows x64, Python 3.11 or later for the build scripts, internet access,
and [Inno Setup 6.7.1 or later](https://jrsoftware.org/isdl.php). From the repository:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build/windows/build.ps1
```

Use `-IsccPath 'C:\path\to\ISCC.exe'` for a compiler outside PATH or the default
Inno Setup 6 directory. `-Python .venv/Scripts/python.exe` selects a build interpreter;
it does not change the Python shipped to users. `-StageOnly` prepares the release
without compiling an installer. Build inputs and resources live under `build/windows/`;
generated files live in a fresh directory under ignored `out/windows/`.

The script verifies the pinned uv archive, checks `uv.lock` without updating it, and
stages application files without developer environments, settings, projects, or training
data. It uses `src/startrails/ui/icons/startrails_windows.ico` for the Windows icon.
`toolchain.json` owns the packaged uv and Python versions; the application version
comes from `pyproject.toml`.
Update the uv archive SHA-256 from its upstream release when changing the toolchain.
Keep Qt on a Windows 10 compatible release line; Qt 6.12 is the last supported line.

Each completed build produces:

- `StarTrailsAI-<version>-windows-x64-setup.exe`
- `StarTrailsAI-<version>-models.zip`
- `SHA256SUMS`

Publish these three files together to the GitHub Release tagged `v<version>` before
distributing the installer. The installer downloads that release's model archive and
verifies the hash embedded at build time. `-ModelBaseUrl https://host/path` changes the
archive's hosting directory. Keep published release assets immutable. The staged `app/`
directory, `application.zip`, and generated `build_config.iss` are build intermediates.

The installer targets Windows 10 22H2 and Windows 11 x64, installs for the current user,
and invokes the same `setup.ps1` and GPU probe as repository launches. Packaged setup
uses its bundled uv, a private managed Python and environment, and `uv sync --locked`.
It downloads the selected dependencies; Python and uv need not be preinstalled or
added to PATH. Normal installed launches use the prepared environment without network
access. The default bundled sky model works locally; explicitly choosing an online
model requires downloading it separately.

NVIDIA acceleration requires a compatible NVIDIA driver. The existing CuPy extras
also require the corresponding CUDA Toolkit components; setup does not install GPU
drivers or a system CUDA Toolkit. Shared runtime checks report missing acceleration
prerequisites, and the installer displays their guidance. CPU processing is available
without NVIDIA hardware. Missing native DLLs may require the Microsoft Visual C++ x64
Redistributable; native import errors are retained in the setup log.
Use **Repair StarTrails AI** in the Start menu to rerun setup after driver changes or
to retry dependency installation. During dependency setup, the installer shows an
animated activity bar and live output. The transcript is at `runtime/setup.log` inside
the installed release. The `-Packaged -Repair` switches on the installed `setup.ps1` provide
the same operation from a terminal.

Releases and environments are prepared under `<install>/releases/<release-id>/` at
their final paths. Shortcuts change only after dependency setup succeeds. Previous
releases remain on disk until uninstall, allowing a failed upgrade to leave the old
launch target usable. Uninstall removes these application-owned release directories;
working directories and external projects are preserved. Keep user files outside the
installation directory. Updating a currently running release requires closing it first.

Development installers are unsigned. For signed installers, pass `-SignCommand` with
an Inno Setup signing command; `$f` is the filename placeholder. Supply signing
credentials through your signing tool rather than committing them. This signs setup
and its uninstaller. GitHub Actions can later invoke the same build command.

Before publishing, test clean Windows 10 and 11 systems without Python or uv, CPU and
supported NVIDIA setups, paths containing spaces and Unicode, core processing offline,
interrupted downloads and retry, upgrades, repair, and uninstall while preserving projects.
