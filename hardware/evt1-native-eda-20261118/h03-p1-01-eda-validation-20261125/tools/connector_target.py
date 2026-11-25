"""Select a verified connector before a P1 batch touches an editor document."""

import json
import subprocess
import time


def bind(native, requested=None):
    result = subprocess.run(["easyeda", "health"], capture_output=True, check=True, timeout=30)
    health = json.loads(result.stdout)
    daemon = health["found"]["raw"]
    if health["versionGate"]["cli"] != "v1.20.0" or daemon["version"] != "v1.20.0":
        raise RuntimeError("P1-01 requires CLI and daemon v1.20.0")
    compatible = [w["windowId"] for w in daemon["windows"]
                  if w.get("connectorVersion") == "1.20.0" and w.get("connectorVersionOk") is True]
    if requested is None:
        if len(compatible) != 1:
            raise RuntimeError("Select a unique registered v1.20.0 Connector with --window")
        requested = compatible[0]
    if requested not in compatible:
        raise RuntimeError("The requested window is not a registered v1.20.0 Connector")

    call_unpinned = native.call
    def call(output, label, *args, **options):
        if "--window" not in args:
            args = ("--window", requested, *args)
        else:
            if args[args.index("--window") + 1] != requested:
                raise RuntimeError("Call addressed a different Connector")
        return call_unpinned(output, label, *args, **options)

    def open_project(output, project, document):
        call(output, "open", "project", "open", "--project-uuid", project, "--allow-discard-unsaved")
        for _ in range(8):
            listing = subprocess.run(
                ["easyeda", "--window", requested, "--project", project, "doc", "ls"],
                capture_output=True, timeout=25,
            )
            if listing.returncode == 0 and document.encode() in listing.stdout:
                (output / "docs.txt").write_bytes(listing.stdout)
                return
            time.sleep(2)
        raise RuntimeError("The isolated native document tree did not become ready")

    native.window = lambda: requested
    native.call = call
    native.open_project = open_project
    return requested
