# Contributing to ios-anywhere

Report bugs or suggest improvements in [issues](https://github.com/rodriguesabner/ios-anywhere/issues). Submit code or documentation changes through a [pull request](https://github.com/rodriguesabner/ios-anywhere/pulls).

## Setup

Use Python 3.11 or newer:

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/ios-anywhere --help
```

Unit tests need no certificates, device, or Apple SDKs. Real builds require the [external toolchain](docs/toolchain.md). Read the [architecture](docs/architecture.md) before changing backends.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q ios_linux tests
node --test tests/signing-setup.test.cjs
git diff --check
```

Signing-helper tests require Node and OpenSSL; they use a fake Apple API and temporary test certificates, never an Apple account.

Add a small test for new logic or a regression fix. Document changes to configuration, commands, and compatibility. Preserve the `ios-linux` alias, existing paths, and `IOS_LINUX_*` variables unless implementing an explicit migration.

## Reports and pull requests

Include the CLI version, Linux distribution and architecture, engine and version, command, expected result, and observed error. Remove secrets and personal information from logs. Provide a minimal example you can share; do not attach SDKs, IPAs, or third-party private projects.

Describe the problem, change, and checks performed. Distinguish unit tests, successful compilation, installation, device execution, and App Store processing. Do not present one stage as proof of another. See [Validation](docs/validation.md).

Preserve copyright and license notices for reused material; update [THIRD_PARTY.md](THIRD_PARTY.md) when needed. Original contributions are intended for the project's MIT license; third-party material retains its own terms. Contribute only material you are authorized to share.
