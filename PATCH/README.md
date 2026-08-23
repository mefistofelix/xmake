# Xmake callback extensions

This fork adds a small set of callback features that can be used directly from `xmake.lua`.

The callbacks run in the normal Xmake sandbox, so normal APIs such as `os.runv()`, `os.vrunv()`, `os.execv()`, `os.iorunv()`, `io.*`, `path.*`, environment access, and imported modules are available.

## `on_toolchain_prepare`

Use this when a toolchain needs to be materialized or configured immediately before Xmake performs the first real toolchain check.

```lua
on_toolchain_prepare(function (toolchain)
    if toolchain:name() == "mytoolchain" then
        os.vrunv("sdk-bootstrap", {"--prepare"})
        toolchain:set("sdkdir", path.join(os.projectdir(), "sdk"))
    end
end)
```

Signature:

```lua
on_toolchain_prepare(function (toolchain)
end)
```

The callback receives the toolchain instance.

For a lazily used toolchain, the relevant order is:

```text
on_toolchain_prepare
-> toolchain on_check
-> toolchain on_load
-> first actual tool use
```

Declaring a toolchain does not by itself run this callback. It runs when Xmake reaches the first real check for that runtime toolchain instance.

Typical uses:

- download or unpack an SDK;
- generate a compiler wrapper;
- set environment-dependent toolchain data;
- prepare files that `on_check` or `on_load` expect to exist.

## `before_sources`

Use this when files or directories must exist before Xmake performs the first `add_files()` matching for a target.

```lua
target("app")
    before_sources(function (target)
        os.mkdir("generated")
        os.vrunv("generator", {"--out", "generated"})
    end)
    add_files("generated/*.c")
```

Signature:

```lua
before_sources(function (target)
end)
```

The callback receives the target instance.

It runs once for that target instance, immediately before the first source-list materialization. Files created by the callback are therefore visible to that same first `add_files()` glob.

The callback follows the first real caller of the target source list. It is not artificially restricted to the `build` command.

Typical uses:

- create a generated source directory before a glob is expanded;
- materialize generated sources that do not need another target to be built first;
- prepare source manifests or generated file trees before source discovery.

## `add_files(..., {source = ...})`

Use `source` when one declared input can deterministically become zero, one, or many effective source files during source discovery.

```lua
target("app")
    add_files("schema/*.idl", {
        source = function (sourcefile, sourcefiles, depend)
            local outfile = path.join("generated", path.basename(sourcefile) .. ".c")

            os.mkdir("generated")
            os.vrunv("idl-generator", {sourcefile, "-o", outfile})

            sourcefiles[1] = outfile
            table.insert(depend.files, "generator-config.json")
        end
    })
```

Signature:

```lua
source = function (sourcefile, sourcefiles, depend)
end
```

Arguments:

- `sourcefile`: the matched source candidate, or the declared path/pattern if there was no match;
- `sourcefiles`: a mutable list initially containing `{sourcefile}`;
- `depend`: mutable dependency information, initially containing `sourcefile` in `depend.files`.

Return values are ignored. Modify `sourcefiles` and `depend` directly.

`source` may:

- keep the original source;
- replace it;
- expand one source into several sources;
- remove it by emptying `sourcefiles`;
- generate files immediately;
- append deterministic inputs or outputs to `depend.files`.

Without a `build` callback, only resulting paths that exist after `source` are added to the target source list.

## `add_files(..., {build = ...})`

Use `build` when the same deterministic source transformation must happen later because it needs a target dependency to finish first, for example when the generator executable is itself built by Xmake.

```lua
target("codegen")
    set_kind("binary")
    add_files("tools/codegen.c")

target("app")
    add_deps("codegen", {links = false})
    add_files("schema/input.def", {
        source = function (sourcefile, sourcefiles, depend)
            sourcefiles[1] = "generated/input.c"
            table.insert(depend.files, "schema/options.json")
        end,
        build = function (sourcefile, sourcefiles, depend)
            os.mkdir("generated")
            os.vrunv(path.join("build", "codegen.exe"), {sourcefile, "-o", sourcefiles[1]})
        end
    })
```

Signature:

```lua
build = function (sourcefile, sourcefiles, depend)
end
```

It receives the same three kinds of arguments as `source`.

`source` and `build` are two phases of the same incremental transformation. They share one dependency record and one dirty/clean decision:

```text
inputs unchanged
-> neither source nor build runs
-> previous effective sourcefiles are restored

inputs changed / missing
-> source runs
-> direct add_deps() targets finish
-> build runs
-> dependency state is saved
```

This means that when the transformation becomes dirty, both configured phases run again. There is no independent dirtiness decision for `build`.

All direct `add_deps()` targets, including dependencies declared with `{links = false}`, complete before `build` runs. The `build` callbacks complete before the normal `before_build_file`, `before_build_files`, and file-rule build work for the generated sources.

A `build` callback may also append entries to `depend.files`. It receives the mutable `sourcefiles` table too, although changing the source list at that late stage does not rewrite source jobs that were already scheduled for the current build invocation.

`build` requires the normal Xmake jobgraph build mode.

## Dependency behavior

The `source`/`build` pair uses normal Xmake dependency semantics.

For each original source candidate:

- the original candidate starts in `depend.files`;
- effective source paths are added to `depend.files`;
- callbacks may append more concrete deterministic dependencies;
- missing dependency paths make the transformation dirty;
- if nothing relevant changed, the callbacks are skipped and the previous effective source list is reused;
- if a callback fails, successful dependency state is not recorded for the unfinished transformation.

Example:

```lua
add_files("model.in", {
    source = function (sourcefile, sourcefiles, depend)
        sourcefiles[1] = "generated/model.c"
        table.insert(depend.files, "model.options")
    end,
    build = function (sourcefile, sourcefiles, depend)
        os.vrunv("model-generator", {sourcefile, "model.options", sourcefiles[1]})
    end
})
```

Changing `model.in`, changing `model.options`, or removing `generated/model.c` makes the transformation dirty and causes the configured callbacks to run again.

## Callback order

For a target that uses all of these features, the relevant order is conceptually:

```text
on_toolchain_prepare   (only when that toolchain is first actually checked)
-> toolchain check/load
-> before_sources      (before the target's first source-list materialization)
-> add_files source    (for each dirty source candidate)
-> direct target dependencies build
-> add_files build     (for each dirty candidate that has build=...)
-> normal before_build_file[s] / file build rules
```

The exact first two positions depend on which operation first needs the toolchain or the source list; the callbacks remain lazy and run at their actual Xmake lifecycle boundaries.
