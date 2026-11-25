import argparse, hashlib, json, subprocess, time
from pathlib import Path
def run():
 parser=argparse.ArgumentParser()
 parser.add_argument('captures',type=Path)
 parser.add_argument('output',type=Path)
 args=parser.parse_args()
 args.output.mkdir(exist_ok=True,parents=True)
 cases=[
    ('PCB1','LS3_VREF2_EN',2,4,'R24.1','U19.7'),
    ('PCB2','opt_r_qdo1_PANEL',1,4,'J3.P6','R20.2'),
    ('PCB3','I2S_LRCLK_1V8',1,4,'U11.K4','J1.P12')
 ]
 result=[]
 for board,net,layer,width,start,end in cases:
    name=board+'-'+net
    board_path=args.captures/(board+'-copper.json')
    req=args.output/(name+'-request.json')
    report=args.output/(name+'-solve.json')
    args_json={'schemaVersion':1,'units':'mil','net':net,'layer':layer,'widthMil':width,
      'from':start,'to':end,'stepMil':1,'maxDetourMil':90,'maxStates':65000}
    req.write_text(json.dumps(args_json,indent=2)+'\n')
    t0=time.perf_counter()
    cli=['easyeda','pcb','route']
    base=['--board',str(board_path),'--from',str(req)]
    solved=subprocess.run([*cli,'solve',*base,'--out',str(report)],capture_output=True,timeout=40)
    took=time.perf_counter()-t0
    (args.output/(name+'-solve.stderr.txt')).write_bytes(solved.stderr)
    solution=json.loads(report.read_bytes()) if report.exists() else {}
    record={'board':board,'net':net,'inputsSHA256':hashlib.sha256(board_path.read_bytes()).hexdigest(),
       'solveExit':solved.returncode,'solveSeconds':round(took,3),'solveStatus':solution.get('status')}
    if solved.returncode==0:
      checked=args.output/(name+'-check.json')
      verification=subprocess.run([*cli,'check',*base,'--plan',str(report),'--out',str(checked)],capture_output=True,timeout=40)
      (args.output/(name+'-check.stderr.txt')).write_bytes(verification.stderr)
      record['checkExit']=verification.returncode
    result.append(record)
    print(record,flush=True)
 (args.output/'offline-router-benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':run()
