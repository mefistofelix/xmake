# AGENTS.md

## Purpose

This repository maintains a minimal patch set on top of the latest commit of the upstream repository's default branch (`xmake-io/xmake`, currently `dev`).

The goal is to keep the patches small, easy to rebase, easy to test, and behaviorally compatible with upstream Xmake except for the explicitly documented features below.

## Repository layout and GitHub setup

- The GitHub repository must be a direct fork of `xmake-io/xmake`, not a separate standalone repository.
- Create the fork on GitHub first, then clone that fork locally as the repository/workspace root.
- The local Xmake source checkout belongs at the repository root. **Never clone or place the Xmake/upstream source tree inside `PATCH/`.**
- Configure the fork as `origin` and `https://github.com/xmake-io/xmake.git` as the `upstream` remote.
- Keep `AGENTS.md` at the root of that Xmake checkout.
- `PATCH/` is only for patch-specific auxiliary files owned by this project: tests, rebundling utilities, fixtures, generated test artifacts, and related local support files.
- Keep `PATCH/.gitignore` there as well.
- Keep one `PATCH/xmake.lua` test project covering all patched behavior.
- Upstream Xmake files retain their normal paths in the root checkout and are edited in place; they are **not** copied under `PATCH/`.
- Modify the fewest upstream files possible.
- Prefer the simplest correct implementation and the least code.
- Do not introduce new subsystems when existing Xmake mechanisms are sufficient.
- Do not use GitHub Actions or repository workflow files in this fork for building, testing, rebundling, packaging, or release automation; perform project validation locally.

## Workflow

For initial setup:

1. Fork `xmake-io/xmake` on GitHub.
2. Clone the fork locally so the clone itself is the repository/workspace root; do not create a nested clone under `PATCH/` or any other subdirectory.
3. Set the fork remote to `origin` and the canonical `xmake-io/xmake` repository to `upstream`.
4. Fetch `upstream`, detect its current default branch from GitHub (currently `dev`), and base patch work on the latest `upstream/<default-branch>`; do not hard-code `main`.

For every change:

Work in **small, independently validated milestones**. Do not accumulate multiple meaningful patch features before validating and publishing the current milestone.

For every meaningful milestone, complete this sequence **before starting the next milestone**:

1. Start from the latest upstream default branch in the root Xmake checkout (currently `upstream/dev`), re-detecting the default branch rather than assuming `main`.
2. Implement only the smallest viable part of the patch directly in the relevant upstream Xmake files.
3. Add or update the corresponding patch-specific tests/support files under `PATCH/`, especially `PATCH/xmake.lua`.
4. Run the relevant local tests against the source-tree implementation first where useful.
5. Download or refresh the latest official Windows x64 bundled Xmake release executable if the current milestone has not yet been rebundled from that release base.
6. Rebundle the current source tree with `PATCH/xmake_rebundle.py`.
7. Run the full patch suite with the newly rebundled `xmake.exe` itself, without `XMAKE_PROGRAM_DIR`.
8. Only after those tests pass, commit the milestone to the fork and push it to `origin`.
9. Do not begin the next meaningful patch milestone until the commit and push for the current one have succeeded.
10. Update the patch registry below whenever behavior, rationale, important decisions, or modified upstream Lua files change.

A source edit without its tests, fresh rebundle, rebundled-executable validation, commit, and push is an **unfinished milestone** and must not be followed by implementation of another meaningful patch feature.

If priorities change and another patch must be implemented before the current unfinished milestone, **do not leave the current work half-applied**. Before switching milestones:

1. Revert every uncommitted upstream-source change belonging to the unfinished milestone back to the exact current `upstream/<default-branch>` state (currently `upstream/dev`).
2. Remove or revert its unfinished `PATCH/` tests, fixtures, generated files, and support code as well; do not keep speculative artifacts from an abandoned attempt.
3. Preserve only already accepted project infrastructure and documentation that are independent of the abandoned patch, such as `AGENTS.md` and `PATCH/xmake_rebundle.py`.
4. Verify with Git that there are no leftover source changes from the abandoned milestone before starting the new patch.
5. Never mix two unfinished patch implementations in the working tree, even temporarily.

### Test discipline

- Regression tests must exercise the **exact public API, lifecycle, dependency ordering, source discovery, toolchain initialization, and jobgraph behavior** described by the patch. Do not weaken or replace a real behavioral test merely to make it easier to run.
- Tests must be self-contained and must not require Visual Studio, MSVC, GCC, Clang, SDKs, package managers, network access, or any other developer tool to be installed on the machine running the suite.
- When a compiler/tool is logically needed by a scenario, provide a patch-local custom rule/toolchain/fake executable or other deterministic fixture under `PATCH/` that drives the real Xmake code path without depending on host-installed toolchains.
- Do not change source extensions, target kinds, or test semantics solely to bypass Xmake toolchain/configuration behavior that the project is supposed to patch.
- If an exact regression test is blocked by eager initialization of an unavailable host toolchain, treat that as evidence that the **lazy toolchain initialization / selected build graph patch must be implemented first**. Do not work around that failure in the test.
- A milestone is complete only when its exact behavioral tests pass with the rebundled executable in a clean environment that does not rely on `XMAKE_PROGRAM_DIR` or host compiler availability.

## Rebundle tool

`PATCH/xmake_rebundle.py` rebuilds the Lua payload inside a Windows Xmake executable without rebuilding the native core.

Before rebundling, download the latest available official Windows x64 bundled Xmake executable from an official `xmake-io/xmake` GitHub Release asset. Do not source the base executable from CI artifacts, workflow runs, third-party mirrors, or a locally rebuilt native core. Treat that freshly downloaded official bundled `xmake.exe` as the rebundle input/base; do not assume a previously cached executable is current.

It must:

- extract/rebundle the embedded XMZ without executing the input Xmake;
- replace the final `.xmz` PE section instead of accumulating sections;
- derive a SHA-256 prefix from the new XMZ and replace the equal-length native cache token;
- ensure different Lua payloads use different `.xmake0/<version>` cache directories;
- support validation entirely through the rebundled executable.

# Patch registry

## 1. Lazy Windows IDL source discovery

**Goal:** IDL support must not force global or premature source-glob expansion during configuration.

Preserve these invariants:

- generated-source globs may become populated during selected-target `on_prepare()` and compile in the same invocation;
- unrelated enabled targets are not scanned or materialized;
- normal IDL generation still runs;
- the IDL autogen include directory is added once, remains `public`, and propagates to dependents;
- project-generator/build-command discovery keeps the same include setup without duplicate mutation.

## 2. No-op build performance

**Goal:** optimize hot paths without changing semantics.

Preserve these invariants:

- `remove_files()` glob patterns are compiled once per source-list resolution, not once per source/pattern pair;
- filtering behavior remains unchanged, including normalized paths and suffix metadata;
- compiler dependency payloads are materialized when `depend.save()` persists them;
- `depend.save()` does not mutate the caller's dependency table;
- new compiler records omit raw `depfiles` after materialization;
- old records containing raw compiler dependency payloads remain readable and are materialized on load;
- non-compiler dependency records and downstream behavior remain unchanged.

## 3. Lazy toolchain initialization and selected build graph

**Goal:** targets/toolchains outside the selected build closure must stay inert.

First real use must follow:

`on_toolchain_prepare -> check -> load -> use`

Preserve these invariants:

- build-driven configuration is limited to the selected target/dependency closure;
- unrelated targets do not run `on_config`, toolchain checks, source discovery, or configfile generation;
- unavailable toolchains on unused targets remain inert;
- `toolconfig()` does not activate unused candidate toolchains;
- concurrent users share one serialized initialization boundary;
- global `on_toolchain_prepare` runs in the project/runtime sandbox and may mutate the descriptor before detection;
- phony targets needing no compiler use the inert `none` fallback;
- standalone `xmake config` keeps normal all-target semantics.

## 4. `before_sources` target hook

**Goal:** selected targets may prepare files before source discovery/materialization.

Preserve these invariants:

- the target's standalone toolchain finishes `on_toolchain_prepare` and `check()` first;
- `before_sources` runs before build-driven source glob resolution/materialization;
- files created there are visible to `add_files()` and its materialization callback in the same invocation;
- `on_config` calls to `target:sourcebatches()` see the materialized list;
- `on_prepare` sees the same materialized sources;
- unrelated targets do not run `before_sources`;
- standalone `xmake config` does not run `before_sources`.

## 5. `add_files()` source materialization

**Goal:** each `add_files()` source candidate may be incrementally transformed into zero, one, or many effective sources using Xmake's existing dependency machinery.

### API contract

`callback(sourcefile, sources, depend)` runs during source discovery.

- `sourcefile`: matched candidate, or the declared path/pattern when nothing matched.
- `sources`: mutable effective source list, initially `{sourcefile}`.
- `depend`: mutable dependinfo, initially containing `sourcefile` in `depend.files`.
- callback return values are ignored.
- file contents are read explicitly by the callback when needed.

`build_callback(target, sourcefile, sourcefiles, depend, opt)` is optional and runs later in the jobgraph for generators that depend on another target.

- discovery alone may change the effective source list;
- mutating `sourcefiles` inside `build_callback` has no source-list effect;
- all direct `add_deps()` targets, including `{links = false}`, finish before the build callback;
- all build callbacks finish before normal `before_build_file[s]` and build-file rules;
- disabling `build.jobgraph` must fail immediately with a clear diagnostic;
- build callbacks are not translated into IDE/project-generator commands.

### Source semantics

The discovery callback may:

- keep, replace, expand, or remove the original source;
- generate or modify files;
- add incremental dependencies;
- run for a declared input that does not yet exist.

Without `build_callback`, only resulting paths that exist enter the target source list.
With `build_callback`, declared resulting paths may be absent during discovery because the build job will materialize them before normal file rules run.

### Dependency semantics

- Dependency tracking is per source candidate, not per `add_files()` declaration.
- Every effective source path is added to `depend.files`.
- Callbacks may append additional concrete dependencies.
- `xmake.lua` is never added implicitly to each materialization dependency record.
- Missing entries in `depend.files` retain normal Xmake semantics and therefore keep the record dirty.
- Discovery results are cached in `dependinfo.result`; unchanged records restore that list without rerunning Lua.
- `build_callback` uses a separate dependfile and runs when concrete inputs change, outputs are missing, or the target is rebuilt.
- Its dependfile is saved only after successful generation.

### Downstream behavior

- Do not touch output mtimes artificially.
- Normal compilation/dependency behavior continues after materialization.
- Effective sources inherit a clone of the original `add_files(..., {...})` file configuration.
- Rule selection uses the effective post-callback path.
- Targets using callbacks refresh built-in language/file rules before source batches are created so transformed extensions resolve normally.
- Targets without callbacks keep the original fast path.

### Implementation scope

Keep this feature limited to:

- `core/project/target.lua`
- `modules/private/action/build/target.lua` (current jobgraph scheduler)

Do not modify `core.project.depend` for this feature; use its existing `load`, `is_changed`, and `save` APIs.
Do not extend the deprecated non-jobgraph engine.
