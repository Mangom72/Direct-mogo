package kr.gijul.direct;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

/**
 * 기기를 켜지 않고 확인할 수 있는 것들.
 *
 * <h3>왜 이 넷인가</h3>
 * 앱에서 <b>틀려도 조용히 틀리는</b> 자리를 골랐다. 화면에서는 아무 일도 안
 * 일어나고 오류도 안 나는데 결과만 어긋나는 것들이다.
 *
 * <ul>
 *   <li>허용 목록 — 한 글자 차이로 남의 서버를 받아들인다</li>
 *   <li>이름 거르기 — 우리 폴더 밖에 파일을 쓴다</li>
 *   <li>열쇠 가르기 — 위젯 여섯이 전부 이것을 거친다</li>
 *   <li>연속 일수 — 잔디밭과 이번 주가 이 셈을 쓴다</li>
 * </ul>
 *
 * 위젯이 실제로 그려지는 모습이나 SAF·웹뷰는 여기서 못 본다. 그쪽은 기기가
 * 있어야 하고, 이 시험은 그것을 대신하지 않는다.
 */
public class GuardTest {

    // ── 어디서 받아도 되는가 ────────────────────────────────────────────

    @Test
    public void ebsi만_받는다() {
        assertTrue(Net.EBSI.ok("wdown.ebsi.co.kr"));
        assertTrue(Net.EBSI.ok("www.ebsi.co.kr"));
        assertTrue(Net.EBSI.ok("ebsi.co.kr"));

        /* 점이 빠지면 이것들이 통과한다. endsWith("ebsi.co.kr") 로 적었다면
           아래 둘이 전부 참이 되고, 아무 데서도 티가 나지 않는다. */
        assertFalse(Net.EBSI.ok("notebsi.co.kr"));
        assertFalse(Net.EBSI.ok("evil-ebsi.co.kr"));
        assertFalse(Net.EBSI.ok("ebsi.co.kr.example.com"));
        assertFalse(Net.EBSI.ok("ebsi.co.kr.kr"));
        assertFalse(Net.EBSI.ok(null));
        assertFalse(Net.EBSI.ok(""));
    }

    @Test
    public void 우리_사이트만_받는다() {
        assertTrue(Net.SITE.ok("mangom72.github.io"));
        assertFalse(Net.SITE.ok("mangom72.github.io.example.com"));
        assertFalse(Net.SITE.ok("evil.mangom72.github.io"));
        assertFalse(Net.SITE.ok("github.io"));
        assertFalse(Net.SITE.ok(null));
    }

    @Test
    public void 릴리스_자산이_넘어가는_자리를_받는다() {
        assertTrue(Net.RELEASE.ok("github.com"));
        assertTrue(Net.RELEASE.ok("mangom72.github.io"));
        /* 깃허브가 조용히 바꾸는 자리다. 예전에는 objects.…, 지금은 release-assets.…
           둘 다 받아야 한다 — 하나를 못박으면 이름이 바뀐 날 모두의 갱신이 멈춘다. */
        assertTrue(Net.RELEASE.ok("objects.githubusercontent.com"));
        assertTrue(Net.RELEASE.ok("release-assets.githubusercontent.com"));

        assertFalse(Net.RELEASE.ok("githubusercontent.com.example.com"));
        assertFalse(Net.RELEASE.ok("evilgithubusercontent.com"));
        assertFalse(Net.RELEASE.ok("raw.github.com.example.com"));
        assertFalse(Net.RELEASE.ok(null));
    }

    // ── 파일 이름 ──────────────────────────────────────────────────────

    @Test
    public void 자리를_벗어나는_이름을_막는다() throws Exception {
        assertEquals("수능.pdf", Names.safe("수능.pdf"));
        assertEquals("2025 수능 확률과 통계", Names.safe("2025 수능 확률과 통계"));

        for (String bad : new String[]{
                null, "", ".", "..",
                "../비밀", "폴더/파일", "폴더\\파일", "이름\0잘림",
                "/절대경로", "..\\위로"}) {
            try {
                Names.safe(bad);
                fail("막았어야 합니다: " + bad);
            } catch (Exception expected) { }
        }
    }

    @Test
    public void 날짜를_짧게_적는다() {
        assertEquals("8.24", Names.mmdd("20260824"));
        assertEquals("11.3", Names.mmdd("20261103"));
        assertEquals("1.1", Names.mmdd("20260101"));
        assertEquals("", Names.mmdd("짧음"));
        assertEquals("", Names.mmdd(""));
    }

    // ── 수능 날 ────────────────────────────────────────────────────────

    @Test
    public void 수능은_11월_13일에서_19일_사이의_목요일이다() {
        /* 화면과 같은 규칙이어야 한다. 어긋나면 D-day 가 두 곳에서 갈린다 —
           tests/test_twins.py 가 창의 경계를, 여기서는 셈한 날 자체를 본다. */
        int[][] want = {
                {2016, 17}, {2017, 16}, {2018, 15}, {2019, 14}, {2020, 19},
                {2021, 18}, {2022, 17}, {2023, 16}, {2024, 14}, {2025, 13},
                {2026, 19}, {2027, 18},
        };
        for (int[] w : want) {
            java.util.Calendar c = java.util.Calendar.getInstance();
            c.clear();
            c.set(w[0], java.util.Calendar.NOVEMBER, w[1]);
            assertEquals("(" + w[0] + "년) 목요일이 아닙니다",
                    java.util.Calendar.THURSDAY, c.get(java.util.Calendar.DAY_OF_WEEK));
            assertTrue("(" + w[0] + "년) 11월 13~19일 밖입니다", w[1] >= 13 && w[1] <= 19);
        }
    }

    // ── 적어 둔 것을 읽기 ───────────────────────────────────────────────

    private static String log(String... pairs) {
        StringBuilder b = new StringBuilder("{\"v\":1,\"marks\":{");
        for (int i = 0; i < pairs.length; i += 2) {
            if (i > 0) b.append(',');
            b.append(org.json.JSONObject.quote(pairs[i])).append(':')
                    .append(org.json.JSONObject.quote(pairs[i + 1]));
        }
        return b.append("},\"subs\":{\"D300/158\":\"확률과 통계\"}}").toString();
    }

    @Test
    public void 열쇠를_학년_과목_시행일_회차이름으로_가른다() {
        java.util.Map<String, java.util.List<Solved.Item>> out =
                Solved.byDay(log("D300/158/20251113/수능", "20260824"));
        assertEquals(1, out.size());
        Solved.Item x = out.get("20260824").get(0);
        assertEquals("D300", x.grade);
        assertEquals("158", x.sub);
        assertEquals("20251113", x.date);
        assertEquals("수능", x.title);
        assertEquals("확률과 통계", x.name);       // subs 에서 이름을 찾아온다
        assertTrue(x.gov());
    }

    @Test
    public void 회차_이름에_구분자가_들어가도_끊지_않는다() {
        /* 앞의 셋만 끊고 나머지는 통째로 이름이다. 넷으로 잘라 버리면
           '10월 학평(서울/경기)' 같은 이름이 조용히 잘린다. */
        java.util.Map<String, java.util.List<Solved.Item>> out =
                Solved.byDay(log("D300/158/20251012/10월 학평(서울/경기)", "20260824"));
        assertEquals("10월 학평(서울/경기)", out.get("20260824").get(0).title);
    }

    @Test
    public void 망가진_줄은_버리고_성한_줄은_남긴다() {
        java.util.Map<String, java.util.List<Solved.Item>> out = Solved.byDay(log(
                "D300/158/20251113/수능", "20260824",     // 성함
                "열쇠가아님", "20260824",                  // 구분자가 없다
                "D300/158", "20260824",                   // 셋을 못 채웠다
                "D300/158/20250401/4월 학평", "짧음"));    // 날짜가 여덟 자가 아니다
        assertEquals(1, out.get("20260824").size());
        assertEquals("수능", out.get("20260824").get(0).title);
    }

    @Test
    public void 비었거나_읽을_수_없으면_빈_손으로_돌아온다() {
        assertTrue(Solved.byDay((String) null).isEmpty());
        assertTrue(Solved.byDay("").isEmpty());
        assertTrue(Solved.byDay("이건 JSON 이 아닙니다").isEmpty());
        assertTrue(Solved.byDay("{\"v\":1}").isEmpty());        // marks 가 없다
    }

    @Test
    public void 평가원과_교육청을_제목으로_가른다() {
        // kindOf() 와 같은 규칙이어야 한다 — 제목이 '수능'으로 시작하거나 '평가원'을 담는다
        assertTrue(item("수능").gov());
        assertTrue(item("수능 홀수형").gov());
        assertTrue(item("6월 모평(평가원)").gov());
        assertFalse(item("10월 학평(서울)").gov());
        assertFalse(item("3월 학평(서울)").gov());
    }

    private static Solved.Item item(String title) {
        return Solved.byDay(log("D300/158/20251113/" + title, "20260824"))
                .get("20260824").get(0);
    }

    // ── 며칠째 이어지는가 ───────────────────────────────────────────────

    @Test
    public void 오늘부터_거꾸로_빠짐없이_이어진_날을_센다() {
        assertEquals(3, streakOf(0, 1, 2));         // 오늘·어제·그제
        assertEquals(0, streakOf(2, 3));            // 어제가 비었으면 0
        assertEquals(2, streakOf(1, 2, 4));         // 어제·그제만 (오늘 안 했다)
        assertEquals(1, streakOf(0));
        assertEquals(0, streakOf());
    }

    /** {@code back} 일 전마다 하나씩 찍어 둔 기록을 만들어 연속 일수를 센다 */
    private static int streakOf(int... back) {
        String[] pairs = new String[back.length * 2];
        for (int i = 0; i < back.length; i++) {
            java.util.Calendar c = java.util.Calendar.getInstance();
            c.add(java.util.Calendar.DAY_OF_MONTH, -back[i]);
            pairs[i * 2] = "D300/158/2025111" + i + "/회차" + i;
            pairs[i * 2 + 1] = Solved.ymd(c);
        }
        return Solved.streak(Solved.byDay(log(pairs)));
    }
}
