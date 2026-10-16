# Expo applications with extensions

The Linux backend accepts one application and any number of iOS app-extension
targets with a standard Expo Swift host AppDelegate. The exported Xcode product type determines the role, regardless of target
order or the `APPLICATION_EXTENSION_API_ONLY` flag. Other product types and multiple
host applications fail explicitly. Existing single-application graphs remain usable.

Each executable gets its own compiled objects and link invocation. CocoaPods
aggregate dependencies are traversed per target; unrelated static libraries are not
added to its link search paths. Swift and C/Objective-C/C++ sources in application
and extension targets are compiled. Extensions link with `-application_extension
-e _NSExtensionMain -u _main`. The ExpoModulesJSI framework is rebuilt from source
when present, using the installed Linux toolchain and the project's own sources.

Staging writes the host to `Payload/<app>.app` and each extension to
`PlugIns/<extension>.appex`, preserving its Info.plist and NSExtension dictionary.
Scene lifecycle changes apply only to the host. Pod resource dependencies and
native resource phases are copied per target. Expo Widgets JavaScript is rebuilt
with its Metro configuration and stored as
`ExpoWidgets.bundle/ExpoWidgets.bundle`, alongside a BNDL Info.plist, in targets
that depend on ExpoWidgets. Only the host receives the main JavaScript bundle.

Signing requires an exact provisioning profile for every executable bundle and a
shared distribution certificate. Requested entitlements, including App Groups,
are checked against the corresponding profiles before signing. The push environment
is taken from the distribution profile, as in a distribution export. Profile matching
uses bundle identifiers, not JSON entry names. The existing recursive signer and
IPA verifier process both the app and its extensions. Credentials and generated
outputs must remain outside version control.

## SDK selection

Set `"sdk": "iPhoneOS27.0.sdk"` in the local configuration to use an already
installed SDK under `toolchain/sdks` for compilation and linking. The default
remains SDK 26.4 for compilation and 26.5 for linking. Qadra’s resolved OpenIAP
3.4.0 uses StoreKit APIs absent from SDK 26.4; its validation uses the existing
SDK 27.0. No SDK download or installation is performed.

## Limits and validation

This remains an experimental Linux backend. Asset catalogs and storyboards use
existing limited fallbacks; arbitrary Xcode script phases, watch apps, test targets,
multiple host applications, nonstandard host AppDelegate lifecycles, different
signing certificates per target, and
App Store submission are not implemented. Distribution validation currently
expects device provisioning profiles. Framework discovery still uses the pod
frameworks available in the generated project; it is not a general Xcode executor.

SDK-free regression tests cover target classification, dependency cycles/missing
targets, per-target link inputs, C-source compilation dispatch, two embedded
extensions, widget resources, plist isolation, missing profiles and App Group
mismatch. They do not prove a native build, installation, or widget rendering.
See the PR for the observed full-build attempt and remaining blockers.
