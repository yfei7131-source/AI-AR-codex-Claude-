"""Run an approved plan in a new native project and leave exact rollback evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import batch_gate as gate
from connector_target import bind

native = gate.native

BLIND_VIAS = """
const request = __CLI__.args;
const current = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!current || current.parentProjectUuid !== request.project || current.uuid !== request.doc) {
    throw new Error('Unexpected active project/PCB in official SDK session');
}
const completed = [];
for (const {net, via} of request.routes) {
    if (!via) continue;
    const pending = await eda.pcb_PrimitiveVia.create(
        net, via.x, via.y, via.drill, via.diameter, 1, via.rule, null, false
    );
    if (!pending) throw new Error('Native SDK did not create a via');
    const id = pending.getState_PrimitiveId();
    const saved = await eda.pcb_PrimitiveVia.get(id);
    if (!saved || saved.getState_Net() !== net ||
        saved.getState_ViaType() !== 1 ||
        saved.getState_DesignRuleBlindViaName() !== via.rule) {
        throw new Error('Via readback mismatch ' + id);
    }
    completed.push(id);
}
return {project: request.project, doc: request.doc, completed};
"""


def capture(output, project, board, persist=False):
    doc = native.PCB_IDS[board]
    scope = "--project", project, "--doc", doc
    if persist:
        save = native.call(output, f"{board}-save", *scope, "pcb", "save")
        gate.require(save["result"]["saved"] is True, f"{board}: save did not persist")
        native.call(output, f"{board}-reload", *scope, "doc", "reload", "--json")
        gate.load_reload(output / f"{board}-reload.json", board, project)
    raw = output / f"{board}-copper.json"
    native.call(output, f"{board}-dump", *scope, "pcb", "dump", "--include-copper", "--no-silk", "--out", str(raw))
    active, unused = gate.capture_identity(output, board)
    gate.require(active == project, f"{board}: capture drifted to another project")
    native.drc(output, f"{board}-drc", scope)
    sch = "--project", project, "--doc", gate.SCH_DOCS[board]
    capture_erc(output, board, sch)
    compiled = native.call(output, f"{board}-netlist", *sch, "sch", "netlist", "--type", "Protel2")
    netlist = output / f"{board}.net"
    shutil.copyfile(compiled["result"]["artifactPath"], netlist)
    gate.require(native.digest(netlist) == compiled["artifacts"][0]["sha256"], f"{board}: netlist artifact did not verify")


def capture_erc(output, board, scope):
    # Strict ERC completion returns exit 1 when fatal findings were reported.
    # A missing receipt, a tool failure, and non-strict results remain errors.
    label = f"{board}-erc"
    try:
        native.call(output, label, *scope, "sch", "drc", "--strict", "--json")
    except RuntimeError:
        receipt = output / f"{label}.json"
        if not receipt.stat().st_size:
            raise
        report = native.read(receipt)
        if report.get("ok") is not True or report.get("result", {}).get("strict") is not True:
            raise
    gate.strict_erc(output / f"{label}.json")


def verified_snapshot(checkpoint, names, output, name):
    source = native.archive(checkpoint)
    gate.require(name.startswith("P1-ISOLATED-"), "Require a uniquely named P1 isolated project")
    output.mkdir()
    project = native.import_snapshot(output, checkpoint, name, native.PCB_IDS[names[0]])
    copy = output / "NATIVE-REEXPORTED.epro2"
    verified = native.export(output, "snapshot-export", project, copy)
    gate.require(verified == source and gate.project_metadata(checkpoint) == gate.project_metadata(copy),
                 "Fresh native project differs from active checkpoint")
    for board in names:
        capture(output, project, board)
        gate.check_capture_records(board, gate.capture_identity(output, board)[1],
                                   verified["PCB", native.PCB_IDS[board]])
    return project, source


def call_vendor(exe, out, *args):
    output = out / "sdk-receipt.json"
    stderr = out / "sdk-stderr.txt"
    with output.open("xb") as stdout, stderr.open("xb") as err:
        result = subprocess.run([exe, "invoke", *args], timeout=60, stdout=stdout, stderr=err)
    reply = native.read(output)
    gate.require(result.returncode == 0 and reply.get("ok") is True, f"Official SDK write failed. Inspect {output.name}")
    return reply["value"]


def modify(output, project, doc, move, index):
    scope = "--project", project, "--doc", doc
    pose = output / f"move-{index:03d}-pose.json"
    native.write(pose, {k: v for k, v in move["after"].items() if k != "layer"})
    result = native.call(output, f"move-{index:03d}", *scope, "pcb", "modify", "--id", move["id"], "--patch-file", str(pose))
    target = result["mutationContext"]
    placed = result["result"]["component"]
    gate.require((target["projectUuid"], target["documentUuid"]) == (project, doc)
                 and placed["primitiveId"] == move["id"]
                 and all(gate.equal_number(placed[k], v) for k, v in move["after"].items()),
                 "Move response differed from authorized instance or placement")


def route_actions(board, config, output, project, editor, session, records):
    doc = native.PCB_IDS[board]
    scope = "--project", project, "--doc", doc
    for index, move in enumerate(config.get("moves", []), 1):
        modify(output, project, doc, move, index)
    routes = config.get("routes", [])
    raw = output / f"{board}-copper.json"
    native.call(output, "post-move-dump", *scope, "pcb", "dump", "--include-copper", "--no-silk", "--out", str(raw))
    ident, dump = gate.capture_identity(output, board)
    gate.require(ident == project, f"{board}: pre-route target drifted")
    gate.verify_route_endpoints(board, config, dump, records)
    if any(r.get("via") for r in routes):
        gate.require(editor is not None and session, "Specified blind vias require an explicit official editor executable and session")
        switch = subprocess.run(["easyeda", "--window", native.window(), "--project", project, "doc", "switch", doc], timeout=45,
                                capture_output=True)
        (output / "sdk-switch.txt").write_bytes(switch.stdout + switch.stderr)
        gate.require(switch.returncode == 0, "Could not activate the intended PCB for official SDK")
        script = output / "place-blind-vias.js"
        script.write_text(BLIND_VIAS, encoding="utf-8")
        args = {"project": project, "doc": doc, "routes": routes}
        res = call_vendor(editor, output, "--session", session, "--code-file", str(script),
                          "--args", json.dumps(args, ensure_ascii=True, separators=(",", ":")))
        gate.require((res["project"], res["doc"]) == (project, doc)
                     and len(set(res["completed"])) == sum(bool(x.get("via")) for x in routes),
                     "Missing or duplicated native blind via receipt")
    for i, r in enumerate(routes, 1):
        for j, (a, b) in enumerate(zip(r["points"], r["points"][1:]), 1):
            ans = native.call(output, f"line-{i:03d}-{j:03d}", *scope, "pcb", "track", "--net", r["net"],
                              "--layer", str(r["layer"]), "--width", str(r["width"]),
                              "--x1", str(a[0]), "--y1", str(a[1]), "--x2", str(b[0]), "--y2", str(b[1]))
            ctx = ans["mutationContext"]
            gate.require((ctx["projectUuid"], ctx["documentUuid"]) == (project, doc), "Track write target drifted")


def run(checkpoint, plan_path, output, name, editor, session, acceptance=None):
    plan = gate.parse_plan(plan_path, checkpoint)
    if acceptance is not None:
        gate.require(acceptance.get("status") == "accepted-isolated"
                     and acceptance.get("level") == plan["level"]
                     and acceptance.get("planSha256") == native.digest(plan_path)
                     and acceptance.get("checkpointSha256") == native.digest(checkpoint)
                     and acceptance.get("independentReimportVerified") is True,
                     "Replay requires a matching independently re-imported acceptance")
    boards = tuple(native.PCB_IDS) if plan["level"] == "L3" else tuple(plan["boards"])
    if any(r.get("via") for item in plan["boards"].values() for r in item.get("routes", [])):
        gate.require(editor is not None and session, "Explicit official editor executable/session required for blind-via replay")
    output.mkdir()
    before = output / "baseline"
    project, original = verified_snapshot(checkpoint, boards, before, name)
    native.write(output / "sandbox.json", {"releaseStatus": "NOT FOR FAB", "projectUuid": project,
                                          "checkpointSha256": native.digest(checkpoint),
                                          "planSha256": native.digest(plan_path)})
    try:
        if acceptance is not None:
            gate.require(all(project not in phase for phase in acceptance["projects"]),
                         "Replay project is not separate from accepted captures")
        # Prove every pose against the persisted checkpoint before the first edit.
        for board, change in plan["boards"].items():
            prec = original["PCB", native.PCB_IDS[board]]
            for move in change.get("moves", []):
                gate.require(gate.pose_matches(prec["COMPONENT", move["id"]], move["before"]),
                             f"{board}: stale placement id or pose {move['id']}")
            _, dump = gate.capture_identity(before, board)
            gate.verify_isolated_moves(board, change, dump, prec)

        for board, change in plan["boards"].items():
            actions = output / board
            actions.mkdir()
            route_actions(board, change, actions, project, editor, session, original["PCB", native.PCB_IDS[board]])
        after = output / "after"
        after.mkdir()
        for board in boards:
            capture(after, project, board, persist=True)
        result = output / "POST-BATCH.epro2"
        current = native.export(output, "batch-export", project, result)
        geometry = gate.check_archive(original, current, plan)
        for board, change in plan["boards"].items():
            prec = original["PCB", native.PCB_IDS[board]]
            post = current["PCB", native.PCB_IDS[board]]
            gate.verify_endpoints(board, change, gate.capture_identity(before, board)[1],
                                  gate.capture_identity(after, board)[1], prec, post)
            result_checks = gate.drc_gate(*(native.read(folder / f"{board}-drc.json") for folder in (before, after)), change)
            if acceptance is not None:
                gate.require(result_checks["connectionErrors"] == acceptance["boards"][board]["connectionErrors"],
                             f"{board}: replay native DRC did not reproduce accepted result")
        native.write(output / "candidate.json", {"status": "requires-acceptance", "releaseStatus": "NOT FOR FAB",
                                               "postSha256": native.digest(result), "projectUuid": project,
                                               "geometry": geometry})
    except Exception as error:
        native.write(output / "failed.json", {"status": "reject-do-not-replay", "projectUuid": project,
                                              "checkpointSha256": native.digest(checkpoint),
                                              "error": str(error), "rollback": "native_batch.py restore"})
        raise


def restore(checkpoint, baseline, out, name, boards):
    project, records = verified_snapshot(checkpoint, boards, out, name)
    for b in boards:
        restored, prior = (native.read(folder / f"{b}-drc.json") for folder in (out, baseline))
        gate.require(gate.signatures(prior) == gate.signatures(restored), f"{b}: rollback changed DRC objects")
        old_project, old = gate.capture_identity(baseline, b)
        gate.require(old_project != project, "Rollback was not isolated from the changed project")
        fresh = gate.capture_identity(out, b)[1]
        gate.require(gate.raw_terminals(old) == gate.raw_terminals(fresh), f"{b}: rollback terminal mismatch")
        gate.check_erc_net(b, baseline, out)
    native.write(out / "rollback.json", {"status": "restored-in-new-project", "projectUuid": project,
                                       "checkpointSha256": native.digest(checkpoint), "documents": len(records),
                                       "boards": list(boards)})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    modes = ap.add_subparsers(dest="mode", required=True)
    apply = modes.add_parser("apply")
    replay = modes.add_parser("replay")
    for runner in (apply, replay):
        runner.add_argument("--plan", type=Path, required=True)
        runner.add_argument("--editor", type=Path)
        runner.add_argument("--session")
    replay.add_argument("--acceptance", type=Path, required=True)
    reimport = modes.add_parser("reimport")
    rollback = modes.add_parser("restore")
    rollback.add_argument("--baseline-logs", type=Path, required=True)
    for parser in (apply, replay, reimport, rollback):
        parser.add_argument("--checkpoint", type=Path, required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--out", type=Path, required=True)
    for parser in (reimport, rollback):
        parser.add_argument("--boards", choices=tuple(native.PCB_IDS), nargs="+", default=list(native.PCB_IDS))

    for parser in (apply, replay, reimport, rollback):
        parser.add_argument("--window", help="specific v1.20.0 Connector window id")
    args = ap.parse_args()
    bind(native, args.window)
    checkpoint, out = args.checkpoint.resolve(), args.out.resolve()
    if args.mode in ("apply", "replay"):
        acceptance = native.read(args.acceptance) if args.mode == "replay" else None
        run(checkpoint, args.plan.resolve(), out, args.name, str(args.editor.resolve()) if args.editor else None,
            args.session, acceptance)
    elif args.mode == "reimport":
        verified_snapshot(checkpoint, tuple(args.boards), out, args.name)
    else:
        restore(checkpoint, args.baseline_logs.resolve(), out, args.name, tuple(args.boards))


if __name__ == "__main__":
    main()
