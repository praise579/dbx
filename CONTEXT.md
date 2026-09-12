# DBX

DBX is a desktop database client (an open-source alternative to DBeaver/TablePlus) built with Tauri 2. Connections to databases either compile into the app or run in separate agent processes managed by the app.

## Language

### Distribution

**Portable package (绿色包)**:
A ZIP containing `DBX.exe` plus a `portable.dbx` marker; extracting and double-clicking is the whole install. Data lives in `data/` next to the executable. The whole folder can run from removable media.
_Avoid_: green package, portable version, 免安装包

**Offline portable package**:
A portable package that additionally bundles a Fixed Version WebView2 Runtime (`WebView2Runtime/`) and Kafka agent offline import package (`agents-offline/`), so an air-gapped Windows machine needs nothing else. Produced by the `offline-portable.yml` workflow.
_Avoid_: offline green package, 离线绿色包

**Offline installer**:
The `-offline-setup.exe` NSIS installer with WebView2 built in. Despite the name it is still an installer — it must execute and write to the machine. Not usable when installers are blocked.
_Avoid_: offline package (ambiguous with offline portable package)

**Fixed Version Runtime**:
A WebView2 Runtime shipped as a plain folder, selected via `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`; never installed or registered. Distinct from the Evergreen runtime, which is machine-installed.

**Agent driver**:
A per-database-type helper process (Go or Java) downloaded on demand into `<data>/agents/drivers/<db-type>/` and driven over JSON-RPC. Databases with built-in pure-Rust drivers (MySQL, PostgreSQL, Redis, MongoDB, SQL Server, Elasticsearch, …) do not use agent drivers.

**Agent offline import package**:
A ZIP (`agent-registry.json` + `drivers/*.jar|native` + `jre/*.tar.zst`) produced by export or assembly, importable from the app UI to install agent drivers and their JRE without network access. Platform-specific: a package built for `windows-x64` only serves `windows-x64`.
_Avoid_: offline driver zip, 离线驱动包
