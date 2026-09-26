# StarTrails sidebar UI plan

Status: implementation in progress.
Created: 2026-09-26. Branch: `ui_refresh`.
Baseline inspected: StarTrails `efb6681`; Pyquator `70236ae`.

This document is the implementation backlog and progress tracker. Assign an owner before starting a task, update its status and checkboxes as work lands, and add the commit and validation evidence to its tracker row. Suggested statuses: TODO, IN PROGRESS, BLOCKED, DONE. A task is done when its acceptance checks pass, not just when code is written.

## Objective and boundaries

Adopt Pyquator's left sidebar design for StarTrails: project file management above collapsible operation steps, beside the image canvas. Continue authoring layouts in declarative PySide `.ui` files.

Confirmed requirements:

- Replace both input and output Filestrips with file management in the sidebar. Remove the entire footer and the right action column.
- Support 1,000+ files without thumbnails, while identifying files with annotations.
- Preserve the header's app title, progress/cancel controls, and system resource view, including their layout and behavior.
- Provide steps in this order: **1. Detect Streaks**, **2. Stack Images**, **3. Fill Gaps**. Stack Images must work without running Detect Streaks.
- Move the existing detection and stacking dialog settings into the corresponding steps. Fill Gaps currently has no settings dialog.
- Put **Export Masks** and **Export Training** in an **Optional: Export Artifacts** collapsible step at the bottom, outside the three numbered operations.
- Keep the first file-manager version minimal, with single-file actions and no search, filters, or bulk actions.
- Follow the system light/dark theme while adopting Pyquator's layout and styling.
- The existing forced dark appearance and icons need not be retained.
- Preserve task-queue behavior. Operation buttons continue submitting work through the existing queue.
- Implement in manageable commits on the current branch after planning.

Out of scope: changes to image-processing algorithms, project serialization formats, a replacement scheduler, pipeline/run-all automation, filename search, annotation filters, bulk file actions, or modifying Pyquator. Shared cross-repository UI packages can be considered later.

## Decisions and questions

The following choices were confirmed by the user during planning.

| ID | Choice | Decision | Status |
| --- | --- | --- | --- |
| D1 | Export actions | Put Export Training and Export Masks in an **Optional: Export Artifacts** step widget | Confirmed |
| D2 | Large-list tools in the first version | Minimal file manager with single-file actions; defer search, filters, and bulk actions | Confirmed |
| D3 | Sidebar colors | Follow the system palette while adopting Pyquator's spacing, card hierarchy, and accents | Confirmed |

Additional working decisions:

- Keep separate collapsible **Input Files** and **Output Files** sections with count badges. Retain all generated outputs, including gap-fill masks.
- Keep New Project, Open Project, and Add Files in the sidebar's project area. Preserve replace-versus-append behavior when choosing input files.
- Keep **Show Deleted Masks** near the canvas as a view control, since it changes how the current image is displayed.
- Use independent step expansion; users can inspect settings even when an operation cannot run. Disable its Run button and explain the prerequisite rather than locking the entire card.
- Initially expand Input Files and Detect Streaks; keep the other sections collapsible. Do not auto-collapse a user's open settings during progress updates.
- Keep inline settings during the current project session; reset to existing defaults when switching projects. Persisting operation settings across launches is a separate enhancement.
- Preserve header structure and behavior. Removing inherited dark styles may change its palette; do not redesign it or introduce a second progress area.

## Proposed layout

```text
+-----------------------------------------------------------------------+
| Existing title / image name / progress / cancel / resource header       |
+-----------------------------+-----------------------------------------+
| Project                     | Show Deleted Masks                      |
| New / Open                  |                                         |
|                             |                                         |
| v Input Files (count)   [+]  |                                         |
|   Filename      Annotations |                                         |
|   ...scrollable rows...     |              Existing canvas            |
| > Output Files (count)      |                                         |
|                             |                                         |
| Operations                  |                                         |
| v 1 Detect Streaks          |                                         |
|   Settings / Detect Streaks |                                         |
| > 2 Stack Images            |                                         |
| > 3 Fill Gaps               |                                         |
|                             |                                         |
| > Optional: Export Artifacts|                                         |
|   Export Masks / Training   |                                         |
+-----------------------------+-----------------------------------------+
```

The optional export card contains both export buttons when expanded and has no sequential prerequisite of completing Fill Gaps.

Use a horizontal splitter so the sidebar can be resized. Match Pyquator's compact section headers, counts, rounded step cards, numbered badges, subtitles, and chevrons. Start around its 400 px sidebar width, then verify smaller windows and display scaling. Bound the file views' height and give them their own scrolling so thousands of files cannot push operations thousands of rows below the viewport. The sidebar itself scrolls when expanded settings exceed the available height; Optional: Export Artifacts is the last sidebar card, with no application footer.

## Source map and migration details

| Area | Current source | Implication |
| --- | --- | --- |
| Main layout and generated form | [interface.ui](../src/startrails/ui/interface.ui), [ui_interface.py](../src/startrails/ui/ui_interface.py) | Edit the `.ui` source and regenerate Python; preserve the header subtree |
| Controller, readiness, dispatch | [ui_wrap.py](../src/startrails/ui/ui_wrap.py) | Replace widget bindings while retaining operation workers and queue |
| Thumbnail strips | [filestrip.py](../src/startrails/ui/filestrip.py) | Replace per-file widgets and thumbnail loading with model/view rows |
| Signals | [signals.py](../src/startrails/ui/signals.py) | Remove/exclude signals currently carry a `QPushButton`; decouple them from row widgets |
| Detection settings | [ui_dialog_streaks.ui](../src/startrails/ui/ui_dialog_streaks.ui), [dialog_detectStreaks.py](../src/startrails/ui/dialog_detectStreaks.py) | Reuse fields, defaults, device logic, and merge-method mapping |
| Stacking settings | [ui_dialog_stack.ui](../src/startrails/ui/ui_dialog_stack.ui), [dialog_stackImages.py](../src/startrails/ui/dialog_stackImages.py) | Reuse fade, masking, batch-size, and device behavior |
| Domain state and persistence | [file.py](../src/startrails/lib/file.py), [app.py](../src/startrails/app.py), [project.py](../src/startrails/ui/project.py) | Keep File objects and the existing project schema authoritative |
| Canvas and progress | [canvasLabel.py](../src/startrails/ui/canvasLabel.py), [progress.py](../src/startrails/ui/progress.py) | Preserve annotation gestures, brightest-frame navigation, previews, and header updates |
| Pyquator reference | `C:/Users/kyles/Documents/GitHub/pyquator/src/pyquator/gui/sidebar.py` | Reference `CollapsibleCategorySection`, `CollapsibleOutputSection`, `StepHeaderWidget`, `CollapsibleStepCard`, and `SidebarWidget` |

Pyquator's current forms are built in Python, and its category sections create a widget for every file. Port the visual design into declarative forms, with a model/view implementation for StarTrails' scale. Do not copy its sequential step locks or completion counter: detection is optional, and existing annotations do not prove detection completed.

### Declarative forms and controllers

- Keep `interface.ui` as the main shell. Add a reusable `step.ui` shell plus `step_detect_streaks.ui`, `step_stack_images.ui`, `step_fill_gaps.ui`, and `step_export_artifacts.ui` bodies, and a `file_manager.ui` form as needed.
- Define static widgets, labels, layouts, size policies, and tab order in `.ui` files. Python handles expansion, model/delegate behavior, validation, state, and signal connections. Composing generated forms is acceptable; rebuilding their static layouts in Python is not the intended pattern.
- Retain the existing generated-Python approach using the project's pinned PySide6 version. Add one documented generation command/script that updates every form deterministically. Never hand-edit generated form modules.
- Use palette-aware styling. New icons may use Qt standard icons or small bundled resources with accessible text labels.

### File manager

- Use model-backed views, such as `QTreeView` with a `QAbstractItemModel`, for the input/output sections. Paint compact indicators with a delegate; do not use `setIndexWidget`, thumbnail loaders, or a widget per file.
- Store references to existing `InputFile`/`OutputFile` objects. Identify rows by the file object within the loaded project, not basename or visible row number. Duplicate basenames must remain distinct; show full paths in tooltips.
- Show automatic masks, manual masks, and exclusion state separately. Also indicate manual deletions so a file with only deleted detections still appears as reviewed/annotated. Use short labels or symbols with tooltips rather than color alone.
- Counts derive from `streaksMasks`, `streaksManualMasks`, and `streaksManualDeletedMasks`; exclusion derives from `excludeFromStack`. A zero-mask file must not be labeled as successfully processed without evidence.
- Single selection previews the current file. Programmatic focus from operation progress or brightest-frame lookup expands the relevant section and reveals the same file without recursive selection signals.
- Preserve single-file Remove from Project and the input Exclude from Stack toggle. Removal does not delete an image from disk. No multi-selection or bulk actions in this version.
- Preserve source order for stacking and fading. Selection is for preview and single-file actions; it must not restrict detection or stacking to the selected row.
- Apply per-file changes through targeted model notifications. Reset on project replacement, not on every mask edit or progress tick. Keep model/view updates on the GUI thread.
- Handle removing the displayed file and loading a new/empty project by clearing or choosing a valid current file. Refresh Fill Gaps eligibility immediately.

For 1,000+ files, model/view rendering alone is insufficient: `appendInputFile()` currently saves the whole project for every added file, and readiness checks scan inputs on frequent updates. Measure these paths. If needed, batch persistence for one import and maintain incremental annotation summaries, keeping project contents and operation semantics unchanged. Avoid filesystem or image decoding work in row rendering; load pixels only for the actual canvas preview/operation.

### Steps and operation contract

| Step/action | Inline controls | Eligibility and behavior to preserve |
| --- | --- | --- |
| Detect Streaks | Confidence threshold (0.3), merge threshold (0.2), NMS/Greedy NMM (default NMS), Use GPU | Enabled with input files; dispatch existing detection worker |
| Stack Images | Lighten method label; Keep/Remove streaks; fade None/Start/End/Both; fade amount; batch size; Use GPU; memory estimate | Enabled with input files, independently of detection. Default Keep without masks; Remove available/default when masks exist. Fade defaults to Both at 20%; use existing batch/device suggestion |
| Fill Gaps | Selected stacked image name, prerequisite hint, Fill Gaps button | Requires a selected `OutputFile` whose operation is `Stacked`; no new algorithm parameters |
| Export Masks | Button in Optional: Export Artifacts; existing destination chooser | Preserve current mask readiness predicate and export implementation; independent of Fill Gaps |
| Export Training | Button in Optional: Export Artifacts; existing confirmation/destination chooser | Preserve existing manual-edit readiness and dispatch; independent of Fill Gaps |

Always-visible settings must handle an empty project safely: both current dialog controllers index the first input file during setup. Defer device/batch suggestions until an input exists and refresh them when the input project/device choice changes. Do not overwrite a user's edits on each progress update. Validate numeric input before enqueueing; report invalid settings beside the field.

Queue preservation is an explicit review boundary:

- Retain `Ui_AppWindow.op_queue`, `QThreadPool.setMaxThreadCount(1)`, `AsyncWorker`, and existing queue submissions for detect, stack, fill, exports, and brightest-frame lookup.
- Capture scalar detection/stack settings on button activation, as the dialogs currently do. Later field edits must not alter a queued job's settings.
- Preserve existing job ordering, repeated submission behavior, file-list/target resolution timing, previews, result publication, and cancel behavior. In particular, Fill Gaps currently reads `currentFile` inside its worker; changing this to a captured target is a separate behavior change.
- Do not add a busy lock that prevents submissions currently allowed, auto-run subsequent steps, clear pending work, replace cancellation, or move work onto a different executor.
- Use prerequisite/status subtitles supported by actual state. Detailed queued/running/done tracking is deferred unless it can be derived faithfully without changing the queue contract. The existing header remains the progress authority.
- Removing Filestrip-only thumbnail/deferred-widget machinery is allowed after checking all callers. Shared worker/signal infrastructure must remain where operations still use it.

## Assignable tasks and commit sequence

Every task below is a suggested commit-sized unit. T2 and T3 can be developed before integration; T4 is the point where the visible shell changes. Keep each committed state runnable.

| ID | Deliverable / suggested commit | Depends on | Owner | Status | Commit / validation evidence |
| --- | --- | --- | --- | --- | --- |
| T0 | Record source audit and migration plan | — | Codex | DONE | This document; implementation untouched |
| T1 | Record behavior baseline for confirmed design | T0 | Codex | DONE | [Baseline](ui-behavior-baseline.md); four contract checks pass |
| T2 | Add declarative step forms and generation tooling | T1 | Codex | IN PROGRESS | |
| T3 | Add scalable file models, views, and indicators | T1 | Unassigned | TODO | |
| T4 | Integrate left sidebar and remove footer/right column | T2, T3 | Unassigned | TODO | |
| T5 | Wire inline settings to existing operation dispatch | T4 | Unassigned | TODO | |
| T6 | Retire obsolete UI code and complete theme/accessibility pass | T5 | Unassigned | TODO | |
| T7 | Verify workflows, queue parity, and large projects | T6 | Unassigned | TODO | |

### T1 — Baseline and decisions

- [x] Record answers to D1–D3 and update this document's scope and layout.
- [x] Capture current header/layout and control defaults for comparison.
- [x] Record queue behavior with two submitted operations, cancellation, changes to selection while work waits, and progress-driven focus.
- [x] Record no-files, inputs-without-masks, manual-only-masks, and selected-stacked-output readiness states.

Acceptance: a concrete baseline and resolved scope exist before UI integration; any discovered pre-existing defects are recorded separately from intended UI changes.

### T2 — Declarative components

- [ ] Add reusable step shell and operation bodies in `.ui`, with small controllers.
- [ ] Add a repeatable form-generation command and document Designer workflow.
- [ ] Implement accessible expand/collapse controls and independent expansion state.
- [ ] Preserve existing field defaults and guard empty-project initialization.

Acceptance: forms open in Designer, regenerate cleanly, and instantiate without loading images, models, or a GPU; settings remain intact while a step is collapsed.

### T3 — File manager

- [ ] Implement input/output models, bounded views, count headers, and annotation/exclusion indicators.
- [ ] Implement add, preview, remove, include/exclude, and identity-safe focus.
- [ ] Keep file interactions to single-file selection/actions; add no search, filters, or bulk controls.
- [ ] Replace button-dependent remove/exclude bindings with file-based actions; adapt callers together at integration.
- [ ] Measure import/persistence and frequent update costs; address demonstrated large-list bottlenecks within scope.

Acceptance: 1,000 and 5,000 synthetic file records render with no thumbnails or per-row widgets; duplicate basenames, targeted annotation changes, empty lists, and removals behave correctly.

### T4 — Layout integration

- [ ] Add left sidebar/canvas splitter to `interface.ui` and mount the new forms.
- [ ] Move project/file controls into the sidebar, and Show Deleted Masks beside the canvas.
- [ ] Mount operation cards; during this intermediate commit their actions may still open the existing dialogs.
- [ ] Remove input/output footer containers and the right action column; disconnect obsolete Filestrip hookups.
- [ ] Preserve header layout, controls, timer wiring, image name, and canvas interactions.

Acceptance: the application starts and existing actions remain usable with the new layout; there is no footer/right action column, and no header redesign.

### T5 — Inline settings and queue integration

- [ ] Replace dialog execution with validated values from inline controllers.
- [ ] Preserve device suggestions, GPU fallback, fade conversion, and mask availability rules.
- [ ] Update readiness and input/output models on imports, annotations, project changes, and generated outputs.
- [ ] Connect Fill Gaps and both export buttons in Optional: Export Artifacts, preserving each action's readiness rules.
- [ ] Confirm all operation dispatch uses the existing queue and retains settings capture and target resolution behavior.

Acceptance: each operation runs from the new UI with equivalent arguments; stacking works without detection, and settings changes after enqueue do not mutate submitted scalar settings.

### T6 — Cleanup and visual review

- [ ] Remove obsolete dialog/Filestrip modules and resources only after all references are migrated.
- [ ] Remove forced dark rules; apply D3 consistently without changing header structure.
- [ ] Check long filenames, keyboard navigation, focus indication, tooltips, palette contrast, and display scaling.
- [ ] Regenerate all forms and update relevant user/developer documentation.

Acceptance: no stale imports or duplicate signal hookups; every remaining control is reachable at a small window size, and generated files match their `.ui` sources.

### T7 — Validation and completion

- [ ] Run the checks below; record environment, timing measurements, failures, fixes, and commit references.
- [ ] Confirm old project files open without migration and saved annotations/exclusions survive reopening.
- [ ] Review diff against all confirmed boundaries, especially header and queue behavior.
- [ ] Mark implementation tasks DONE only after their acceptance checks pass.

## Validation checklist

Use lightweight Qt checks with fake file records and fake operation callbacks for model/signal/dispatch behavior; do not load ML models for these checks. Add focused regression tests for identity, model updates, settings capture, and queue dispatch where they protect actual behavior. Visual changes need manual review rather than tests that mirror widget construction.

| Area | Required checks |
| --- | --- |
| Forms/startup | All `.ui` files compile with pinned PySide6; generated modules import; empty project starts with no index errors |
| Layout | Header unchanged structurally; footer/right buttons removed; narrow window and 100%/150%/200% scaling remain usable |
| File scale | 1,000 and 5,000 synthetic records; record initial population, scroll/selection response, targeted-update time, and memory; widget count does not grow per file |
| Performance target | On the development machine, target model population under 1 second for 1,000 records and UI interactions under 100 ms, excluding image preview decoding and disk import; record results rather than assuming these targets are met |
| Real import | Add at least 1,000 actual image paths; measure import separately from list rendering and identify project-save/image-I/O costs |
| File correctness | Duplicate names in different folders; annotation add/edit/delete; auto/manual/deleted indicators; exclude/include; displayed-file removal; project replacement |
| Selection | Single-file actions affect exactly the intended file; programmatic focus expands/reveals it; preview selection does not change detection/stacking scope or source order |
| Operation settings | Every migrated field matches baseline defaults and values; invalid values do not enqueue; suggestions tolerate empty projects and CPU-only systems |
| Workflow | Stack without detection; detect then stack; manually annotate then stack; select stacked output then fill; inspect both filled image and generated gap mask; export masks and training artifacts without requiring Fill Gaps |
| Canvas | Zoom/pan, polygon creation/edit/deletion, Show Deleted Masks, and brightest-frame lookup still work |
| Queue parity | Multiple clicks still enqueue in the existing serial queue; compare cancel and pending-job behavior to T1; collapsing/editing steps does not cancel or rewrite queued work |
| Header | Progress text/bar, cancel, GPU/resource timer, and intermediate image previews still update |
| Persistence | Existing projects reopen with input/output lists, annotations, and exclusions intact; new project clears stale selection/readiness |

## Progress log

| Date | Task | Update |
| --- | --- | --- |
| 2026-09-26 | T0 | Inspected both repositories; documented current forms, per-file widget costs, dialog defaults, readiness rules, and queue integration. Asked D1–D3. No application code changed. |
| 2026-09-26 | T1 | User confirmed Optional: Export Artifacts containing both exports, minimal single-file management, and system-aware theme. Updated scope and acceptance checks; runtime baseline remains TODO. |

| 2026-09-26 | T1 | Baseline recorded; four isolated Qt contract tests pass. Image name stays in the existing header. |
