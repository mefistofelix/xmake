set_project("xmake-patch-tests")

toolchain("good")
    set_kind("standalone")
    set_runtimes("patch-static-runtime")
    on_check(function (toolchain)
        print("[callback] toolchain on_check: " .. toolchain:name())
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before check")
        toolchain:config_set("patch.checked", true)
        return true
    end)
    on_load(function (toolchain)
        print("[callback] toolchain on_load: " .. toolchain:name())
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before load")
        assert(toolchain:config("patch.checked"), "check did not run before load")
        toolchain:set("toolset.cc", "gcc@" .. os.programfile())
    end)

toolchain("bad")
    set_kind("standalone")
    set_runtimes("bad-static-runtime")
    on_check(function ()
        raise("unused bad toolchain must never be detected")
    end)
    on_load(function ()
        raise("unused bad toolchain must never be loaded")
    end)
toolchain_end()

local function _marker(name)
    return path.join(os.projectdir(), ".patch-" .. name)
end

on_toolchain_prepare(function (toolchain)
    local name = toolchain:name()
    if name == "good" or name == "bad" then
        print("[callback] on_toolchain_prepare: " .. name)
        assert(not toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare ran more than once for %s", name)
        local preparedir = path.join(os.projectdir(), ".patch-toolchain-prepare")
        os.mkdir(preparedir)
        os.vrunv(os.getenv("COMSPEC") or "cmd", {"/c", "exit", "0"})
        io.writefile(_marker("prepare-" .. name), preparedir)
        toolchain:set("patch.prepared", true)
    end
end)

target("dep")
    set_kind("phony")
    on_config(function ()
        io.writefile(_marker("config-dep"), "1")
    end)
    on_build(function ()
        io.writefile(_marker("build-dep"), "1")
    end)

target("app")
    set_kind("phony")
    set_toolchains("good")
    add_deps("dep", {links = false})
    on_config(function ()
        io.writefile(_marker("config-app"), "1")
    end)
    on_build(function (target)
        assert(target:tool("cc"), "good toolchain did not provide cc")
        io.writefile(_marker("use-good"), "1")
    end)

target("unused")
    set_kind("phony")
    set_default(false)
    set_toolchains("bad")
    on_config(function ()
        io.writefile(_marker("config-unused"), "1")
    end)

target("before-sources")
    set_kind("phony")
    set_default(false)
    before_sources(function (target)
        print("[callback] before_sources: " .. target:name())
        assert(target, "before_sources did not receive target")
        os.vrunv(os.getenv("COMSPEC") or "cmd", {"/c", "exit", "0"})
        local sourcedir = path.join(os.projectdir(), ".patch-before-sources-files")
        local marker = _marker("before-sources-count")
        local count = os.isfile(marker) and (tonumber(io.readfile(marker)) or 0) or 0
        io.writefile(marker, tostring(count + 1))
        os.mkdir(sourcedir)
        io.writefile(path.join(sourcedir, "generated.c"), "")
    end)

task("test-before-sources")
    set_menu {usage = "xmake test-before-sources", description = "Run before_sources regression tests", options = {}}
    on_run(function ()
        local project = import("core.project.project")
        local sourcedir = path.join(os.projectdir(), ".patch-before-sources-files")
        local marker = _marker("before-sources-count")
        os.tryrm(sourcedir)
        os.tryrm(marker)

        local template = project.target("before-sources")
        local empty = template:sourcefiles()
        assert(#empty == 0, "target without add_files unexpectedly has sources")
        assert(not os.isfile(marker), "before_sources ran for a target without add_files")

        local target = template:clone()
        target:set("files", ".patch-before-sources-files/*.c")
        local sourcefiles = target:sourcefiles()
        assert(#sourcefiles == 1 and path.filename(sourcefiles[1]) == "generated.c",
            "before_sources output was not visible to first add_files materialization")
        assert(io.readfile(marker) == "1", "before_sources did not run exactly once")

        local sourcefiles_again = target:sourcefiles()
        assert(#sourcefiles_again == 1 and sourcefiles_again[1] == sourcefiles[1],
            "cached source list changed after first materialization")
        assert(io.readfile(marker) == "1", "before_sources ran more than once")

        os.tryrm(sourcedir)
        os.tryrm(marker)
        print("before_sources patch tests passed")
    end)

target("materialize-dep")
    set_kind("phony")
    set_default(false)
    on_build(function ()
        print("[callback] dependency on_build: materialize-dep")
        local tracefile = path.join(os.projectdir(), ".patch-materialize-order")
        io.writefile(tracefile, (os.isfile(tracefile) and io.readfile(tracefile) or "") .. "dependency on_build\n")
        io.writefile(_marker("materialize-dep-ready"), "ready")
    end)

target("materialize-app")
    set_kind("object")
    set_default(false)
    add_deps("materialize-dep", {links = false})
    before_sources(function (target)
        print("[callback] before_sources: " .. target:name())
        local tracefile = path.join(os.projectdir(), ".patch-materialize-order")
        io.writefile(tracefile, (os.isfile(tracefile) and io.readfile(tracefile) or "") .. "before_sources\n")
        assert(target:name() == "materialize-app", "before_sources received unexpected target")
    end)
    add_files(".patch-materialize/input.in", {
        source = function (sourcefile, sourcefiles, depend)
            print("[callback] add_files source: " .. sourcefile)
            local tracefile = path.join(os.projectdir(), ".patch-materialize-order")
            io.writefile(tracefile, (os.isfile(tracefile) and io.readfile(tracefile) or "") .. "add_files source\n")
            os.vrunv(os.getenv("COMSPEC") or "cmd", {"/c", "exit", "0"})
            local marker = path.join(os.projectdir(), ".patch-materialize-source-count")
            local count = os.isfile(marker) and (tonumber(io.readfile(marker)) or 0) or 0
            io.writefile(marker, tostring(count + 1))
            assert(#sourcefiles == 1 and sourcefiles[1] == sourcefile, "source callback received unexpected source list")
            assert(#depend.files == 1 and depend.files[1] == sourcefile, "source callback received unexpected dependency list")
            depend.shared_marker = "source"
            table.insert(depend.files, ".patch-materialize/source.dep")
            sourcefiles[1] = ".patch-materialize/generated.c"
        end,
        build = function (sourcefile, sourcefiles, depend)
            print("[callback] add_files build: " .. sourcefile)
            local tracefile = path.join(os.projectdir(), ".patch-materialize-order")
            io.writefile(tracefile, (os.isfile(tracefile) and io.readfile(tracefile) or "") .. "add_files build\n")
            os.vrunv(os.getenv("COMSPEC") or "cmd", {"/c", "exit", "0"})
            local marker = path.join(os.projectdir(), ".patch-materialize-build-count")
            local count = os.isfile(marker) and (tonumber(io.readfile(marker)) or 0) or 0
            io.writefile(marker, tostring(count + 1))
            assert(os.isfile(path.join(os.projectdir(), ".patch-materialize-dep-ready")),
                "build callback ran before links=false dependency")
            assert(depend.shared_marker == "source", "source/build callbacks did not share the same depend table")
            assert(#sourcefiles == 1 and sourcefiles[1] == ".patch-materialize/generated.c",
                "build callback did not receive source output list")
            io.writefile(sourcefiles[1], "generated")
            local sidecar = ".patch-materialize/generated.sidecar"
            io.writefile(sidecar, "sidecar")
            table.insert(sourcefiles, sidecar)
            table.insert(depend.files, ".patch-materialize/build.dep")
        end
    })
    on_build_file(function (_, sourcefile)
        print("[callback] on_build_file: " .. sourcefile)
        local tracefile = path.join(os.projectdir(), ".patch-materialize-order")
        io.writefile(tracefile, (os.isfile(tracefile) and io.readfile(tracefile) or "") .. "on_build_file\n")
        assert(sourcefile == ".patch-materialize/generated.c", "unexpected materialized source: %s", sourcefile)
        assert(os.isfile(sourcefile), "normal file job ran before build callback generated its output")
        local marker = path.join(os.projectdir(), ".patch-materialize-consumed-count")
        local count = os.isfile(marker) and (tonumber(io.readfile(marker)) or 0) or 0
        io.writefile(marker, tostring(count + 1))
    end)

task("test-add-files")
    set_menu {usage = "xmake test-add-files", description = "Run add_files source/build callback regression tests", options = {}}
    on_run(function ()
        local workdir = path.join(os.projectdir(), ".patch-materialize")
        local markers = {
            "materialize-source-count", "materialize-build-count", "materialize-consumed-count", "materialize-dep-ready",
            "materialize-order"
        }
        os.tryrm(workdir)
        for _, name in ipairs(markers) do
            os.tryrm(_marker(name))
        end
        os.mkdir(workdir)
        io.writefile(path.join(workdir, "input.in"), "input")
        io.writefile(path.join(workdir, "source.dep"), "source dependency")
        io.writefile(path.join(workdir, "build.dep"), "build dependency")

        -- this plain config does not resolve the materialized source list, so callbacks stay lazy
        print("[test-add-files] standalone config")
        os.runv(os.programfile(), {"f", "-c"})
        assert(not os.isfile(_marker("materialize-source-count")), "source callback ran before source discovery")
        assert(not os.isfile(_marker("materialize-build-count")), "build callback ran before source discovery")

        -- first dirty build runs source, waits for links=false dep, then runs build before the file job
        print("[test-add-files] dirty build #1")
        os.runv(os.programfile(), {"build", "materialize-app"})
        print("[test-add-files] observed order #1:\n" .. io.readfile(_marker("materialize-order")):trim())
        assert(io.readfile(_marker("materialize-source-count")) == "1", "source callback did not run once")
        assert(io.readfile(_marker("materialize-build-count")) == "1", "build callback did not run once")
        assert(os.isfile(path.join(workdir, "generated.c")), "build callback did not generate source output")
        assert(os.isfile(path.join(workdir, "generated.sidecar")), "build callback did not generate sidecar output")

        -- clean build reuses depend.result and executes neither callback
        os.tryrm(_marker("materialize-order"))
        print("[test-add-files] clean build #2")
        os.runv(os.programfile(), {"build", "materialize-app"})
        print("[test-add-files] observed order #2:\n" .. io.readfile(_marker("materialize-order")):trim())
        assert(io.readfile(_marker("materialize-source-count")) == "1", "source callback reran on clean build")
        assert(io.readfile(_marker("materialize-build-count")) == "1", "build callback reran on clean build")

        -- a source added by build is tracked in the same depend record; removing it dirties both phases
        os.tryrm(path.join(workdir, "generated.sidecar"))
        os.tryrm(_marker("materialize-dep-ready"))
        os.tryrm(_marker("materialize-order"))
        print("[test-add-files] dirty build #3 after removing generated.sidecar")
        os.runv(os.programfile(), {"build", "materialize-app"})
        print("[test-add-files] observed order #3:\n" .. io.readfile(_marker("materialize-order")):trim())
        assert(io.readfile(_marker("materialize-source-count")) == "2", "source callback did not rerun with dirty dependency")
        assert(io.readfile(_marker("materialize-build-count")) == "2", "build callback did not rerun with dirty dependency")

        os.tryrm(workdir)
        for _, name in ipairs(markers) do
            os.tryrm(_marker(name))
        end
        print("add_files source/build patch tests passed")
    end)

task("test-noop")
    set_menu {usage = "xmake test-noop", description = "Run no-op build performance regression tests", options = {}}
    on_run(function ()
        local depend = import("core.project.depend")
        local project = import("core.project.project")

        local function contains(values, expected)
            for _, value in ipairs(values or {}) do
                if path.translate(value) == path.translate(expected) then
                    return true
                end
            end
        end

        local removedir = path.join(os.projectdir(), ".patch-noop-remove")
        os.mkdir(removedir)
        io.writefile(path.join(removedir, "keep.c"), "")
        io.writefile(path.join(removedir, "remove.c"), "")
        io.writefile(path.join(removedir, "ignored.c"), "")
        local synthetic = project.target("dep"):clone()
        synthetic:set("files", ".patch-noop-remove/*.c|ignored.c", "__remove_./.patch-noop-remove/remove*.c")
        local sourcefiles = synthetic:sourcefiles()
        assert(#sourcefiles == 1 and contains(sourcefiles, ".patch-noop-remove/keep.c"),
            "remove_files filtering changed: %s", table.concat(sourcefiles, ", "))

        local dependdir = path.join(os.projectdir(), ".patch-noop-depend")
        os.mkdir(dependdir)
        local currentfile = path.join(dependdir, "current.d")
        local oldfile = path.join(dependdir, "old.d")
        local plainfile = path.join(dependdir, "plain.d")
        local depfiles = "object.o: .patch-noop-depend/a.h .patch-noop-depend/b.h"
        local dependinfo = {
            files = {"seed.h"},
            values = {"value"},
            depfiles_format = "gcc",
            depfiles = depfiles
        }

        depend.save(dependinfo, currentfile)
        assert(dependinfo.depfiles == depfiles and dependinfo.depfiles_format == "gcc",
            "depend.save mutated compiler dependency payload")
        assert(#dependinfo.files == 1 and dependinfo.files[1] == "seed.h",
            "depend.save mutated caller dependency files")
        local saved = io.load(currentfile)
        assert(saved and not saved.depfiles and not saved.depfiles_format,
            "new dependency record retained raw compiler payload")
        assert(contains(saved.files, "seed.h") and contains(saved.files, ".patch-noop-depend/a.h")
            and contains(saved.files, ".patch-noop-depend/b.h"),
            "new dependency record did not materialize compiler dependencies")

        io.save(oldfile, dependinfo)
        local old = depend.load(oldfile)
        assert(old and not old.depfiles and not old.depfiles_format,
            "old compiler dependency record was not materialized on load")
        assert(contains(old.files, "seed.h") and contains(old.files, ".patch-noop-depend/a.h")
            and contains(old.files, ".patch-noop-depend/b.h"),
            "old dependency record lost compiler dependencies")

        local plain = {files = {"plain.h"}, values = {"plain"}}
        depend.save(plain, plainfile)
        local plainsaved = io.load(plainfile)
        assert(plainsaved and #plainsaved.files == 1 and plainsaved.files[1] == "plain.h"
            and #plainsaved.values == 1 and plainsaved.values[1] == "plain",
            "non-compiler dependency record changed")

        os.tryrm(removedir)
        os.tryrm(dependdir)
        print("no-op build performance patch tests passed")
    end)
