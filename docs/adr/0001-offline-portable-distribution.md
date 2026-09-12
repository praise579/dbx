# Offline portable package bundles its own WebView2 Fixed Version Runtime

Some deployments run DBX on air-gapped Windows x64 machines where executing installers is blocked entirely, so neither the NSIS installer nor the `-offline-setup.exe` (which is still an installer) can be used. The existing portable ZIP satisfies "no install", but the bare `dbx.exe` needs the Evergreen WebView2 Runtime, which cannot be installed offline.

We extend the portable package into an **offline portable package**: it bundles a Fixed Version WebView2 Runtime as a folder (`WebView2Runtime/` next to `DBX.exe`). At startup, portable builds point `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` at that folder before the first webview is created; the vendored wry was patched to honor an explicitly set folder on all Windows targets (previously only the Win7 target on Win7/2012R2 respected it).

## Considered Options

- **Launcher script setting the env var** (a `.bat` wrapping `DBX.exe`): zero code changes, but breaks "double-click DBX.exe" and any file associations.
- **Reuse the Win7-target build** (`x86_64-win7-windows-msvc`), which already honors the env var: it is a specialized target validated for Win7/2012R2, not for Windows 11.
- **Chosen**: small wry patch + normal x64 build + bundled recent Fixed Version Runtime (133.x; the Win7 build stays pinned to 109 for OS reasons).

## Consequences

- Portable builds self-locate their runtime; a user-set `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` always wins, so the override remains available.
- In portable mode the update check short-circuits locally (no network call, no update errors offline); updates happen by replacing the package folder.
- Kafka is the one required database that needs an agent driver plus a platform-specific JRE; the workflow assembles its agent offline import package from the official `agents-latest` registry on CI (export from a local machine would be platform-mismatched for ARM Mac developers). MySQL/Redis/Elasticsearch need nothing extra.
- The fork-produced `DBX.exe` is unsigned; if a target machine's policy blocks even unsigned executables, only an administrator allowlist helps.
