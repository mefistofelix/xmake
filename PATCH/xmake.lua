set_project("xmake-patch-tests")

toolchain("good")
    set_kind("standalone")
    set_runtimes("patch-static-runtime")
    on_check(function (toolchain)
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before check")
        toolchain:config_set("patch.checked", true)
        return true
    end)
    on_load(function (toolchain)
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
        assert(not toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare ran more than once for %s", name)
        local preparedir = path.join(os.projectdir(), ".patch-toolchain-prepare")
        os.mkdir(preparedir)
        os.runv(os.programfile(), {"--version"})
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
