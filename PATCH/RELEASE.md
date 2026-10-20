Xmake with the fork's existing patches. The release title identifies the official native base; the notes below identify the source commit.

- Lazy Windows IDL discovery and toolchain preparation.
- `before_sources` and incremental `add_files` source/build callbacks.
- No-op source filtering and compiler dependency optimizations.
- Windows x64 ZIP and Linux x86_64 tar.gz, each containing a standalone bundled executable, documentation, license and `build-info.json`.
- Official upstream release native cores with the fork's Lua payload. No native core rebuild. Exact base and payload hashes are included in `build-info.json`.

Both packages pass `test-patches` through their bundled executable, without `XMAKE_PROGRAM_DIR` and with host compiler tools excluded from test subprocess PATH. This covers lazy toolchain preparation, source discovery, dependency ordering, clean-build callback reuse and legacy dependency records. There is no retained IDL/MIDL regression or real compiler/SDK integration test.

Verify the adjacent `.sha256` file before extracting. Linux requires glibc and the official bundle's runtime libraries (`libncurses.so.6` and `libtinfo.so.6`); the executable is not a static musl build.

The automation creates a draft after both native platforms pass. Publish the reviewed draft manually.
