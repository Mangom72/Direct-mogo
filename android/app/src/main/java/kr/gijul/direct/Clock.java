package kr.gijul.direct;

/**
 * 시험 시간을 재는 셈. <b>안드로이드가 없어도 돈다.</b>
 *
 * <h3>왜 셈만 따로 두는가</h3>
 * 타이머는 얼굴이 셋이다 — 뷰어의 칩, 띄운 창의 바, 나갔을 때의 알림. 셋이
 * 저마다 시간을 세면 조금씩 어긋나고, 어긋나는 것을 아무도 못 본다. 시간은
 * 여기 한 곳에서만 흐르고 셋은 이것을 읽어 그릴 뿐이다.
 *
 * <h3>시각을 들고 있지 시간을 세지 않는다</h3>
 * 1초마다 남은 시간을 <b>빼 나가면</b> 화면이 꺼져 있는 동안, 앱이 잠든 동안,
 * 프로세스가 죽었다 살아난 동안 그만큼이 통째로 사라진다. 그래서 <b>언제
 * 시작했는지</b>만 적어 두고 남은 시간은 물어볼 때마다 셈한다. 시계가 맞으면
 * 답도 맞는다.
 *
 * 일시정지는 '멈춘 만큼을 시작 시각에서 뒤로 미는 것'으로 다룬다. 그래야 멈춘
 * 채로 프로세스가 죽어도 되살아난 뒤 셈이 같다.
 */
final class Clock {

    /** 정한 시험 시간(ms). 0이면 타이머가 없는 것이다. */
    final long limit;
    /** 시작한 시각(epoch ms). 일시정지한 만큼 뒤로 밀린다. */
    final long from;
    /** 멈춰 있으면 멈춘 시각, 돌고 있으면 0 */
    final long pausedAt;

    Clock(long limit, long from, long pausedAt) {
        this.limit = limit;
        this.from = from;
        this.pausedAt = pausedAt;
    }

    static Clock start(long limit, long now) { return new Clock(limit, now, 0); }

    boolean running() { return limit > 0 && pausedAt == 0; }
    boolean paused() { return limit > 0 && pausedAt != 0; }
    boolean on() { return limit > 0; }

    /** 시작한 뒤 흐른 시간(ms). 멈춰 있으면 멈춘 그 자리에서 선다. */
    long spent(long now) {
        if (limit <= 0) return 0;
        long at = pausedAt != 0 ? pausedAt : now;
        return Math.max(0, at - from);
    }

    /** 남은 시간(ms). 넘겼으면 음수 — 넘긴 만큼을 그대로 들고 있다. */
    long left(long now) { return limit - spent(now); }

    boolean over(long now) { return on() && left(now) < 0; }

    /** 0..1. 넘겨도 1을 넘지 않는다 — 실선이 칸 밖으로 자라면 안 된다. */
    float ratio(long now) {
        if (limit <= 0) return 0f;
        return Math.max(0f, Math.min(1f, spent(now) / (float) limit));
    }

    Clock pause(long now) { return paused() ? this : new Clock(limit, from, now); }

    /** 멈춰 있던 만큼 시작 시각을 뒤로 민다. 그래야 흐른 시간이 그대로 이어진다. */
    Clock resume(long now) {
        if (!paused()) return this;
        return new Clock(limit, from + (now - pausedAt), 0);
    }

    /** 시간을 더 준다. 넘긴 뒤에도 더할 수 있다. */
    Clock plus(long ms) { return new Clock(limit + ms, from, pausedAt); }

    // ── 사람이 읽는 꼴 ──────────────────────────────────────────────────

    /**
     * 남은 시간. 한 시간이 넘으면 {@code 1:12:30}, 아니면 {@code 12:30}.
     * 넘겼으면 앞에 {@code +}를 붙이고 넘긴 만큼을 센다.
     */
    static String face(long leftMs) {
        boolean over = leftMs < 0;
        long s = Math.abs(leftMs) / 1000;
        /* 넘긴 쪽은 올림이다. 0.4초 넘긴 것을 '+0:00'으로 적으면 안 넘긴 것처럼
           보인다 — 넘겼다는 사실이 첫 1초부터 보여야 한다. */
        if (over && Math.abs(leftMs) % 1000 != 0) s++;
        long h = s / 3600, m = (s % 3600) / 60, ss = s % 60;
        String t = h > 0 ? String.format("%d:%02d:%02d", h, m, ss)
                         : String.format("%d:%02d", m, ss);
        return over ? "+" + t : t;
    }

    /**
     * 끝낸 뒤 표시에 남길 한 줄. 소요 시간과, 고사 시간에서 그것을 뺀 값을 함께.
     *
     * 부호로 적지 않는다. 재는 동안에는 {@code +}가 '넘겼다'는 뜻인데, 여기서
     * (고사 − 소요)의 양수는 '남겼다'는 뜻이라 <b>같은 기호가 반대를 가리키게
     * 된다.</b> 말로 적으면 그럴 일이 없다.
     */
    static String record(long limitMs, long spentMs) {
        long spentMin = Math.round(spentMs / 60000.0);
        long diffMin = Math.round((limitMs - spentMs) / 60000.0);
        if (limitMs <= 0) return spentMin + "분";
        if (diffMin > 0) return spentMin + "분 · " + diffMin + "분 남김";
        if (diffMin < 0) return spentMin + "분 · " + (-diffMin) + "분 넘김";
        return spentMin + "분 · 딱 맞춤";
    }

    /**
     * 상태 표시줄에 붙는 아주 짧은 글. 자리가 손톱만 해서 <b>한 눈금만</b> 담는다.
     *
     * <p>초까지 흐르면 눈이 자꾸 끌리는데, 한 시간 넘게 푸는 동안 초는 알 필요가
     * 없다. 그래서 남은 것이 많을수록 성기게 적고, <b>1분이 남았을 때만 초로
     * 바뀐다</b> — 그때는 초가 유일하게 중요한 값이다.
     */
    static String brief(long leftMs) {
        if (leftMs < 0) {
            long over = (-leftMs + 59_999) / 60_000;        // 넘긴 것은 올림
            return "+" + over + "분";
        }
        long s = leftMs / 1000;
        if (s >= 3600) return (s / 3600) + ":" + two((s % 3600) / 60);
        if (s >= 60) return (s / 60) + "분";
        return s + "초";
    }

    private static String two(long v) { return v < 10 ? "0" + v : String.valueOf(v); }
}
