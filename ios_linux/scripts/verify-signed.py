import hashlib, json, os, pathlib, plistlib, struct, subprocess, sys, tempfile, zipfile

ipa = pathlib.Path(sys.argv[1])
results = []
with zipfile.ZipFile(ipa) as z, tempfile.TemporaryDirectory() as temp:
    assert z.testzip() is None
    roots = [
        name[: -len("Info.plist")]
        for name in z.namelist()
        if name.endswith((".app/Info.plist", ".appex/Info.plist"))
    ]
    assert roots, "No app bundles found"
    for root in roots:
        info_bytes = z.read(root + "Info.plist")
        info = plistlib.loads(info_bytes)
        prov = subprocess.run(
            ["openssl", "cms", "-verify", "-inform", "DER", "-noverify"],
            input=z.read(root + "embedded.mobileprovision"),
            capture_output=True,
            check=True,
        )
        profile = plistlib.loads(prov.stdout)
        assert profile.get("ProvisionedDevices"), (
            "Expected a device provisioning profile"
        )
        if os.environ.get("IOS_LINUX_UDID"):
            assert os.environ["IOS_LINUX_UDID"] in profile["ProvisionedDevices"]
        assert profile["Entitlements"]["application-identifier"].endswith(
            "." + info["CFBundleIdentifier"]
        ), "Profile identity differs from app"
        b = z.read(root + info["CFBundleExecutable"])
        assert b[:4] == bytes.fromhex("cffaedfe")
        start = length = None
        off = 32
        for _ in range(struct.unpack_from("<I", b, 16)[0]):
            cmd, size = struct.unpack_from("<II", b, off)
            if cmd == 0x1D:
                start, length = struct.unpack_from("<II", b, off + 8)
            off += size
        assert start is not None, "Missing code signature"
        blob = b[start : start + length]
        magic, total, count = struct.unpack_from(">III", blob)
        assert magic == 0xFADE0CC0
        slots = {}
        for i in range(count):
            kind, pos = struct.unpack_from(">II", blob, 12 + 8 * i)
            size = struct.unpack_from(">I", blob, pos + 4)[0]
            slots[kind] = blob[pos : pos + size]
        entitlements = plistlib.loads(slots[5][8:])
        assert (
            entitlements["application-identifier"]
            == profile["Entitlements"]["application-identifier"]
        )
        assert not entitlements.get("get-task-allow", False)
        cds = [v for k, v in slots.items() if k == 0 or 0x1000 <= k <= 0x1005]
        assert cds, "Missing code directory"
        for cd in cds:
            hash_off, _, special, pages, limit = struct.unpack_from(">IIIII", cd, 16)
            hsize, htype, _, page_exp = struct.unpack_from("BBBB", cd, 36)
            hashfn = {
                1: hashlib.sha1,
                2: hashlib.sha256,
                3: hashlib.sha256,
                4: hashlib.sha384,
            }[htype]
            for i in range(pages):
                chunk = b[i * (1 << page_exp) : min((i + 1) * (1 << page_exp), limit)]
                assert (
                    hashfn(chunk).digest()[:hsize]
                    == cd[hash_off + i * hsize : hash_off + (i + 1) * hsize]
                )
            for slot, data in [
                (1, info_bytes),
                (3, z.read(root + "_CodeSignature/CodeResources")),
                (5, slots[5]),
            ]:
                if special >= slot:
                    assert (
                        hashfn(data).digest()[:hsize]
                        == cd[hash_off - slot * hsize : hash_off - (slot - 1) * hsize]
                    )
        p = pathlib.Path(temp)
        (p / "cms.der").write_bytes(slots[0x10000][8:])
        (p / "cd").write_bytes(slots[0])
        subprocess.run(
            [
                "openssl",
                "cms",
                "-verify",
                "-binary",
                "-inform",
                "DER",
                "-in",
                str(p / "cms.der"),
                "-content",
                str(p / "cd"),
                "-noverify",
                "-out",
                str(p / "verified"),
            ],
            capture_output=True,
            check=True,
        )
        resources = plistlib.loads(z.read(root + "_CodeSignature/CodeResources"))
        for name, entry in resources.get("files2", {}).items():
            if isinstance(entry, dict) and "hash2" in entry:
                assert entry["hash2"] == hashlib.sha256(z.read(root + name)).digest(), (
                    "Resource hash mismatch: " + name
                )
            elif isinstance(entry, dict) and "hash" in entry:
                assert entry["hash"] == hashlib.sha1(z.read(root + name)).digest(), (
                    "Resource hash mismatch: " + name
                )
        results.append(
            {
                "bundle": info["CFBundleIdentifier"],
                "provisioned_device_count": len(profile["ProvisionedDevices"]),
                "profile_expiry": str(profile["ExpirationDate"]),
                "code_page_hashes_valid": True,
                "cms_signature_valid": True,
                "special_slot_hashes_valid": True,
            }
        )
report = {
    "ipa_sha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
    "targets": results,
    "device_installation_tested": False,
    "apple_certificate_trust_and_revocation_checked": False,
}
ipa.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
