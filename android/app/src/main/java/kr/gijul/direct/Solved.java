package kr.gijul.direct;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * 페이지가 찍어 둔 '푼 회차'를 앱 쪽에 옮겨 적어 두는 곳.
 *
 * <h3>왜 옮겨 적는가</h3>
 * 표시는 웹뷰 안의 {@code localStorage} 에 있다. 위젯은 <b>다른 프로세스</b>라
 * 거기에 손이 닿지 않는다. 그래서 페이지가 열릴 때마다 통째로 건네받아
 * ({@code GijulNative.setSolved}) 여기에 적고, 위젯은 이것만 읽는다.
 *
 * 따라오는 결과가 하나 있고 숨길 수 없다 — <b>페이지를 한 번은 열어야</b> 위젯이
 * 최신이 된다. 웹에서만 찍은 것은 앱을 열기 전까지 위젯에 안 보인다.
 *
 * <h3>적는 꼴</h3>
 * <pre>{ "v":1,
 *   "marks": { "&lt;학년&gt;/&lt;과목&gt;/&lt;시행일&gt;/&lt;회차이름&gt;": "&lt;푼 날&gt;" },
 *   "subs":  { "&lt;학년&gt;/&lt;과목&gt;": "확률과 통계" } }</pre>
 *
 * 과목 이름을 함께 받는 것은, 열쇠에는 <b>과목 번호</b>만 있고 그것을 이름으로
 * 바꾸는 표가 페이지에만 있어서다. 위젯이 그 표를 얻으려면 자료를 받아 와야
 * 하는데, 홈 화면에 뜨는 것이 망을 타는 것은 옳지 않다. 표시에 실제로 나오는
 * 과목만 담으므로 몇 줄 되지 않는다.
 *
 * 앱이 이 값을 고치는 일은 없다 — 고치는 곳이 둘이 되면 어느 쪽이 옳은지 알
 * 수 없게 된다. 여기는 읽기만 하는 사본이다.
 */
final class Solved {

    private static final String TAG = "gijul.solved";
    private static final String PREF = "solved";
    private static final String KEY = "json";
    private static final String AT = "at";

    private Solved() { }

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
    }

    /** 페이지가 건넨 것을 그대로 적는다. 바뀐 것이 없으면 위젯을 깨우지 않는다. */
    static boolean put(Context c, String json) {
        if (json == null) return false;
        try {
            if (!new JSONObject(json).has("marks")) throw new Exception("marks 없음");
        } catch (Exception e) {
            Log.w(TAG, "표시를 읽지 못했습니다", e);
            return false;
        }
        SharedPreferences p = prefs(c);
        if (json.equals(p.getString(KEY, null))) return false;
        p.edit().putString(KEY, json).putLong(AT, System.currentTimeMillis()).apply();
        return true;
    }

    /** 한 회차 — 위젯이 그리는 데 필요한 만큼만 */
    static final class Item {
        final String grade, sub, date, title, day, name;
        Item(String grade, String sub, String date, String title, String day, String name) {
            this.grade = grade; this.sub = sub; this.date = date;
            this.title = title; this.day = day; this.name = name;
        }
        boolean gov() {
            return title.startsWith("수능") || title.contains("평가원");
        }
    }

    /** 푼 날("YYYYMMDD") → 그날 찍은 것들. 없으면 빈 map. */
    static Map<String, List<Item>> byDay(Context c) {
        Map<String, List<Item>> out = new HashMap<>();
        String json = prefs(c).getString(KEY, null);
        if (json == null) return out;
        try {
            JSONObject all = new JSONObject(json);
            JSONObject o = all.getJSONObject("marks");
            JSONObject subs = all.optJSONObject("subs");
            for (Iterator<String> it = o.keys(); it.hasNext(); ) {
                String k = it.next();
                String day = o.optString(k, "");
                if (day.length() != 8) continue;
                /* 열쇠는 학년/과목/시행일/회차이름. 회차 이름에 '/'가 들어갈 수도
                   있으니 앞의 셋만 끊고 나머지는 통째로 이름으로 본다. */
                int a = k.indexOf('/'), b = a < 0 ? -1 : k.indexOf('/', a + 1);
                int d = b < 0 ? -1 : k.indexOf('/', b + 1);
                if (d < 0) continue;
                String who = k.substring(0, b);          // 학년/과목
                Item x = new Item(k.substring(0, a), k.substring(a + 1, b),
                        k.substring(b + 1, d), k.substring(d + 1), day,
                        subs == null ? k.substring(a + 1, b) : subs.optString(who, k.substring(a + 1, b)));
                List<Item> l = out.get(day);
                if (l == null) out.put(day, l = new ArrayList<>());
                l.add(x);
            }
        } catch (Exception e) {
            Log.w(TAG, "표시를 읽지 못했습니다", e);
        }
        return out;
    }

    // ── 세는 것들 ───────────────────────────────────────────────────────

    static int on(Map<String, List<Item>> log, String day) {
        List<Item> l = log.get(day);
        return l == null ? 0 : l.size();
    }

    /** 오늘부터 거꾸로, 하루도 빠지지 않고 이어진 날수. 오늘 안 했으면 어제부터 센다. */
    static int streak(Map<String, List<Item>> log) {
        Calendar c = Calendar.getInstance();
        if (on(log, ymd(c)) == 0) c.add(Calendar.DAY_OF_MONTH, -1);
        int n = 0;
        while (on(log, ymd(c)) > 0) {
            n++;
            c.add(Calendar.DAY_OF_MONTH, -1);
            if (n > 3650) break;                 // 적힌 값이 망가져도 여기서 선다
        }
        return n;
    }

    /** 최근 것부터. 같은 날 안에서는 적힌 차례를 지킨다. */
    static List<Item> recent(Map<String, List<Item>> log, int max) {
        List<String> days = new ArrayList<>(log.keySet());
        Collections.sort(days, Collections.reverseOrder());
        List<Item> out = new ArrayList<>();
        for (String d : days) {
            for (Item x : log.get(d)) {
                out.add(x);
                if (out.size() >= max) return out;
            }
        }
        return out;
    }

    static String ymd(Calendar c) {
        return String.format("%04d%02d%02d", c.get(Calendar.YEAR),
                c.get(Calendar.MONTH) + 1, c.get(Calendar.DAY_OF_MONTH));
    }

    // ── 이름 줄이기 ─────────────────────────────────────────────────────

    /* 페이지의 SHORT_SUB 와 같은 표다. 두 곳에 있는 것이 반갑지는 않지만, 위젯이
       페이지를 열어 물어볼 수는 없다. 과목이 새로 생기는 일은 교육과정이 바뀔
       때뿐이라 서로 어긋날 틈이 넓지 않다. */
    private static final Map<String, String> SHORT = new HashMap<>();
    static {
        String[][] t = {
            {"화법과 작문","화작"},{"언어와 매체","언매"},{"확률과 통계","확통"},{"미적분","미적"},
            {"생활과 윤리","생윤"},{"윤리와 사상","윤사"},{"한국지리","한지"},{"세계지리","세지"},
            {"동아시아사","동사"},{"세계사","세사"},{"정치와 법","정법"},{"사회·문화","사문"},
            {"통합사회","통사"},{"통합과학","통과"},
            {"물리학Ⅰ","물1"},{"물리학Ⅱ","물2"},{"화학Ⅰ","화1"},{"화학Ⅱ","화2"},
            {"생명과학Ⅰ","생1"},{"생명과학Ⅱ","생2"},{"지구과학Ⅰ","지1"},{"지구과학Ⅱ","지2"},
        };
        for (String[] p : t) SHORT.put(p[0], p[1]);
    }

    static String shortSub(String name) {
        String s = SHORT.get(name);
        return s != null ? s : name;
    }

    /** 평가원은 '평'(6평·9평), 교육청은 '모'(3모·7모). 홀짝과 지역은 뗀다. */
    static String shortRound(String title) {
        String s = title
                .replaceAll("(\\d+)월\\s*모평(\\(평가원\\))?", "$1평")
                .replaceAll("(\\d+)월\\s*학평(\\([^)]*\\))?", "$1모")
                .replaceAll("\\s*\\(평가원\\)", "")
                .replaceAll("\\s*(홀수형|짝수형)", "");
        return s.replaceAll("\\s+", " ").trim();
    }

    /**
     * "26 6평 확통". 앞 두 자리는 <b>학년도</b>(시행 연도 + 1)다 — 학생이 말하는
     * '26 3모'이 2025년 3월에 치른 그것이라, 줄여 부를 때는 이쪽이 맞는다.
     */
    static String label(Item x) {
        int y;
        try { y = Integer.parseInt(x.date.substring(0, 4)) + 1; }
        catch (Exception e) { return shortSub(x.name); }
        return String.valueOf(y).substring(2) + " " + shortRound(x.title) + " " + shortSub(x.name);
    }
}
