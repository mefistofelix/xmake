set_project("xmake-lazy-toolchain-patch-tests")

add_toolchaindirs("toolchains")

local function _marker(name)
    return path.join(os.projectdir(), ".patch-" .. name)
end

on_toolchain_prepare(function (toolchain)
    local name = toolchain:name()
    if name == "good" or name == "bad" then
        assert(not toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare ran more than once for %s", name)
        toolchain:set("patch.prepared", true)
    end
end)

target("dep")
    set_kind("phony")
    on_config(function (target)
        assert(target:toolchain("none"), "phony dependency did not use the none toolchain")
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
        assert(os.isfile(_marker("config-dep")), "dependency on_config did not run before app")
        io.writefile(_marker("config-app"), "1")
    end)
    on_build(function (target, jobgraph)
        jobgraph:add(target:fullname() .. "/tool_user_1", function ()
            assert(target:tool("cc"), "good toolchain did not provide cc")
            io.writefile(_marker("use-one"), "1")
        end)
        jobgraph:add(target:fullname() .. "/tool_user_2", function ()
            assert(target:tool("cc"), "good toolchain did not provide cc")
            io.writefile(_marker("use-two"), "1")
        end)
    end, {jobgraph = true})

target("unused")
    set_kind("phony")
    set_default(false)
    set_toolchains("bad")
    set_configdir(path.join(os.projectdir(), ".patch-unused-config"))
    add_configfiles("fixtures/unused.in", {onlycopy = true})
    on_config(function (target)
        local bad = assert(target:toolchain("bad"), "bad toolchain missing")
        assert(bad:config("patch.checked"), "unused target was configured before its toolchain was checked")
        -- make source discovery observable if this unrelated target is configured
        target:sourcefiles()
        io.writefile(_marker("config-unused"), "1")
    end)
