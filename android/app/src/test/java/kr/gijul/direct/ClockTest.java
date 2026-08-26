package kr.gijul.direct;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/**
 * 시험 시간 셈. 기기 없이 확인한다.
 *
 * 타이머는 <b>틀려도 조용히 틀리는</b> 것 중에서도 고약하다 — 화면에는 숫자가
 * 멀쩡히 흐르고, 어긋난 것은 시험이 끝난 뒤에야 안다. 그때는 이미 그 한 회차를
 * 잘못 잰 것이다.
 */
public class ClockTest {

    private static final long M = 60_000L;
    private static final long T0 = 1_700_000_000_000L;

    @Test
    public void 남은_시간은_시작_시각에서_셈한다() {
        Clock c = Clock.start(100 * M, T0);
        assertEquals(100 * M, c.left(T0));
        assertEquals(72 * M, c.left(T0 + 28 * M));
        assertEquals(28 * M, c.spent(T0 + 28 * M));
        assertTrue(c.running());
        assertFalse(c.over(T0 + 99 * M));
    }

    @Test
    public void 화면이_꺼져_있던_시간도_흘렀다() {
        /* 1초마다 빼 나가면 잠든 동안이 통째로 사라진다. 시각을 들고 있으면
           얼마를 자고 왔든 답이 같다 — 그것이 이 방식을 고른 까닭이다. */
        Clock c = Clock.start(100 * M, T0);
        assertEquals(10 * M, c.left(T0 + 90 * M));
    }

    @Test
    public void 넘긴_만큼을_음수로_들고_있는다() {
        Clock c = Clock.start(100 * M, T0);
        long now = T0 + 108 * M;
        assertTrue(c.over(now));
        assertEquals(-8 * M, c.left(now));
        assertEquals(108 * M, c.spent(now));
        assertEquals(1f, c.ratio(now), 0.001f);   // 실선이 칸 밖으로 자라지 않는다
    }

    @Test
    public void 멈추면_그_자리에_선다() {
        Clock c = Clock.start(100 * M, T0).pause(T0 + 30 * M);
        assertTrue(c.paused());
        assertFalse(c.running());
        // 멈춘 뒤 한 시간이 지나도 흐른 시간은 그대로다
        assertEquals(30 * M, c.spent(T0 + 90 * M));
        assertEquals(70 * M, c.left(T0 + 90 * M));
    }

    @Test
    public void 다시_시작하면_멈춘_만큼_이어진다() {
        Clock c = Clock.start(100 * M, T0)
                .pause(T0 + 30 * M)
                .resume(T0 + 50 * M);          // 20분 멈춰 있었다
        assertTrue(c.running());
        assertEquals(30 * M, c.spent(T0 + 50 * M));
        assertEquals(40 * M, c.spent(T0 + 60 * M));
        assertEquals(60 * M, c.left(T0 + 60 * M));
    }

    @Test
    public void 여러_번_멈췄다_가도_어긋나지_않는다() {
        Clock c = Clock.start(100 * M, T0);
        long now = T0;
        for (int i = 0; i < 5; i++) {
            now += 6 * M;                       // 6분 풀고
            c = c.pause(now);
            now += 13 * M;                      // 13분 쉬고
            c = c.resume(now);
        }
        assertEquals(30 * M, c.spent(now));      // 푼 것은 30분
        assertEquals(70 * M, c.left(now));
    }

    @Test
    public void 시간을_더_줄_수_있다() {
        Clock c = Clock.start(100 * M, T0).plus(10 * M);
        assertEquals(20 * M, c.left(T0 + 90 * M));
        // 넘긴 뒤에 더해도 된다
        Clock d = Clock.start(100 * M, T0).plus(10 * M);
        assertFalse(d.over(T0 + 105 * M));
    }

    @Test
    public void 얼굴은_한_시간을_넘으면_시_분_초다() {
        assertEquals("1:12:30", Clock.face(72 * M + 30_000));
        assertEquals("12:30", Clock.face(12 * M + 30_000));
        assertEquals("0:05", Clock.face(5_000));
        assertEquals("0:00", Clock.face(0));
    }

    @Test
    public void 넘기면_첫_1초부터_보인다() {
        /* 400ms 넘긴 것을 '+0:00' 으로 적으면 안 넘긴 것처럼 보인다 */
        assertEquals("+0:01", Clock.face(-400));
        assertEquals("+2:14", Clock.face(-(2 * M + 14_000)));
        assertEquals("+1:00:00", Clock.face(-60 * M));
    }

    @Test
    public void 남긴_것과_넘긴_것을_말로_적는다() {
        // 부호로 적으면 재는 동안의 '+'(넘김)와 반대를 가리키게 된다
        assertEquals("92분 · 8분 남김", Clock.record(100 * M, 92 * M));
        assertEquals("108분 · 8분 넘김", Clock.record(100 * M, 108 * M));
        assertEquals("100분 · 딱 맞춤", Clock.record(100 * M, 100 * M));
        assertEquals("92분", Clock.record(0, 92 * M));      // 시간을 안 정하고 잰 경우
    }

    @Test
    public void 타이머가_없으면_아무것도_세지_않는다() {
        Clock c = new Clock(0, T0, 0);
        assertFalse(c.on());
        assertFalse(c.running());
        assertEquals(0, c.spent(T0 + 90 * M));
        assertEquals(0f, c.ratio(T0 + 90 * M), 0.001f);
    }

    // ── 상태 표시줄의 손톱만 한 글 ─────────────────────────────────────

    /**
     * 자리가 좁아 한 눈금만 담는다. 남은 것이 많을수록 성기게 적고,
     * 1분이 남았을 때만 초로 바뀐다.
     */
    @Test public void 짧은_글은_눈금이_바뀐다() {
        assertEquals("1:38", Clock.brief(98 * 60_000L));          // 1시간 38분
        assertEquals("2:00", Clock.brief(120 * 60_000L));
        assertEquals("59분", Clock.brief(59 * 60_000L));
        assertEquals("1분", Clock.brief(60_000L));
        assertEquals("59초", Clock.brief(59_000L));
        assertEquals("0초", Clock.brief(0L));
    }

    /** 넘긴 것은 올림이다 — 1초를 넘겨도 '+1분'이라야 넘긴 것이 보인다 */
    @Test public void 넘기면_올려서_적는다() {
        assertEquals("+1분", Clock.brief(-1_000L));
        assertEquals("+1분", Clock.brief(-60_000L));
        assertEquals("+2분", Clock.brief(-61_000L));
        assertEquals("+14분", Clock.brief(-14 * 60_000L));
    }

    /** 시가 넘어갈 때 분이 두 자리로 채워져야 자릿수가 안 흔들린다 */
    @Test public void 시_뒤의_분은_두_자리() {
        assertEquals("1:05", Clock.brief((60 + 5) * 60_000L));
        assertEquals("3:00", Clock.brief(180 * 60_000L));
    }
}
