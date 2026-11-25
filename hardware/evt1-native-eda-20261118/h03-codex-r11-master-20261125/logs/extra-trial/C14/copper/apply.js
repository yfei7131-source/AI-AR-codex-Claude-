
const a=__CLI__.args, written=[];
const confirm=async()=>{const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(d.uuid!==a.doc||d.parentProjectUuid!==a.project)throw Error('Editor target changed');};
await confirm();
for (const r of a.routes){
 await confirm();
 if(r.via){
  const v=r.via;
  const o=await eda.pcb_PrimitiveVia.create(r.net,v.x,v.y,v.drill,v.diameter,1,v.rule,null,false);
  const id=o.getState_PrimitiveId();const check=await eda.pcb_PrimitiveVia.get(id);
  if(!check || check.getState_DesignRuleBlindViaName()!==v.rule || check.getState_ViaType()!==1 || check.getState_Net()!==r.net)throw Error('Blind via readback failed '+id);
  written.push({kind:'VIA',id,net:r.net,rule:v.rule});
 }
 for(let i=1;i<r.points.length;i++){
  let [x,y]=r.points[i-1], [u,v]=r.points[i];
  const o=await eda.pcb_PrimitiveLine.create(r.net,r.layer,x,y,u,v,r.width,false);
  if(!o||o.getState_Net()!==r.net || o.getState_LineWidth()!==r.width) throw Error('Line create failed');
  written.push({kind:'LINE',id:o.getState_PrimitiveId(),net:r.net});
 }
}
await confirm();return {doc:a.doc,project:a.project,written};
