"""머문 시간 기준을 두 방식으로 돌려 비교한다.
시나리오: 한 화면에 두 쪽이 걸치도록 천천히 내려간다 (14·15 → 15·16 → 16·17 …)"""
DWELL=200; FRAME=16

def old_way(windows):
    """맨 위 쪽이 안 바뀐 시간이 기준. 바뀌면 시계를 되감는다."""
    fired=[]; top=None; held=0
    for (f,l) in windows:
        if f!=top: top=f; held=0
        held+=FRAME
        if held>=DWELL and f not in fired: fired.append(f); held=0
    return fired

def new_way(windows, n=20):
    """쪽마다 화면에 머문 시간의 합. 화면을 벗어나면 0."""
    seen=[0]*n; fired=[]
    for (f,l) in windows:
        for i in range(n):
            if i<f or i>l: seen[i]=0; continue
            if seen[i]<0: continue
            seen[i]+=FRAME
            if seen[i]>=DWELL: seen[i]=-1; fired.append(i)
    return fired

# 14·15가 180ms, 15·16이 180ms — 어느 쪽도 단독으로는 200ms를 못 넘긴다
w=[(14,15)]*11 + [(15,16)]*11
print("창:  14·15 176ms → 15·16 176ms   (각 창은 기준 미달, 15만 352ms 연속)")
print("  예전 기준 →", old_way(w) or "아무것도 안 그림")
print("  지금 기준 →", new_way(w))

# 빠르게 스쳐 지나가는 경우엔 걸리면 안 된다
w2=[(i,i+1) for i in range(0,12) for _ in range(3)]     # 쪽마다 48ms
print("\n창:  쪽마다 48ms씩 스쳐 지나감")
print("  지금 기준 →", new_way(w2) or "아무것도 안 그림 (의도대로)")
