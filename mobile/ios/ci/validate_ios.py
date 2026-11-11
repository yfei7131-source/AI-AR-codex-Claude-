"""Portable configuration checks only; this does not compile Swift or contact CI."""
from pathlib import Path
import plistlib
import re


def main():
    ios = Path(__file__).resolve().parents[1]
    info = plistlib.loads((ios / "Runner/Info.plist").read_bytes())
    for key in ("NSBluetoothAlwaysUsageDescription", "NSLocalNetworkUsageDescription",
                "NSCameraUsageDescription", "NSPhotoLibraryUsageDescription"):
        assert isinstance(info.get(key), str) and info[key].strip(), key + " missing purpose"
    assert not info.get("UIBackgroundModes"), "No background camera/audio/BLE behavior was authorized"
    assert "NSMicrophoneUsageDescription" not in info, "No native recording implementation exists"
    assert not info.get("NSBonjourServices"), "Device AP protocol uses fixed IP, not Bonjour"
    assert not info.get("NSAppTransportSecurity", {}).get("NSAllowsArbitraryLoads"), "Global ATS bypass prohibited"
    project = (ios / "Runner.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    for name in ("GlassesBleBridge.swift", "DeviceImageTransfer.swift"):
        assert (ios / "Runner" / name).is_file()
        assert name + " in Sources" in project, name + " not in Xcode sources"
    ids = re.findall(r"^\s*([A-F0-9]{24}) /\*[^\n]+?\*/ =", project, re.M)
    assert len(ids) == len(set(ids)), "Duplicate Xcode object IDs"
    app = (ios / "Runner/AppDelegate.swift").read_text(encoding="utf-8")
    assert "didInitializeImplicitFlutterEngine" in app and "GlassesBleBridge(messenger:" in app
    print("PASS iOS plist / native source registration / foreground-only configuration (not Swift compilation)")


if __name__ == "__main__":
    main()
