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
- Keep one `PATCH/xmake.lua` test project for the patch-local regression coverage that is intentionally retained. Do not keep separate Python test runners. The Windows IDL patch intentionally has no patch-local regression test.
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
8. After those tests pass, **stop before committing or pushing** and present the milestone to the user for a local review gate. Report exactly which upstream and `PATCH/` files changed, the per-file diff size (added/removed lines, using Git), what each file change does, why each file is necessary, and the total upstream footprint. Call out any file that may still be removable or any logic that may still be simplified.
9. Do **not** commit or push until the user explicitly confirms that the reviewed local diff is acceptable and authorizes commit/push. A passing test suite is not authorization. Silence, a general request to continue working, or approval of the design is not authorization to publish the current diff.
10. Before that approval, stay within the same milestone and freely perform additional local simplification/review cycles requested by the user. After each material simplification, rerun the relevant validation and present the updated file/line footprint again. Do not start a different patch milestone while this one is awaiting approval.
11. Only after explicit user approval, commit the reviewed milestone to the fork and push it to `origin`.
12. Do not begin the next meaningful patch milestone until the approved commit and push for the current one have succeeded.
13. Update the patch registry below whenever behavior, rationale, important decisions, or modified upstream Lua files change.

A source edit without its tests, fresh rebundle, rebundled-executable validation, **user review/approval**, commit, and push is an **unfinished milestone** and must not be followed by implementation of another meaningful patch feature.

### Mandatory pre-commit review gate

This gate applies to every future commit that contains project implementation changes, test changes, or patch documentation tied to a milestone.

- Never run `git commit` or `git push` for a milestone before the user has reviewed the current local diff summary and explicitly authorized publication.
- The review summary must be based on the actual current Git diff, not memory. At minimum report `git diff --stat`/`--numstat`-equivalent information and explain each changed file.
- Separate **upstream Xmake files** from **project-owned `PATCH/`/documentation files** so patch invasiveness is immediately visible.
- For every upstream file, explain the exact upstream function/lifecycle boundary being changed and why that behavior cannot be achieved by reusing an already modified boundary instead.
- Highlight deletions as well as additions: a large negative diff may be desirable when it removes upstream eager behavior, but it still needs an explanation.
- If the user questions the footprint, do not defend the current implementation by default. Re-open the upstream source and look for a smaller existing lifecycle/selection boundary, then iterate locally and show the new footprint.
- Explicit approval is scoped to the exact reviewed state. If code changes materially after approval, present the updated diff again and obtain fresh approval before committing/pushing.

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
- If an exact regression test is blocked by eager initialization of an unavailable host toolchain, treat that as evidence that the **lazy toolchain initialization patch must be implemented first**. Do not work around that failure in the test.
- A milestone is complete only when its exact behavioral tests pass with the rebundled executable in a clean environment that does not rely on `XMAKE_PROGRAM_DIR` or host compiler availability.
- Project callbacks/hooks introduced or exercised by this patch must run in the normal Xmake project/runtime sandbox. The normal `os` sandbox API must be available there, including operations such as `os.mkdir`, `os.run`/`os.runv`/`os.vrunv`, file/path checks, environment access, and the rest of the standard callback `os.*` surface; do not implement a reduced ad-hoc callback environment.
- Do **not** add ad-hoc cache invalidation, timestamp touching, forced rechecks, or private cache resets to make these patches work. Hook into Xmake's existing lazy lifecycle and dependency/cache machinery and let Xmake's normal `depend`, cache, dirtiness, and rebuild semantics decide when work is repeated.

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

**Goal:** the built-in Windows IDL rule must not force global or premature `add_files()` source-glob expansion merely because a target is configured for Windows. This patch is standalone and belongs entirely to the existing `platform.windows.idl` rule; it does not depend on `before_sources`, add-files callbacks, lazy toolchains, selected-target plumbing, or any new core lifecycle.

### Root cause and technical model

`platform.windows` depends on `platform.windows.idl`, so the IDL rule is present on ordinary Windows C/C++ targets even when they declare **no `.idl` files at all**. Upstream `platform.windows.idl` registered an `on_config` callback that called `idl.configure(target)`, and upstream `idl.configure()` called `target:sourcebatches()` only to discover whether an IDL batch existed. `target:sourcebatches()` materializes the target's complete source list, so this IDL-specific config callback accidentally expands every unrelated `add_files()` glob during ordinary Windows configuration.

The canonical regression is therefore deliberately a Windows target with **zero IDL declarations** and an unrelated absent glob such as `add_files("generated/*.c")`. On unpatched Xmake, banal `xmake f -c` reaches the IDL rule's `on_config -> target:sourcebatches()` path and emits the normal `cannot match add_files("generated\\*.c")` warning, proving that the unrelated source glob was materialized. With this patch, the same config must not inspect that glob and must not emit that warning.

### Reconstruction recipe

1. In `xmake/rules/platform/windows/idl/idl.lua::configure(target)`, remove the `target:sourcebatches()["platform.windows.idl"]` probe and its conditional. `configure()` becomes purely declarative: compute `path.join(target:autogendir(), "platform/windows/idl")`, create that directory, and add it to `includedirs` with `{public = true}`. Do not inspect any target source list here.
2. In `xmake/rules/platform/windows/idl/xmake.lua`, remove the IDL `on_config("windows", "mingw", ...)` callback completely. The `.idl` extension already binds this file rule to the correct source batch; do not add manual file-pattern recognition or inspect `target:get("files")`.
3. Reuse the existing IDL file-rule lifecycle. At the beginning of `before_build_files`, call `idl.configure(target)` and then run the existing `idl.generate_idl(...)`. Because this hook already receives the `platform.windows.idl` source batch, configuration occurs only when Xmake is actually processing IDL files.
4. Add the corresponding `before_buildcmd_files` hook that calls `idl.configure(target)`. Project generators consume build-command hooks instead of the jobgraph `before_build_files` hook; this preserves the generated/public include setup for CMake/Visual Studio/Ninja/Make project generation without restoring eager config-time source discovery.
5. Do not change `generate_idl`, `generate_single`, `build_idlfiles`, MIDL invocation, generated C compilation, target/source core, or any global configuration/build action.
6. Do not add source-cache invalidation, force `sourcefiles()`/`sourcebatches()` refreshes, scan raw `add_files()` patterns, or create a new generic lazy-source mechanism for this patch. The fix is specifically to stop the IDL rule from asking for source batches during `on_config` and to use its existing file-specific hooks instead.

The current target scope is built by Xmake with deduplication enabled, so repeated `target:add("includedirs", autogendir, {public = true})` through the build/buildcmd paths does not require the old patch's manual include-directory deduplication loop. Keep the `public` visibility: project generators must expose the IDL autogen directory both to the target and through its interface/dependents.

Preserve these invariants:

- banal Windows `xmake config` does not materialize unrelated `add_files()` globs merely because `platform.windows.idl` is in the rule dependency chain, including targets that contain no IDL declaration at all;
- generated-source IDL globs may become populated during selected-target `on_prepare()` and are then visible to the normal IDL build/generator path in the same invocation;
- normal IDL/MIDL generation and generated C compilation remain unchanged;
- the IDL autogen include directory is added once logically, remains `public`, and propagates to dependents;
- project-generator/build-command discovery keeps the same include setup without reintroducing config-time source materialization.

No patch-local regression test is retained for this IDL patch; do not add IDL coverage to `PATCH/xmake.lua` unless the user explicitly requests it.

Intended upstream footprint: exactly `xmake/rules/platform/windows/idl/idl.lua` and `xmake/rules/platform/windows/idl/xmake.lua`.

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

### Technical model and upstream change points

- `xmake/core/project/target.lua::_instance:sourcefiles()` compiles normalized `remove_files()` patterns once before scanning the resolved source list. Keep whole-pattern anchoring and the existing `|...` suffix stripping semantics unchanged.
- `xmake/modules/core/project/depend.lua` materializes compiler `depfiles` into `files` at save time. Clone the caller table before materialization so `depend.save()` remains non-mutating, and reuse the same materialization helper when loading old raw records.
- `xmake/modules/private/action/build/object.lua` passes `{target = target}` to `depend.save()` because its existing `depend.load()` path already supplies that target context; this preserves GCC C++ module mapping when parsing moves from load time to save time. The SWIG path remains unchanged because its existing load path parses without target context.
- Do not move compiler parsing into compiler implementations, add a new dependency-record format, or change `depend.is_changed()` semantics.

Intended upstream footprint: exactly three files:

- `xmake/core/project/target.lua`;
- `xmake/modules/core/project/depend.lua`;
- `xmake/modules/private/action/build/object.lua`.

### Required regression proof

`PATCH/xmake.lua` contains the retained no-op regression task. `xmake test-noop` must prove `remove_files()` filtering still handles normalized patterns and `add_files()` suffix exclusions, new compiler records are saved with materialized dependency paths but without raw `depfiles`, the caller table is unchanged, old raw compiler records still materialize on load, and ordinary non-compiler records are unchanged. The test must not require a host compiler.

## 3. Lazy toolchain initialization

**Goal:** declaring/configuring a toolchain must not detect it. Detection happens only at the first real use of that runtime toolchain instance.

The required order at first real use is:

`on_toolchain_prepare -> check -> load -> use`

A plain `xmake config` may keep all of upstream Xmake's normal target/configuration traversal. This patch does **not** track selected build roots, target closures, dependency graphs, or build concurrency, and must not modify `xmake/actions/build/main.lua` or `xmake/actions/config/main.lua` merely to decide which target might later use a toolchain. Laziness belongs to the toolchain object itself.

### Technical model and upstream change points

- `xmake/core/platform/platform.lua`, especially `_instance:check()`, is descriptive only. It may load toolchain descriptors and preserve the existing ordered candidate names/fullnames, including explicit standalone-toolchain priority, but it must not call `toolchain:check()`, probe tools/SDKs, discard unavailable candidates, or fail merely because a candidate is not installed.
- `xmake/modules/private/utils/target.lua::check_target_toolchains()` is the other eager global boundary. It may validate/load declared toolchain descriptors, but it must not call `toolchain:check()` merely because a target declares a toolchain.
- `xmake/core/tool/toolchain.lua::check()` remains a real Xmake check in every task. The patch only inserts `on_toolchain_prepare` immediately before the first normal check for that runtime instance; it does not special-case `config`.
- `_load()` must enter the normal `check()` boundary before `on_load()`. This replaces the old assumption that configuration had already checked every toolchain eagerly. `tool()`, `toolconfig()`, rules, options, packages and other callers otherwise retain upstream semantics.
- Therefore a rule/option that explicitly asks for a tool, dynamic toolchain configuration, or `toolchain:check()` during `xmake config` is a genuine use and may legitimately trigger prepare/detection. A plain config that only loads descriptors and runs ordinary target configuration must not trigger it.
- `on_toolchain_prepare` runs in the normal project/runtime sandbox immediately before the first real detection attempt for that runtime instance. It may create directories, download/materialize an SDK or executable, run programs, modify environment inputs, or mutate the toolchain descriptor so the normal checker sees the prepared state.
- Do not add cache invalidation, forced rechecks, timestamps, target-selection state, dependency-graph state, synthetic fallback toolchains, or a new concurrency subsystem. Existing Xmake `__checked`, `__loaded`, `__loading`, localcache/memcache, depend and dirtiness semantics remain authoritative.

Preserve these invariants:

- a banal `xmake config` that does not actually request a toolchain check/load must not run `on_toolchain_prepare`;
- configuration is allowed to visit unrelated targets exactly as upstream does; descriptor visitation alone must not activate their toolchains;
- an unavailable toolchain on a target that is never really used remains inert even if its descriptor is visited;
- any genuine `toolchain:check()` remains a real check and runs `on_toolchain_prepare` first, including when a rule/option legitimately requests it during configuration;
- any `_load()` path enters `check()` before `on_load()`, so actual tool/toolconfig use cannot bypass prepare/detection;
- no special `config` no-op semantics, target-selection plumbing, ad-hoc invalidation, scheduler/locking logic, synthetic `none`, or cached-tool workaround is introduced by this patch.

The intended upstream footprint for this milestone is exactly four files:

- `xmake/core/platform/platform.lua` - remove eager platform detection and retain ordered candidate metadata only;
- `xmake/modules/private/utils/target.lua` - remove eager per-target `toolchain:check()` while retaining descriptor validation;
- `xmake/core/project/project.lua` - register the global `on_toolchain_prepare` project script API;
- `xmake/core/tool/toolchain.lua` - run prepare at the normal check boundary and make load enter that boundary before `on_load()`.

### Reconstruction recipe

This section is intentionally detailed enough to recreate the patch against a fresh upstream tree without copying the current modified files verbatim.

1. In `xmake/core/platform/platform.lua`, change `_instance:check()` from an eager availability probe into candidate registration only. Remove its scheduler lock/import and the loop that calls `toolchain:check()`, filters unavailable candidates, and collapses standalone candidates. Instead iterate `self:toolchains({all = true})` in its existing order, collect each instance `fullname()`, store that list with `config.set(self:_toolchains_key(), names)`, and return `true`. This preserves platform/explicit-toolchain ordering but records no machine-dependent availability decision.
2. In `xmake/modules/private/utils/target.lua::check_target_toolchains()`, keep the existing project/target traversal and keep `target:platform():check()` because target/platform metadata still has to be resolved. For targets with explicit `set_toolchains()`, call `target:toolchains()` only to load/validate their descriptors. Remove the loop that invokes `toolchain_inst:check()` and raises `toolchain(...): not found!` during this global configuration pass. Descriptor-not-found errors still happen when the descriptor itself cannot be loaded; machine availability is deferred.
3. In `xmake/core/project/project.lua::project.apis()`, register root project script API `on_toolchain_prepare`. It is a project-level callback, not a target/rule callback, because it prepares a runtime toolchain instance independently of which consumer first needs it.
4. In `xmake/core/tool/toolchain.lua::_instance:check()`, keep the existing `__checked` cache and normal `_on_check()` implementation. Immediately before reading/running the normal check, run the project `toolchain_prepare` script once per runtime instance, guarded by an in-memory `__prepared` field on `self:info()`. Invoke it through `sandbox.call(on_prepare, self)` and propagate errors normally. Do not clear or rewrite `__checked`; preparation must occur before the first ordinary detector observes the filesystem/environment.
5. In `xmake/core/tool/toolchain.lua::_instance:_load()`, replace the old warning-only assumption that configuration has already checked the toolchain with `if not self:check() then return end`, then leave the existing `__loaded`/`__loading` and `on_load` logic intact. This is what makes every genuine load path enter the same prepare/check boundary.
6. In `xmake/core/tool/toolchain.lua::_instance:tool()`, remove the obsolete warning/comment claiming an unchecked toolchain cannot be checked there. Keep the normal `_load()` call; `_load()` now performs the check correctly. Do not add new logic to `tool()`, `toolconfig()`, compiler/linker, rules, options, packages, action mains, or target selection.

The rationale is that **`check()` is the semantic availability boundary already used throughout Xmake**. It is called not only by final compiler execution but also legitimately by package tools, SDK detection, generators, rules and options. Therefore `check()` must remain real in every task, including `config`. What must disappear is only speculative/global checking performed before any consumer actually asks for availability. Likewise `on_load()` may populate `toolset`, flags, include/link directories, run environments and callbacks, so it must retain normal upstream semantics rather than being globally suppressed during configuration.

Do not recreate any earlier discarded design: no selected-build closure, `__build_selected`, edits to `actions/build/main.lua` or `actions/config/main.lua`, task-name-based `config` no-ops, `{load = false}` changes to generic `toolconfig()`, synthetic `none` toolchains, scheduler locks, cache invalidation, or special cached-tool lifecycle workaround. Those approaches were investigated and removed because they either duplicated Xmake lifecycle state or changed legitimate Xmake configuration semantics.

### Required regression proof

`PATCH/xmake.lua` is the executable specification. Keep the two custom standalone descriptors directly in that file: `good`, whose `on_check` requires the prepare marker/state and whose `on_load` exposes a fake `cc` using `os.programfile()`, and `bad`, whose `on_check`/`on_load` unconditionally fail. The global prepare callback must exercise the normal sandbox (`os.mkdir`, `os.vrunv`, file writing) and mark which toolchain was prepared.

The minimum regression sequence is:

- clean patch markers/cache, run a banal `xmake f -c --toolchain=good`; normal target `on_config` callbacks may run and both `good`/`bad` descriptors may be visited, but neither `prepare-good` nor `prepare-bad` may appear;
- without relying on a host compiler, run `xmake build app`; first `target:tool("cc")` must cause `good` to execute `prepare -> on_check -> on_load -> tool`, while `bad` remains untouched;
- the test must fail immediately if `bad` is eagerly checked/loaded or if `good` reaches `on_check` before prepare.

This proves the intended distinction: **descriptor/configuration traversal is inert; an actual call into Xmake's normal toolchain availability/load path is real use and may trigger preparation, even if that legitimate use happens during a configuration task.**

Do not reintroduce selected-target plumbing in action/config files for this feature. If future patches need build-selection information (for example `before_sources`), solve that separately at the lifecycle point where that feature is actually invoked.

## 4. `before_sources` target hook

**Goal:** intercept the target's source-list boundary immediately before its first `add_files()` discovery/materialization.

Keep this hook deliberately local to `target:sourcefiles()`; do not add build-selection, scheduler, dependency-closure, action, or toolchain plumbing for it.

Preserve these invariants:

- `target.before_sources` is a target script hook stored as `sources_before`;
- a target with no `add_files()` list does not run the hook;
- for a target with `add_files()`, the hook runs at most once per target instance, immediately before the first glob/file matching performed by `target:sourcefiles()`;
- files/directories generated by the hook are visible to that same first source-list materialization;
- later `target:sourcefiles()` / `target:sourcebatches()` calls reuse the normal cached source list and do not rerun the hook;
- the hook runs in the normal Xmake sandbox and therefore has the ordinary `os.*`, `io.*`, path, environment, and imported-module APIs;
- the hook follows the first real caller of `target:sourcefiles()`: if configuration or another lifecycle phase is the first code that materializes the source list, the hook runs there; there is no separate build-only gate;
- no toolchain check is forced by this hook; toolchain lifecycle remains owned by the existing lazy-toolchain patch and by callers that actually request tools.

Intended upstream footprint: exactly `xmake/core/project/target.lua`.

## 5. `add_files()` source materialization

**Goal:** each `add_files()` source candidate may be incrementally transformed into zero, one, or many effective sources using Xmake's existing dependency machinery.

### API contract

`source(sourcefile, sourcefiles, depend)` runs lazily when that `add_files()` candidate is first resolved by normal source discovery.

`build(sourcefile, sourcefiles, depend)` is optional and is the later phase of the same deterministic transformation. It runs in the jobgraph only so it can wait for target dependencies.

For both callbacks:

- `sourcefile`: matched candidate, or the declared path/pattern when nothing matched;
- `sourcefiles`: mutable effective source list, initially `{sourcefile}`;
- `depend`: the same mutable dependinfo shared by both phases, initially containing `sourcefile` in `depend.files`;
- return values are ignored;
- both callbacks run in the normal Xmake sandbox and have the ordinary `os.*`/`io.*` surface, including `os.runv` and `os.vrunv`;
- file contents are read explicitly by the callback when needed.

`source` may keep, replace, expand, or remove the original source, generate or modify files, and append concrete incremental dependencies. `build` may also mutate the passed tables, but because it runs after source batches/jobs have been constructed, changing `sourcefiles` there does not rewrite the current invocation's already-scheduled source jobs. It may freely extend `depend` for deterministic inputs/outputs.

Without `build`, only resulting paths that exist enter the target source list. With `build`, resulting paths may be absent during discovery because the later job is responsible for materializing them.

### Dependency semantics

- Dependency tracking is per source candidate, not per `add_files()` declaration.
- There is exactly one dependfile and one `depend.is_changed()` decision per candidate for the whole `source -> build` transformation.
- If the candidate is dirty, every callback present for it runs in order: `source` first, then `build` later if configured.
- If the candidate is clean, neither callback runs and `dependinfo.result` restores the effective source list.
- Every effective source path is added to `depend.files`; callbacks may append additional concrete dependencies/outputs.
- The callback's Lua file is not added implicitly to `depend.files`.
- Missing entries in `depend.files` retain normal Xmake semantics and therefore make the transformation dirty.
- Do not manually invalidate caches or touch mtimes; express deterministic inputs/results through normal dependency metadata.
- With only `source`, save the dependfile after successful source materialization.
- With `build`, do not save after `source`; save the single dependfile only after `build` completes successfully. If either phase fails, the record remains dirty and both phases rerun next time.

### Jobgraph/downstream behavior

- `build` is delayed only for ordering; it does not perform a second dirtiness check.
- All direct `add_deps()` targets, including `{links = false}`, finish before `build`.
- All `build` callbacks finish before normal `before_build_file[s]` and build-file rules.
- Disabling `build.jobgraph` must fail immediately with a clear diagnostic when `build` is used.
- `build` callbacks are not translated into IDE/project-generator commands.
- Normal compilation/dependency behavior continues after materialization.
- Effective sources inherit a clone of the original `add_files(..., {...})` file configuration.
- Rule selection uses the effective post-`source` path.
- Targets using `source`/`build` refresh built-in language/file rules before source batches are created so transformed extensions resolve normally.
- Targets without either callback keep the original fast path.

### Implementation scope

Keep this feature limited to:

- `core/project/target.lua`
- `modules/private/action/build/target.lua` (current jobgraph scheduler)

Do not modify `core.project.depend` for this feature; use its existing `load`, `is_changed`, and `save` APIs.
Do not extend the deprecated non-jobgraph engine.
