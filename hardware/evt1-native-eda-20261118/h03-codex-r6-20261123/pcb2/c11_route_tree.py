"""Build reusable exact-edge octilinear path trees for the C11 relocation survey."""

from collections import defaultdict
import heapq
from itertools import product
import math

import numpy as np
import shapely
from shapely.geometry import LineString


class RouteTree:
    DIRECTIONS=((1,0),(0,1),(1,1),(-1,1))

    def __init__(self, forbidden, goals, anchor_paths, x_range=range(13,169), y_range=range(46,411)):
        self.forbidden=forbidden
        self.anchor_paths=anchor_paths
        self.neighbors=defaultdict(list)
        x,y=np.meshgrid(tuple(x_range),tuple(y_range))
        coordinates=np.column_stack((x.ravel(),y.ravel()))
        nodes=np.array([tuple(p) for p in coordinates])
        for dx,dy in self.DIRECTIONS:
            offsets=np.column_stack((nodes[:,0]+dx,nodes[:,1]+dy))
            outline_limit=((offsets[:,0]>=min(x_range))&(offsets[:,0]<=max(x_range))&
                          (offsets[:,1]>=min(y_range))&(offsets[:,1]<=max(y_range)))
            a,b=nodes[outline_limit],offsets[outline_limit]
            edges=shapely.linestrings(np.stack((a,b),axis=1))
            ok=np.logical_not(shapely.intersects(forbidden,edges))
            for start,end in zip(a[ok],b[ok],strict=True):
                u,v=tuple(map(int,start)),tuple(map(int,end))
                self.neighbors[u].append(v)
                self.neighbors[v].append(u)
        self.cost={}
        self.parent={}
        self.goal_tag={}
        self.pad_tail={}
        q=[]
        for tag,target in goals:
            for point,path,dist in self.anchors(target):
                if dist >=self.cost.get(point,math.inf):
                    continue
                self.cost[point]=dist
                self.goal_tag[point]=tag
                self.pad_tail[point]=path
                heapq.heappush(q,(dist,point))
        while q:
            val,x=heapq.heappop(q)
            if self.cost[x]!=val:
                continue
            for y in self.neighbors[x]:
                score=val+math.dist(x,y)
                if score>=self.cost.get(y,math.inf):
                    continue
                self.cost[y]=score
                self.parent[y]=x
                self.goal_tag[y]=self.goal_tag[x]
                heapq.heappush(q,(score,y))

    def anchors(self,xy):
        xn,yn=tuple(round(z) for z in xy)
        for x,y in product(range(xn-2,xn+3),range(yn-2,yn+3)):
            node=(x,y)
            if node not in self.neighbors:
                continue
            for points in self.anchor_paths(xy,node):
                if len(points)>1 and LineString(points).intersects(self.forbidden):
                    continue
                yield node,points,total_length(points)

    def path(self,xy):
        sides=sorted((distance+self.cost[n],n,points)
                     for n,points,distance in self.anchors(xy) if n in self.cost)
        for score,n,points in sides[:4]:
            cursor=n
            path=list(points)
            while cursor in self.parent:
                cursor=self.parent[cursor]
                path.append(cursor)
            path.extend(tuple(reversed(self.pad_tail[cursor]))[1:])
            thin=[path[0]]
            for a,b,c in zip(path,path[1:],path[2:]):
                d1=b[0]-a[0],b[1]-a[1]
                d2=c[0]-b[0],c[1]-b[1]
                if abs(d1[0]*d2[1]-d1[1]*d2[0])>1e-7 or d1[0]*d2[0]+d1[1]*d2[1]<0:
                    thin.append(b)
            thin.append(path[-1])
            line=LineString(thin)
            if line.intersects(self.forbidden):
                continue
            yield score,thin,line,self.goal_tag[n]


def total_length(path):
    return sum(math.dist(x,y) for x,y in zip(path,path[1:]))
