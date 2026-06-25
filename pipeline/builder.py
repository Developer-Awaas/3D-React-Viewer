"""
Parametric 3D builder — turns a PLAN (data) into a .glb building.
This is the DURABLE half: all the room/fixture geometry we debugged by hand,
encoded once as reusable functions. Reading a new plan = producing the JSON;
this file turns that JSON into 3D. A trained model would output the same JSON.
"""
import json, struct, math, numpy as np

# ---------- low-level geometry accumulator (opaque + glass) ----------
class Builder:
    def __init__(self):
        self.Po=[];self.No=[];self.Co=[];self.Io=[]      # opaque (vertex-coloured)
        self.Pg=[];self.Ng=[];self.Ig=[]                  # glass (one transparent material)
    def _emit(self,P,N,I,cx,cy,cz,sx,sy,sz,C=None,col=None):
        hx,hy,hz=sx/2,sy/2,sz/2
        F=[((1,0,0),[(hx,-hy,-hz),(hx,hy,-hz),(hx,hy,hz),(hx,-hy,hz)]),((-1,0,0),[(-hx,-hy,hz),(-hx,hy,hz),(-hx,hy,-hz),(-hx,-hy,-hz)]),
           ((0,1,0),[(-hx,hy,-hz),(-hx,hy,hz),(hx,hy,hz),(hx,hy,-hz)]),((0,-1,0),[(-hx,-hy,hz),(-hx,-hy,-hz),(hx,-hy,-hz),(hx,-hy,hz)]),
           ((0,0,1),[(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)]),((0,0,-1),[(hx,-hy,-hz),(-hx,-hy,-hz),(-hx,hy,-hz),(hx,hy,-hz)])]
        for n,vs in F:
            b=[]
            for (x,y,z) in vs:
                P.append((x+cx,y+cy,z+cz));N.append(n)
                if C is not None: C.append(col)
                b.append(len(P)-1)
            I.extend([b[0],b[1],b[2],b[0],b[2],b[3]])
    def box(self,cx,cy,cz,sx,sy,sz,col): self._emit(self.Po,self.No,self.Io,cx,cy,cz,sx,sy,sz,self.Co,col)
    def glass(self,cx,cy,cz,sx,sy,sz):   self._emit(self.Pg,self.Ng,self.Ig,cx,cy,cz,sx,sy,sz)
    def export(self,path):
        a=lambda x,d:np.array(x,d)
        Po,No,Co,Io=a(self.Po,np.float32),a(self.No,np.float32),a(self.Co,np.float32),a(self.Io,np.uint32)
        Pg,Ng,Ig=a(self.Pg,np.float32),a(self.Ng,np.float32),a(self.Ig,np.uint32)
        parts=[Po,No,Co,Io,Pg,Ng,Ig]; blob=b''.join(p.tobytes() for p in parts)
        while len(blob)%4:blob+=b'\x00'
        off=0;bv=[]
        for p,t in [(Po,34962),(No,34962),(Co,34962),(Io,34963),(Pg,34962),(Ng,34962),(Ig,34963)]:
            bv.append({"buffer":0,"byteOffset":off,"byteLength":p.nbytes,"target":t});off+=p.nbytes
        gz=len(self.Pg)>0
        acc=[{"bufferView":0,"componentType":5126,"count":len(Po),"type":"VEC3","min":Po.min(0).tolist(),"max":Po.max(0).tolist()},
             {"bufferView":1,"componentType":5126,"count":len(No),"type":"VEC3"},
             {"bufferView":2,"componentType":5126,"count":len(Co),"type":"VEC3"},
             {"bufferView":3,"componentType":5125,"count":len(Io),"type":"SCALAR"}]
        prims=[{"attributes":{"POSITION":0,"NORMAL":1,"COLOR_0":2},"indices":3,"material":0}]
        if gz:
            acc+=[{"bufferView":4,"componentType":5126,"count":len(Pg),"type":"VEC3","min":Pg.min(0).tolist(),"max":Pg.max(0).tolist()},
                  {"bufferView":5,"componentType":5126,"count":len(Ng),"type":"VEC3"},
                  {"bufferView":6,"componentType":5125,"count":len(Ig),"type":"SCALAR"}]
            prims.append({"attributes":{"POSITION":4,"NORMAL":5},"indices":6,"material":1})
        G={"asset":{"version":"2.0"},"buffers":[{"byteLength":len(blob)}],"bufferViews":bv,"accessors":acc,
           "materials":[{"pbrMetallicRoughness":{"baseColorFactor":[1,1,1,1],"metallicFactor":0,"roughnessFactor":0.8}},
                        {"pbrMetallicRoughness":{"baseColorFactor":[0.6,0.8,1,0.25],"metallicFactor":0,"roughnessFactor":0.1},"alphaMode":"BLEND","doubleSided":True}],
           "meshes":[{"primitives":prims}],"nodes":[{"mesh":0}],"scenes":[{"nodes":[0]}],"scene":0}
        jc=json.dumps(G).encode()
        while len(jc)%4:jc+=b' '
        ch=lambda d,t:struct.pack('<I',len(d))+t+d
        glb=b'glTF'+struct.pack('<II',2,12+8+len(jc)+8+len(blob))+ch(jc,b'JSON')+ch(blob,b'BIN\x00')
        open(path,"wb").write(glb); return len(glb)

# colours
WL=(0.90,0.88,0.83);FL=(0.78,0.70,0.60);TILE=(0.83,0.86,0.89);PIL=(0.55,0.55,0.58)
WOOD=(0.45,0.30,0.18);MAT=(0.96,0.96,0.93);DUV=(0.35,0.45,0.62);PWH=(0.98,0.98,0.96)
CUP=(0.55,0.40,0.25);WHITE=(0.97,0.97,0.97);CNTR=(0.72,0.72,0.74);MET=(0.6,0.6,0.63);DOOR=(0.60,0.45,0.30)

def _wall(b,axis,fixed,a,bb,h,t,opening=None):
    """Build a wall along `axis` ('x' or 'z') from a..bb at `fixed`, with optional opening."""
    def seg(c0,c1):
        L=c1-c0; mid=(c0+c1)/2
        if axis=='x': b.box(mid,h/2,fixed,L,h,t,WL)
        else: b.box(fixed,h/2,mid,t,h,L,WL)
    if not opening: seg(a,bb); return
    typ=opening['type']; c=opening.get('center',(a+bb)/2); w=opening.get('width',0.9)
    seg(a,c-w/2); seg(c+w/2,bb)
    if typ=='window':
        sill=opening.get('sill',0.9); wh=opening.get('wh',1.2)
        if axis=='x':
            b.box(c,sill/2,fixed,w,sill,t,WL); b.box(c,(sill+wh+h)/2,fixed,w,h-(sill+wh),t,WL); b.glass(c,sill+wh/2,fixed,w,wh,t*0.4)
        else:
            b.box(fixed,sill/2,c,t,sill,w,WL); b.box(fixed,(sill+wh+h)/2,c,t,h-(sill+wh),w,WL); b.glass(fixed,sill+wh/2,c,t*0.4,wh,w)
    elif typ=='door':
        b.box(c if axis=='x' else fixed,(2.0+h)/2,fixed if axis=='x' else c,(w if axis=='x' else t),h-2.0,(t if axis=='x' else w),WL)  # header
        if opening.get('state','closed')=='closed':
            if axis=='x': b.box(c,1.0,fixed,w,2.0,0.06,DOOR)
            else: b.box(fixed,1.0,c,0.06,2.0,w,DOOR)

def build_bedroom(b,r,H):
    ox,oz=r['origin']; W,D=r['size']; x0,x1=ox-W/2,ox+W/2; z0,z1=oz-D/2,oz+D/2
    b.box(ox,-0.05,oz,W,0.1,D,FL)
    wo=r.get('walls',{})
    for side,axis,fx,a,bb in [('back','x',z0,x0,x1),('front','x',z1,x0,x1),('left','z',x0,z0,z1),('right','z',x1,z0,z1)]:
        v=wo.get(side,'solid')
        if v=='shared': continue
        _wall(b,axis,fx,a,bb,H,0.2,v if isinstance(v,dict) else None)
    for c in [(x0,z0),(x1,z0),(x0,z1),(x1,z1)]: b.box(c[0],H/2,c[1],0.3,H,0.3,PIL)
    for f in r.get('furniture',[]):
        if f['item']=='queen_bed':
            qw,ql=1.53,2.03; bx=ox+f.get('offset',0); bz=z0+ql/2+0.05
            b.box(bx,1.0,z0+0.08,qw+0.12,1.0,0.12,WOOD); b.box(bx,0.15,bz,qw+0.12,0.3,ql+0.1,WOOD)
            b.box(bx,0.40,bz,qw,0.18,ql,MAT); b.box(bx,0.52,bz+0.25,qw,0.12,ql*0.68,DUV)
            b.box(bx-0.38,0.55,z0+0.5,0.5,0.16,0.4,PWH); b.box(bx+0.38,0.55,z0+0.5,0.5,0.16,0.4,PWH)
        elif f['item']=='wardrobe':
            ww,wd=f.get('size',[1.8,0.5]); b.box(x0+ww/2,1.0,z1-wd/2,ww,2.0,wd,CUP)

def build_toilet(b,r,H):
    ox,oz=r['origin']; W,D=r['size']; x0,x1=ox-W/2,ox+W/2; z0,z1=oz-D/2,oz+D/2
    sign=r.get('mirror',1)
    b.box(ox,0.02,oz,W,0.04,D,TILE)
    wo=r.get('walls',{})
    for side,axis,fx,a,bb in [('back','x',z0,x0,x1),('front','x',z1,x0,x1),('left','z',x0,z0,z1),('right','z',x1,z0,z1)]:
        v=wo.get(side,'solid')
        if v=='shared': continue
        _wall(b,axis,fx,a,bb,H,0.12,v if isinstance(v,dict) else None)
    # WC outer, basin toward centre (our learned convention)
    wcx=x0+0.42 if sign>0 else x1-0.42
    b.box(wcx,0.22,z0+0.40,0.40,0.40,0.50,WHITE); b.box(wcx,0.52,z0+0.14,0.46,0.55,0.20,WHITE)
    bxn=x0+0.95 if sign>0 else x1-0.95
    b.box(bxn,0.82,z0+0.30,0.55,0.12,0.40,CNTR); b.box(bxn,0.86,z0+0.30,0.42,0.10,0.30,WHITE)
    b.box(bxn,1.45,z0+0.06,0.5,0.5,0.04,(0.72,0.86,0.96))
    # one glass partition at the shower band (clear of the door at mid)
    zb=z1-0.95; gw=0.8; gx=x0+gw/2 if sign>0 else x1-gw/2
    b.glass(gx,1.0,zb,gw,2.0,0.03)

ROOMS={'bedroom':build_bedroom,'toilet':build_toilet}
def build_plan(plan, out_path):
    b=Builder(); H=plan.get('ceiling_height',2.5)
    for r in plan['rooms']:
        ROOMS[r['type']](b,r,H)
    n=b.export(out_path); print(f"built {len(plan['rooms'])} rooms -> {out_path} ({n} bytes)")

if __name__=='__main__':
    import sys
    plan=json.load(open(sys.argv[1])); build_plan(plan, sys.argv[2])
