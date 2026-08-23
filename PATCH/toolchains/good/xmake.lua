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
