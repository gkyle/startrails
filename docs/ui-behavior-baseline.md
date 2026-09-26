# UI migration baseline

Recorded against `efb6681` on 2026-09-26, using PySide6 6.8.2 on Windows.
Run the lightweight dispatch contract checks with:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The checks use fake application callbacks, so they do not load models or write the user's project. Real processing and visual checks are recorded separately as implementation proceeds.

## Header and layout

`interface.ui` contains a `toolbar` frame with the app title, progress text/bar, cancel button, current image name, and GPU/resource widgets. Preserve that subtree's layout. The image name is already in the header and should stay there; only Show Deleted Masks moves beside the canvas. Resource refresh runs every 5 seconds.

The old body consists of the canvas and right-side action column. The 160 px footer contains separate horizontal input/output thumbnail strips. Focus on a thumbnail emits `showFile`; progress and brightest-frame lookup also call `showFile`, which updates the canvas/name and emits `focusFile`.

## Settings and readiness

| Condition | Detect | Stack | Export Masks | Export Training | Fill Gaps |
| --- | --- | --- | --- | --- | --- |
| No inputs, no selection | Disabled | Disabled | Disabled | Disabled | Should be disabled |
| Inputs without masks | Enabled | Enabled | Disabled | Disabled | Depends on selected output |
| Manual masks only | Enabled | Enabled | Enabled | Enabled | Depends on selected output |
| Selected stacked output | Depends on inputs | Depends on inputs | Depends on masks | Depends on manual edits | Enabled |
| Selected input or other output | Depends on inputs | Depends on inputs | Depends on masks | Depends on manual edits | Disabled |

Detection defaults: confidence 0.3, merge threshold 0.2, NMS, suggested GPU availability. Stacking defaults: Lighten, Keep without masks/Remove with masks, fade Both at 20%, suggested batch size and GPU availability. The dialog is recreated for every run; the new inline panels deliberately retain settings within a project session.

## Queue contract

- `Ui_AppWindow` owns a `QThreadPool` with one worker. Each operation click creates an `AsyncWorker` and calls `op_queue.start`.
- There is no busy-state submission lock and no automatic pipeline. Two accepted submissions stay separate and execute serially.
- Detection and stack scalar settings are read before creating the worker closure. Input lists passed to the wrapper determine progress totals; the underlying App methods obtain project inputs at execution time.
- Fill Gaps reads `self.currentFile` inside the worker, not when clicked. A selection change while it waits can change its target. Preserve this behavior in this UI migration.
- Cancel calls `app.doInterruptOperation()`, which requests interruption of the active operation. It does not clear pending work from the pool.
- Detection progress can focus an input file; stacking can publish NumPy previews; completion publishes output files. These are existing behaviors, not new step transitions.

## Pre-existing issues encountered in source review

- Dialog initialization indexes input zero; inline controls must guard an empty project.
- `CanvasLabel.setFile(None)` clears pixels but leaves its file reference; clear it during project/selection reset to prevent stale annotation edits.
- Readiness scanning stops on the first manual edit, potentially missing auto masks in a later file. The new model summaries should account for every input.
- Imports save the whole project after each file, creating unnecessary repeated serialization for large lists. Measure and batch one import if necessary.
- Some worker closures directly update UI readiness. Route new model/view updates through GUI-thread signals while retaining operation execution and submission semantics.

## Validation evidence

- Baseline automated checks cover no-input/input/manual-only readiness, late Fill Gaps target resolution, cancellation without queue clearing, and serial execution of two actual `AsyncWorker` instances.
- Full ML processing is not part of these isolated checks. The final validation report must distinguish real image processing, fake dispatch checks, and visual inspection.
