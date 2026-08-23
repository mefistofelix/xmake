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
- Project callbacks/hooks introduced or exercised by this patch must run in the normal Xmake project/runtime sandbox. The normal `os` sandbox API must be available there, including operations such as `os.mkdir`, `os.run`/`os.runv`, file/path checks, environment access, and the rest of the standard callback `os.*` surface; do not implement a reduced ad-hoc callback environment.
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

During an actual build, first real toolchain use must follow lazily:

`on_toolchain_prepare -> check -> load -> use`

`on_toolchain_prepare` is build-driven: merely loading the project or running standalone `xmake config` must not execute it.

### Technical model and upstream change points

Keep this patch architectural rather than procedural: Xmake's configuration/platform layer describes *which* toolchains are candidates, while the existing toolchain use path decides *when* a candidate must actually be detected and loaded.

- `xmake/core/platform/platform.lua`, especially `_instance:check()` and `_instance:toolchains()`, is the platform/candidate-selection boundary. Platform configuration may resolve the platform name, explicit toolchain name, and ordered platform toolchain candidate names/fullnames, and persist that priority list in the existing platform toolchain config key. It must **not** call `toolchain:check()`, probe executables/SDKs, reject an unavailable candidate, or otherwise perform detection. Loading a toolchain descriptor to know its declared kind/name is acceptable; detecting whether the toolchain exists on the machine is not.
- `xmake/core/tool/toolchain.lua` is the first-real-use boundary. The smallest shared path that already feeds actual tool use/load must perform the build-only sequence `on_toolchain_prepare -> check -> load -> use`. Put the lazy boundary here rather than duplicating it in targets, options, platforms, rules, or actions. `on_toolchain_prepare` runs immediately before the normal Xmake detection/check for that runtime toolchain instance, so it may materialize SDK layouts, executables, directories, environment inputs, or descriptor changes that the normal checker then observes.
- Existing Xmake `check()`, `load()`, localcache/memcache, depend files, and dirty/rebuild semantics remain authoritative. The patch should route execution into those mechanisms at the correct time, not replace them and not clear/rewrite their caches manually.
- `xmake/core/project/target.lua` should contain only target-specific policy that cannot live in the generic toolchain layer. In particular, a phony target with no toolset/compiler need may select the inert `none` toolchain; ordinary targets should otherwise expose candidate toolchains and let the generic first-use path choose/detect them lazily.
- `xmake/actions/config/main.lua` must not perform target/platform toolchain detection. Configuration may preserve candidate metadata and normal project configuration behavior, but a plain `xmake config` is not a build and therefore must not run `on_toolchain_prepare` or detect host compilers merely because a target/toolchain is declared.
- Build target selection remains separate from toolchain detection. A build may restrict configuration work to its selected target/dependency closure so unrelated target callbacks/configfiles/source discovery remain inert, but this must reuse existing Xmake selection/`is_enabled()`/dependency traversal mechanisms with the least plumbing possible; do not pass new target lists through multiple project/config layers when an existing selection boundary can express the same thing.
- The implementation must remain small and concentrated. Prefer changing the existing platform candidate-selection function and the existing generic toolchain first-use function over adding parallel lifecycle subsystems or broad option propagation.

Preserve these invariants:

- build-driven configuration is limited to the selected target/dependency closure;
- unrelated targets do not run `on_config`, toolchain checks, source discovery, or configfile generation;
- unavailable toolchains on unused targets remain inert;
- `toolconfig()` does not activate unused candidate toolchains;
- concurrent users share one serialized initialization boundary;
- global `on_toolchain_prepare` runs only for a toolchain actually reached by an active build, in the normal project/runtime sandbox, and may materialize files/tools or mutate the descriptor before Xmake's normal toolchain check/use path;
- toolchain preparation does not manually clear `__checked`, detection caches, or other Xmake cache state; normal Xmake cache semantics remain authoritative;
- phony targets needing no compiler use the inert `none` fallback;
- standalone `xmake config` keeps normal all-target semantics and does not run build-only `on_toolchain_prepare` hooks.

Keep the final upstream footprint synchronized with the implementation. The intended core change points are `xmake/core/platform/platform.lua`, `xmake/core/tool/toolchain.lua`, and only the minimum target/config/build files strictly required for phony `none` fallback and selected-build scoping. If an implementation starts modifying helper layers merely to transport state between those points, first look for an existing Xmake selection or lifecycle mechanism that removes those edits.

Current upstream files for this milestone are intentionally limited to:

- `xmake/actions/build/main.lua` - tells the nested config which build roots/group are active;
- `xmake/actions/config/main.lua` - marks only that root/dependency closure for the duration of build-driven config and performs no toolchain detection;
- `xmake/core/platform/platform.lua` - stores only ordered candidate toolchain names in the existing platform config key;
- `xmake/core/project/project.lua` - exposes the global `on_toolchain_prepare` project API;
- `xmake/core/project/target.lua` - reuses `is_enabled()` for temporary selected-build filtering, keeps platform standalone candidates lazy, and maps tool-less phony targets to `none`;
- `xmake/core/tool/toolchain.lua` - owns the single serialized first-use `prepare -> check -> load` boundary and avoids activating candidates from `toolconfig()`;
- `xmake/toolchains/none/xmake.lua` - minimal inert standalone phony fallback.

Do not reintroduce edits to `actions/config/configfiles.lua`, the sandbox project loader, or `modules/private/utils/target.lua` merely to carry selected target lists: their existing `target:is_enabled()` filtering is sufficient.

## 4. `before_sources` target hook

**Goal:** selected targets may prepare files before source discovery/materialization.

For a target actually reached by an active build, the intended lazy order is:

`on_toolchain_prepare -> toolchain check -> before_sources -> add_files() discovery/materialization -> dependency targets build -> add_files() build_callback -> normal before_build_file[s]/rule build`

Each stage may materialize files, directories, executables, downloaded sources, or other artifacts needed by the following stage. Later stages must observe artifacts created by earlier stages in the same build invocation.

Preserve these invariants:

- `before_sources` is build-driven and lazy: merely loading/configuring a target does not run it;
- it is triggered only when the active build is actually about to resolve that target's `add_files()` source list;
- the target's standalone toolchain finishes build-only `on_toolchain_prepare` and `check()` first, so `before_sources` can use files/tools materialized by toolchain preparation;
- `before_sources` may itself materialize/download/generate source inputs for that target;
- `before_sources` runs immediately before that build-driven source glob resolution/materialization;
- files created there are visible to `add_files()` and its materialization callback in the same invocation;
- `on_config` calls to `target:sourcebatches()` see the materialized list;
- `on_prepare` sees the same materialized sources;
- unrelated targets do not run `before_sources`;
- standalone `xmake config` does not run `before_sources` even if it inspects/configures the target;
- targets whose source list is never needed by the active build do not run `before_sources`.

## 5. `add_files()` source materialization

**Goal:** each `add_files()` source candidate may be incrementally transformed into zero, one, or many effective sources using Xmake's existing dependency machinery.

### API contract

`callback(sourcefile, sources, depend)` runs lazily during source discovery, only when that target's `add_files()` list is actually being resolved for the active build.

- `sourcefile`: matched candidate, or the declared path/pattern when nothing matched.
- `sources`: mutable effective source list, initially `{sourcefile}`.
- `depend`: mutable dependinfo, initially containing `sourcefile` in `depend.files`.
- callback return values are ignored.
- file contents are read explicitly by the callback when needed.

`build_callback(target, sourcefile, sourcefiles, depend, opt)` is optional and runs later in the jobgraph for generators that depend on another target.

- discovery alone may change the effective source list and dependency metadata;
- `build_callback` may consume tools/executables/artifacts produced by direct dependency targets in the same build invocation;
- mutating `sourcefiles` inside `build_callback` has no source-list effect;
- all direct `add_deps()` targets, including `{links = false}`, finish before the build callback, so code generators built as dependencies are available to it;
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
- Materialization callbacks do not manually invalidate Xmake caches or touch mtimes to force rebuilds; they express concrete inputs/results through the existing dependency machinery and let Xmake decide dirtiness.
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
