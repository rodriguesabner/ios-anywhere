# GitHub Actions IPA builds

[Build IPA workflow](../.github/workflows/build-ipa.yml) adds **manual builds on an already prepared Linux x86_64 runner**. Choose the bundled Godot or Expo counter, compile, sign, locally verify, and optionally download `app.ipa` from the run's artifacts after explicitly approving its audience. It never installs on a device or submits to Apple.

This is separate from [SDK-free unit CI](../.github/workflows/tests.yml), which continues to run on GitHub-hosted Ubuntu for pushes and pull requests. **The build workflow does not bootstrap a blank GitHub-hosted runner.** Apple SDKs, Darwin overlays, host macros, Ruby layout, and compatible engine libraries remain explicit prerequisites. No SDK mirror downloads or unsigned toolchain archives are added.

## Prepare once, outside this workflow

1. Provision a dedicated Linux x86_64 runner yourself. Follow [installation](installation.md) and [toolchain layout](toolchain.md), and successfully build your selected backend privately first. Supply Python 3.11+ with venv/pip, Node/npm, OpenSSL, and the backend-specific tools. Allow sufficient free disk for native dependencies and temporary builds. The workflow installs the Python CLI into a fresh virtual environment, not system Python; its pip dependencies still follow `pyproject.toml` and are not a fully locked environment.
2. Keep a reviewed config, toolchain, and signing credentials **outside the checkout**. Use absolute config and credentials paths. Paths inside the credentials JSON are relative to that JSON, as in [credentials.example.json](../credentials.example.json). Keep the JSON, certificate, and profile readable only by the runner account. This workflow reads existing files; it does not generate, store in GitHub, or rotate credentials.
3. Configure a GitHub environment named `ios-build` with required reviewers and deployment branches restricted to `main`, where your GitHub plan supports these protections. Approval must happen before the signing runner receives the job. Do not assume an environment name alone enables protection. If suitable protections are unavailable, do not attach a signing runner to a public repository; use a private, access-controlled consumer repository instead.
4. Restrict runner access to trusted workflows/repositories using runner groups where supported. Give the prepared runner the labels `self-hosted`, `Linux`, `X64`, `ios-anywhere`. Prefer an ephemeral, isolated runner and disposable workspace. Anyone whose code executes on the machine can read its credentials, regardless of whether GitHub secrets are exposed. Do not share this runner with pull-request jobs or untrusted repositories.
5. Set these environment **variables**, containing paths and an app identity, not secret contents:

   - `IOS_ANYWHERE_CONFIG`: absolute path to your existing toolchain config JSON.
   - `IOS_ANYWHERE_CREDENTIALS`: absolute path to your existing signing credentials JSON.
   - `IOS_ANYWHERE_BUNDLE_ID`: the bundle identifier authorized by the supplied provisioning profile.

The configured cache is deliberately ignored for CI. Every run creates an isolated temporary cache and project copy; the durable toolchain, existing cache, and credential files are preserved. Expo's bundle ID is changed only in the disposable sample copy. Godot receives `--bundle-id` directly.

These runner/environment/credential setup steps are operator actions, not performed by opening or merging this change. Registering infrastructure, granting persistent access, accepting licenses, and purchasing services require your own authorization.

## Run and retrieve

After reviewing and merging the workflow onto `main`, open Actions → **Build IPA (prepared runner)** → Run workflow. Select **main** and the backend. IPA upload is **off by default**. Enable the upload checkbox only if you approve sharing the signed app, embedded profile, and device identifiers with repository readers. Without that checkbox the job builds/verifies, then removes the local output without publishing an artifact. Approve the environment deployment if configured. Non-main refs and fork repositories are skipped by the checked-in workflow. There are no push, PR, release, or submission triggers, and checkout credentials are not persisted.

The job installs the CLI, validates the configured toolchain and external signing inputs, then calls the same `ios-anywhere ... build --output ...` command as local builds. The build already verifies the produced IPA before returning success. When explicitly enabled, Actions uploads only that exact `app.ipa`, with one-day retention and a unique run/attempt artifact name. It does not upload the toolchain, source cache, logs, credentials, or verification JSON.

**Artifact visibility matters:** a signed IPA contains the app and its embedded provisioning profile, which may contain device identifiers and team information. Anyone allowed to download your repository's Actions artifacts may access it. Use an appropriately restricted private repository for real app/device data. One-day retention is not access control. Do not run this public-repository example with sensitive profiles unless that audience is acceptable.

Project hooks/dependencies execute as the runner account. Manual dispatch and a branch condition are not a sandbox: an attacker who can modify trusted workflow code or run another workflow on the same runner can bypass those checks. Restrict write access, review workflow changes, protect `main`, and enforce environment/runner access controls before provisioning signing material.

## Failures and cleanup

- A queued job usually needs the prepared runner online with the exact labels, or environment approval. No automatic runner provisioning occurs.
- Preflight catches missing files/commands and non-executable tools. It does not prove ABI/SDK compatibility, certificate validity, Apple trust, or application runtime behavior. Run `ios-anywhere --config /private/config.json --engine godot doctor` (or `expo`) privately for detailed toolchain diagnostics.
- Build output is redirected to temporary private logs and never printed/uploaded, because arbitrary project hooks or signer errors can expose private values. Failure messages are intentionally sanitized. To diagnose, reproduce the documented local CLI build in a private terminal with a fresh output path and inspect that private cache. Do not paste raw signing logs into public issues.
- The helper redirects npm and CocoaPods caches plus XDG cache into the disposable build directory; pip caching is disabled. Third-party tools may still write elsewhere on the runner, so this is not a sandbox. Temporary build state and the venv are removed on normal success/failure. The workflow's `always()` cleanup also handles ordinary cancellation. Abrupt runner termination can leave files behind; ephemeral runner teardown or operator cleanup is still required. Existing credentials remain provisioned on the runner and are not deleted by the workflow.
- No IPA has been built by this new workflow as part of its SDK-free tests. A first successful run on a real prepared runner is required before claiming CI build/signing validation. A local verification pass is not a device launch, Apple processing, or approval result.

## Use your own app

Copy and review the workflow in an access-controlled app repository. Update the exact repository allowlist and trusted branch condition deliberately; preserve manual triggering, approval gates, and restricted runners. Pin ios-anywhere to a reviewed commit rather than an unreviewed moving branch. Use the same CLI shape:

```sh
ios-anywhere --config "$CONFIG" --engine expo \
  --project "$APP_SOURCE" --credentials "$CREDENTIALS" \
  build --output "$NEW_OUTPUT_DIR/app.ipa"
# Godot: --engine godot and --bundle-id com.yourcompany.game before build.
```

The bundled `scripts/ci_build.py` intentionally builds only the repository's two reviewed examples. For a real app, supply its reviewed source/lockfile, its own identity, and a per-run config/cache outside the app tree. Do not add arbitrary checkout refs or project URLs as signing-workflow inputs. Preserve private log handling, fresh output paths, exact IPA-only uploads, and cleanup. Store submission is a separate, explicitly authorized workflow.
