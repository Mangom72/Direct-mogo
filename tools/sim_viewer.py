"""PdfViewActivity의 렌더링 상태 기계를 그대로 옮겨 시나리오를 돌린다.
목적: 어떤 쪽이 밑그림(280px)에 머무는지, 왜 그런지를 코드 경로로 확인."""

MIN_ZOOM, MAX_RENDER_ZOOM, HARD_MAX, THUMB = 0.5, 2.0, 3000, 280
STAGE_H, LIST_W = 900, 2000
PAGE_H_AT_1 = int(LIST_W * 1.41)      # 한 쪽의 높이(리스트 좌표)

class V:
    """PdfViewActivity"""
    def __init__(self, n):
        self.n=n; self.zoom=1.0; self.renderW=0
        self.visFirst=0; self.visLast=0
        self.sharp={}; self.base={}; self.queued=set()
        self.q=[]                      # io 단일 스레드 FIFO
        self.listH=STAGE_H
        self.holders={}                # page -> shownW  (붙어 있는 것만)
        self.log=[]

    # ── 배치 ────────────────────────────────────────────────
    def layout(self):
        """리스트 높이만큼 항목을 붙인다. 새로 붙는 쪽마다 show()."""
        per = PAGE_H_AT_1
        last = min(self.n-1, (self.listH-1)//per)
        now = set(range(0, last+1))
        for p in list(self.holders):
            if p not in now: del self.holders[p]        # 재활용 → clear()
        for p in sorted(now):
            if p not in self.holders:
                self.holders[p]=0                        # clear(): shownW=0
                self.show(p)

    def updateVisible(self):
        per = PAGE_H_AT_1
        self.visFirst = 0
        self.visLast = min(self.n-1, (self.listH-1)//per)

    # ── 코드 그대로 ─────────────────────────────────────────
    def wantW(self):
        if self.renderW<=0: return 0
        z=max(MIN_ZOOM, min(self.zoom, MAX_RENDER_ZOOM))
        want=min(round(self.renderW*z), HARD_MAX)
        afford=10**9
        return max(round(self.renderW*MIN_ZOOM), min(want, afford))

    def show(self, i):
        self.holders[i]=0
        self.renderW = LIST_W
        if i < self.visFirst: self.visFirst=i
        if i > self.visLast:  self.visLast=i
        s=self.sharp.get(i)
        if s is not None and s >= self.wantW()*0.95:
            self.holders[i]=s
        else:
            if i in self.base: self.holders[i]=self.base[i]
            self.askSharp(i)

    def askSharp(self, i):
        if i<0 or i>=self.n: return
        self.q.append(("sharp", i))

    def resharp(self):
        self.updateVisible()
        for i in range(self.visFirst-1, self.visLast+2): self.askSharp(i)

    def drawThumbs(self):
        for i in range(self.n): self.q.append(("thumb", i))

    def post(self, i, w):
        if i in self.holders and w >= self.holders[i]:
            self.holders[i]=w

    def drain(self):
        while self.q:
            kind, i = self.q.pop(0)
            if kind=="thumb":
                if i in self.base: continue
                self.base[i]=THUMB; self.post(i, THUMB)
            else:
                try:
                    if i < self.visFirst-1 or i > self.visLast+1:
                        self.log.append(f"    렌더 {i} → 화면 밖으로 판정, 버림 "
                                        f"(범위 {self.visFirst}..{self.visLast})")
                        continue
                    w=self.wantW()
                    if w<=0: continue
                    b=self.sharp.get(i)
                    if b is not None and b >= w*0.95:
                        self.post(i, b); continue
                    self.sharp[i]=w; self.post(i,w)
                finally:
                    self.queued.discard(i)

    def report(self, title):
        self.updateVisible()
        need=self.wantW()
        print(f"\n── {title}  (배율 {self.zoom:.0%}, 필요 {need}px)")
        for p in sorted(self.holders):
            w=self.holders[p]
            ok = w>=need*0.95
            print(f"   {p}쪽: 표시 {w}px  {'선명' if ok else '★ 밑그림/부족 ★'}")
        for l in self.log: print(l)
        self.log.clear()

# ── 시나리오: 4쪽 문서 ────────────────────────────────────────
v=V(4)
v.listH=STAGE_H
v.layout(); v.q.append(("noop",0)); v.q.pop()
v.renderW=LIST_W; v.resharp(); v.drawThumbs(); v.drain()
v.report("1. 열었을 때")

# 축소 50%
v.zoom=0.5
v.listH=round(STAGE_H/0.5)          # onScaleBegin: MIN_ZOOM 기준으로 미리 키움
v.layout()                           # 배치가 먼저 돈다
v.resharp()                          # resharp는 list.post로 그 뒤에
v.drain()
v.report("2. 50%로 축소한 뒤 (고친 로직)")
