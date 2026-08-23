toolchain("bad")
    set_kind("standalone")
    on_check(function (toolchain)
        assert(toolchain:get("patch.prepared", {load = false}),
            "on_toolchain_prepare did not run before bad check")
        assert(not toolchain:config("patch.checked"), "bad check ran more than once")
        toolchain:config_set("patch.checked", true)
        return os.getenv("PATCH_ALLOW_BAD") == "1"
    end)
    on_load(function ()
        raise("unused bad toolchain must never be loaded")
    end)
