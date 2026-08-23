toolchain("good")
    set_kind("standalone")
    on_check(function (toolchain)
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before check")
        assert(not toolchain:get("patch.checked", {load = false}), "good check ran more than once")
        toolchain:set("patch.checked", true)
        -- force the two first-use jobs to overlap at the initialization boundary
        os.sleep(200)
        return true
    end)
    on_load(function (toolchain)
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before load")
        assert(toolchain:get("patch.checked", {load = false}),
            "check did not run before load")
        assert(not toolchain:get("patch.loaded", {load = false}), "good load ran more than once")
        toolchain:set("patch.loaded", true)
        toolchain:set("toolset.cc", "gcc@" .. os.programfile())
    end)
