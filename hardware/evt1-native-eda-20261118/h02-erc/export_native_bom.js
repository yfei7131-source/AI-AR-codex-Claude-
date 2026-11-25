// Run inside the official lceda-pro CLI session. Read only; the CSV is returned byte-for-byte.
const { projectId, rootPageId, board, fileType, basisOnly } = __CLI__.args;
const project = await eda.dmt_Project.getCurrentProjectInfo();
const page = await eda.dmt_Schematic.getCurrentSchematicPageInfo();
if (project?.uuid !== projectId || page?.uuid !== rootPageId) {
    throw new Error(`Unexpected export scope: project ${project?.uuid}, page ${page?.uuid}`);
}

const variants = basisOnly ? await eda.sch_ManufactureData.getAssemblyVariantsConfigs() : [];
const basis = variants.find((row) => row.value === "basis");
if (basisOnly && !basis) {
    throw new Error("Editor returned no Basis variant for the schematic");
}
const file = await eda.sch_ManufactureData.getBomFile(
    `${board}-schematic`, fileType ?? "csv", undefined, [], ["Quantity"],
    ["Designator", "Footprint", "Manufacturer Part"], undefined, basis
);
if (!file || !file.size) {
    throw new Error("Editor returned no native schematic BOM");
}

const bytes = new Uint8Array(await file.arrayBuffer());
let binary = "";
for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
}
return { projectId, rootPageId, board, name: file.name, size: bytes.length, base64: btoa(binary) };
