toolchain("good")
    set_kind("standalone")
    on_check(function (toolchain)
        local prepared = toolchain:get("patch.prepared", {load = false})
        local state = toolchain:get("patch.check_state", {load = false})
        if prepared then
            assert(state ~= "build", "good build-time check ran more than once")
            toolchain:set("patch.check_state", "build")
            -- force the two first-use jobs to overlap at the initialization boundary
            os.sleep(200)
        else
            assert(not state, "good config-time check ran more than once")
            toolchain:set("patch.check_state", "config")
        end
        return true
    end)
    on_load(function (toolchain)
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before load")
        assert(toolchain:get("patch.check_state", {load = false}) == "build",
            "build-time check did not run before load")
        assert(not toolchain:get("patch.loaded", {load = false}), "good load ran more than once")
        toolchain:set("patch.loaded", true)
        toolchain:set("toolset.cc", "gcc@" .. os.programfile())
    end)
