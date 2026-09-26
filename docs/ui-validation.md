# Sidebar migration validation

Completed 2026-09-26 on Windows with Python 3.12 and PySide6 6.8.2.

## Results

All **24 isolated UI checks pass**. All eight declarative forms load through `QUiLoader`, and regenerating their Python modules produces identical content.

The tests cover:

- Empty projects, inline defaults, CPU device fallback, numeric validation, and settings retention when collapsed or refreshed.
- Stacking before detection, per-submission scalar settings, repeated queue submissions, serial workers, cancellation without clearing pending jobs, and existing late Fill Gaps target resolution.
- Duplicate basenames, metadata updates without model resets, output insertion, single-file removal/exclusion, programmatic focus, keyboard selection, and step expansion.
- Automatic/manual/deleted-mask indicators, completion refresh for files omitted from detection previews, and GUI-thread model updates.
- Canvas polygon creation/editing/deletion, counts after multiple manual additions, zoom/pan/reset, brightest-frame dispatch and returned-file selection, NumPy previews, and Show Deleted Masks.
- Project reset clearing stale canvas/selection state and disabling Fill Gaps.
- Exact preservation of the header's canonical XML subtree, including every widget, layout, and property.

## Real operation smoke test

`tools/smoke_workflow.py --ml` exercised the actual main window, `AsyncWorker` queue, App methods, local model files, and image processing in a temporary project with two 512×512 TIFF inputs. Only destination/confirmation dialogs were answered programmatically. The user's project and app settings were not used.

| Operation | Result | Example elapsed time |
| --- | --- | --- |
| Stack without detection | Output pixels equal the expected maximum of the inputs | 0.049 s |
| Detect Streaks | Local CPU/OpenVINO inference replaces mask arrays, including valid zero-detection results | 4.786 s; first run including initial setup was 12.833 s |
| Stack after detection | Output published and selected through the UI | 0.046 s |
| Fill Gaps | Local model produces both filled image and gap mask; both appear as outputs | 1.445 s |
| Stack with manual masks | Output pixels match the expected masked stack | 0.040 s |
| Export Masks | Two images written; masked pixels verified | 0.011 s |
| Export Training | Training labels and artifacts written | 0.031 s |
| Reopen project | Input/output lists, manual mask arrays, and exclusion state restored | Passed |

These small-image timings demonstrate working integration; they are not processing-speed benchmarks for full-resolution astrophotography.

## File scale and persistence

| Dataset / check | Result |
| --- | --- |
| 1,000 synthetic file records | Population 36 ms; focus plus metadata update 9 ms; 19 child widgets |
| 5,000 synthetic file records | Population 135 ms; focus plus metadata update 8 ms; 19 child widgets |
| Traced Python allocation peak during population/update | Approximately 171 KiB at 1,000 rows and 739 KiB at 5,000 rows; excludes pre-created file records, Qt native memory, and canvas pixels |
| Thumbnail work | No thumbnail decoder, loader, or per-file widget exists in the new manager |
| Import of 1,000 actual tiny image files | Previous per-file persistence: 23.018 s and 1,001 saves; new import: 0.045 s and one save |
| Import correctness | Append keeps existing objects/annotations; replace clears inputs; sorting, save/reload, annotations, and exclusions verified |

Population timings above include Python allocation tracing, layout, and event processing. Without tracing, observed 5,000-row population was approximately 33–46 ms. The file-count requirement is met without loading image pixels for list rows.

## Visual review and boundaries

Reviewed real-window captures with sample data in light and simulated dark Qt palettes, at 100%, 150%, and 200% display scale. Checked a 1280×900 window and smaller 1000×700 / 850×650 windows, including expanded controls and the bottom export card. File views remain bounded and scroll independently; all steps remain reachable through sidebar scrolling. The header layout is unchanged.

Offscreen Windows Qt does not provide an OS font/theme service, so the preview harness registers local system fonts and supplies a dark palette for that capture. The production app retains Qt's system palette. Live OS theme switching and CUDA-specific behavior were not separately validated.

No changes were made to `src/startrails/op/`, the project/file serialization schema, `progress.py`, or `src/main.py`. `AsyncWorker`, the single-worker operation pool, cancellation, and underlying operation argument/file-resolution semantics remain intact. The only App change batches persistence for an input import. The removed background pool was used solely for Filestrip widget/thumbnail work.

Existing OpenVINO and canvas mouse-coordinate deprecation warnings appeared during checks; they did not cause failures. Existing output naming and pending-job selection semantics remain as documented in the [baseline](ui-behavior-baseline.md).

## Implementation commits

| Commit | Work |
| --- | --- |
| `0917f29` | Behavior baseline and queue contract checks |
| `f82a546` | Declarative step forms, controllers, and generation tooling |
| `ab18571` | Scalable file manager and annotation model |
| `021fbf1` | One project save per file import |
| `5ba9482` | Sidebar integration and inline operation dispatch |
| `a3c9df9` | Metadata refresh for detection results omitted from previews |
| `c55fb8b` | Legacy UI removal, theme/accessibility review, and smoke harness |

The final validation commit adds this report and the remaining regression coverage. Commands are documented in [UI development](ui-development.md); task completion is tracked in the [plan](ui-unification-plan.md).
