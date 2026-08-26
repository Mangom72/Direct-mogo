package kr.gijul.direct;

import static org.junit.Assert.*;
import org.junit.Test;

/**
 * 시험 시간 고르기.
 *
 * <p>이 시험이 없어서 <b>모든 과목이 30분</b>이던 것을 아무도 못 잡았다.
 * 화면에는 코드('140119')가 제목으로 뜨고 시간은 30분으로 떨어졌는데,
 * 30분은 탐구의 정상값이라 로그에도 예외에도 안 남았다.
 */
public class ExamTest {

    @Test public void 과목마다_아는_시간() {
        assertEquals(80, Exam.minutes("화법과 작문"));
        assertEquals(80, Exam.minutes("언어와 매체"));
        assertEquals(100, Exam.minutes("확률과 통계"));
        assertEquals(100, Exam.minutes("미적분"));
        assertEquals(70, Exam.minutes("영어"));
        assertEquals(30, Exam.minutes("한국사"));
        assertEquals(40, Exam.minutes("일본어Ⅰ"));
        assertEquals(40, Exam.minutes("한문Ⅰ"));
        assertEquals(30, Exam.minutes("생활과 윤리"));   // 탐구
        assertEquals(30, Exam.minutes("지구 과학Ⅰ"));    // 탐구
    }

    /** 이름을 못 받았으면 지어내지 않는다 — 여기가 그 버그의 자리다 */
    @Test public void 이름이_비면_모른다고_한다() {
        assertEquals(0, Exam.minutes(null));
        assertEquals(0, Exam.minutes(""));
        assertEquals(0, Exam.minutes("   "));
        assertEquals("아는 시간이 없으면 고를 것도 없어야 한다",
                0, Exam.choices("").length);
        assertEquals(0, Exam.choices(null).length);
    }

    /** 과목 코드가 들어오면 탐구로 오해한다 — 그래서 코드를 넣으면 안 된다 */
    @Test public void 코드는_이름이_아니다() {
        assertNotEquals("코드가 100분으로 풀리면 이름과 구별이 안 된다",
                Exam.minutes("확률과 통계"), Exam.minutes("140119"));
    }

    @Test public void 영어는_두_갈래() {
        Exam.Choice[] cs = Exam.choices("영어");
        assertEquals(2, cs.length);
        assertEquals(70, cs[0].minutes);
        assertEquals(50, cs[1].minutes);
        assertTrue(cs[0].label.contains("듣기"));
        assertTrue(cs[1].label.contains("듣기"));
    }

    @Test public void 아는_과목은_한_갈래() {
        Exam.Choice[] cs = Exam.choices("확률과 통계");
        assertEquals(1, cs.length);
        assertEquals(100, cs[0].minutes);
        assertEquals("100분", cs[0].label);
    }

    /** 앞뒤 공백이 붙어 와도 같은 과목이다 */
    @Test public void 공백은_다듬는다() {
        assertEquals(100, Exam.minutes("  미적분  "));
    }
}
