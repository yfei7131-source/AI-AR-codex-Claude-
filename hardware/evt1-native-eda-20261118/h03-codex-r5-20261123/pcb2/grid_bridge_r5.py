"""Search bounded single-layer decoupling supply and return detours in PCB2."""
import argparse
from collections import defaultdict
import heapq
import json
import math
from itertools import combinations,product
from pathlib import Path

import plan_bridge_r5 as plan

CANDIDATES = [
    ("C9.1","C12.1"),("C9.1","C8.1"),("C9.1","C5.1"),
    ("C5.1","C4.1"),("C5.1","C12.1"),("C5.1","R8.1"),("C31.1","C12.1"),
    ("C31.1","C4.1"),("C11.1","C6.1"),("C11.2","R9.2"),("C11.2","C6.2"),
]
STEP=2.0
WIDTH=3.6
DIRECTIONS=list(product((-1,0,1),repeat=2))
DIRECTIONS.remove((0,0))
MAX_NODES=19000


def candidates(package):
    _,_,_,all_shapes,pads,edges,airwires=plan.load_baseline(package)
    results=[]
    for source,target in CANDIDATES:
        start,layer,p= pads[source]
        goal,_,q=pads[target]
        assert p.net==q.net and p.layers==q.layers and layer in (1,2)
        assert max(p.ref in airwires,q.ref in airwires)
        scoped=[c for c in all_shapes if layer in c.layers]
        # Find the existing same-net islands, including vias' connectivity on other layers.
        net_shapes=[c for c in all_shapes if c.net==p.net]
        parents={c.ref:c.ref for c in net_shapes}
        def root(ref):
            while parents[ref]!=ref:
                ref=parents[ref]
            return ref
        for a,b in combinations(net_shapes,2):
            if a.layers&b.layers and plan.close(a,b,.2) and plan.pair_gap(a,b)<=.2:
                parents[root(a.ref)]=root(b.ref)
        if root(p.ref)==root(q.ref):
            report={"from":source,"to":target,"status":"already same copper island"}
            results.append(report)
            print(report,flush=True)
            continue

        touched={root(p.ref),root(q.ref)}
        width=WIDTH
        # A short rail tie is desirable; discard long serpentine candidates.
        max_cost=math.dist(start,goal)*1.6 + 30
        bound=(max(0,min(start[0],goal[0])-28), min(start[1],goal[1])-42,
              min(181.1024,max(start[0],goal[0])+28), max(start[1],goal[1])+42)
        def keys(box,pad=0):
            return product(range(math.floor((box[0]-pad)/10),math.floor((box[2]+pad)/10)+1),
                           range(math.floor((box[1]-pad)/10),math.floor((box[3]+pad)/10)+1))
        spatial=defaultdict(dict)
        for c in scoped:
            for key in keys(c.bbox,14):
                spatial[key][c.ref]=c
        blocked={}
        def try_edge(a,b):
            ordered=tuple(sorted((a,b)))
            if ordered in blocked:
                return blocked[ordered]
            def evaluate():
                candidate=plan.capsule("track","",p.net,p.layers,a,b,width)
                if min(plan.seg_seg_dist(*a,*b,*x,*y) for x,y in edges)-width/2 < 12:
                    return False
                for obstacle in {k:c for key in keys(candidate.bbox) for k,c in spatial[key].items()}.values():
                    if obstacle.ref in (p.ref,q.ref):
                        continue
                    gap=plan.pair_gap(candidate,obstacle)
                    if obstacle.net==p.net:
                        if obstacle.kind=="track" and plan.collinear_overlap(*a,*b,*obstacle.segment[0],*obstacle.segment[1]):
                            return False
                        if gap<=.25 and root(obstacle.ref) not in touched:
                            return False
                        continue
                    requirement=plan.FOREIGN_COPPER
                    if obstacle.kind=="track":
                        requirement=max(requirement,3.08*max(width,obstacle.radius*2)-width/2-obstacle.radius,
                                        11.8 if {p.net,obstacle.net}&(plan.SENSITIVE|plan.SENSITIVE_3W_NETS) else 0)
                    if gap<requirement:
                        return False
                return True
            passed=evaluate()
            blocked[ordered]=passed
            return passed

        def lead(s,t):
            x,y=map(lambda r:round(r,4),s)
            u,v=map(lambda r:round(r,4),t)
            d=min(abs(u-x),abs(v-y))
            a,b=math.copysign(d,u-x),math.copysign(d,v-y)
            for corner in ((x+a,y+b),(u-a,v-b)):
                path=list(dict.fromkeys((s,tuple(round(e,4) for e in corner),t)))
                if all(try_edge(m,n) for m,n in zip(path,path[1:])):
                    return path
            return None

        near_range=range(-3,4)
        def anchors(point):
            origin=tuple(round(x/STEP) for x in point)
            for i,j in product(near_range,repeat=2):
                node=((origin[0]+i)*STEP,(origin[1]+j)*STEP)
                if lead(point,node):
                    yield node,lead(point,node)
        starts=dict(anchors(start))
        goals=dict(anchors(goal))
        queue=[]
        parents_node={}
        g={}
        for node,lead_in in starts.items():
            g[node]=sum(math.dist(a,b) for a,b in zip(lead_in,lead_in[1:]))
            heapq.heappush(queue,(g[node]+math.dist(node,goal),g[node],node))
        visits=0
        while queue and visits<MAX_NODES:
            estimated,cost,n=heapq.heappop(queue)
            if cost!=g[n]:
                continue
            if estimated>max_cost:
                break
            visits+=1
            if n in goals:
                current=n
                sequence=[n]
                while current in parents_node:
                    current=parents_node[current]
                    sequence.append(current)
                points=starts[current][:-1]+list(reversed(sequence))+list(reversed(goals[n]))[1:]
                merged=[points[0]]
                for idx,point in enumerate(points[1:-1],1):
                    before,after=points[idx-1],points[idx+1]
                    vector1=(point[0]-before[0],point[1]-before[1])
                    vector2=(after[0]-point[0],after[1]-point[1])
                    cross=vector1[0]*vector2[1]-vector1[1]*vector2[0]
                    if abs(cross)>1e-7 or sum(a*b for a,b in zip(vector1,vector2))<0:
                        merged.append(point)
                merged.append(points[-1])
                assert all(try_edge(u,v) for u,v in zip(merged,merged[1:]))
                results.append({"from":source,"to":target,"status":"geometry candidate","points":merged,
                                "layer":layer,"net":p.net,"width_mil":WIDTH,"airwires":(p.ref in airwires,q.ref in airwires),
                                "length_mil":round(sum(math.dist(a,b) for a,b in zip(merged,merged[1:])),4),
                                "visits":visits})
                break
            for a,b in DIRECTIONS:
                m=(n[0]+a*STEP,n[1]+b*STEP)
                new=cost+math.dist(n,m)
                if (bound[0] <= m[0] <= bound[2] and bound[1] <= m[1] <= bound[3]
                        and new<g.get(m,float("inf")) and try_edge(n,m)):
                    g[m]=new
                    parents_node[m]=n
                    heapq.heappush(queue,(new+math.dist(m,goal),new,m))
        else:
            results.append({"from":source,"to":target,"status":"no bounded route","visits":visits})
            print(results[-1],flush=True)
            continue
        if not results or results[-1]["from"]!=source or results[-1]["to"]!=target:
            results.append({"from":source,"to":target,"status":"no bounded route","visits":visits})
        print(results[-1],flush=True)
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("package",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    plan.load_inherited_geometry(args.package)
    output=candidates(args.package)
    args.output.write_text(json.dumps(output,indent=2)+"\n",encoding="utf8")


if __name__=="__main__":
    main()
