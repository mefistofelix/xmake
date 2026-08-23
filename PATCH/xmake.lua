set_project("xmake-lazy-toolchain-patch-tests")

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
