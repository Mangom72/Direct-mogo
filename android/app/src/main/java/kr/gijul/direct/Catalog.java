package kr.gijul.direct;

import android.net.Uri;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 띄운 창이 스스로 목록을 훑기 위한 자료.
 *
 * 새로 만들 것이 없었다 — 사이트가 이미 `data/` 로 같은 자료를 정적 파일로
 * 내보내고 있다. 색인 하나(36KB)가 학년·과목군·과목 전부를 담고, 과목 파일
 * 하나(1~69KB)가 그 과목 회차마다 문제·정답·해설의 **절대 주소**를 담는다.
 * 전체는 2.4MB지만 <b>한 번에 필요한 것은 색인 하나와 과목 하나</b>다.
 *
 * <h3>내려받기 통로를 따로 두는 까닭</h3>
 * MainActivity.download 는 EBSi 주소만 받는다. 문제지를 받는 길이 아무 데나
 * 열리지 않게 막아 둔 것이라 넓히면 안 된다. 그래서 목록은 <b>우리 사이트만</b>
 * 받는 좁은 통로를 따로 쓴다. 좁은 문 둘이 넓은 문 하나보다 낫다.
 *
 * <h3>오래된 것을 버리지 않는다</h3>
 * 자료는 하루에 한 번 바뀌므로 캐시는 하루면 넉넉하다. 다만 새로 받지 못했을
 * 때 있던 것을 버리지는 않는다 — 지하철에서 목록이 통째로 사라지는 것보다
 * 어제 것이라도 보이는 편이 낫다.
 */
class Catalog {

    private static final String TAG = "gijul.catalog";
    private static final String SITE = "https://mangom72.github.io/Direct-mogo/";
    private static final String HOST = "mangom72.github.io";
    private static final long STALE_MS = 24L * 60 * 60 * 1000;
    private static final int MAX_JSON = 4 * 1024 * 1024;
    private static final int KEEP = 24;      // 스쳐 간 문제지를 몇 장까지 들고 있을지

    /** 과목 하나 — 색인에서 온다 */
    static class Subject {
        String grade, gradeLabel, group, id, name, data;
        int count;
        String hay;                 // 검색용으로 미리 눌러 둔 글
        @Override public String toString() { return gradeLabel + " · " + name; }
    }

    /** 회차 하나 — 과목 파일에서 온다 */
    static class Paper {
        String id, title, type, date, source, problem, answer, solution;
        int year;
        /** 그 종류의 자료가 있는가 */
        String url(int kind) {
            return kind == 0 ? problem : kind == 1 ? answer : solution;
        }
    }

    static final String[] KIND = {"문제", "정답", "해설"};

    private final File api, blob;
    private List<Subject> subjects;
    private Subject lastSub;
    private List<Paper> lastPapers;

    Catalog(File cacheDir) {
        api = new File(cacheDir, "api");
        blob = new File(cacheDir, "float");
        api.mkdirs();
        blob.mkdirs();
    }

    // ── 목록 ────────────────────────────────────────────────────────────

    List<Subject> subjects() throws Exception {
        if (subjects != null) return subjects;
        JSONObject o = new JSONObject(text("data/index.json", new File(api, "index.json")));
        List<Subject> out = new ArrayList<>();
        JSONArray grades = o.getJSONArray("grades");
        for (int g = 0; g < grades.length(); g++) {
            JSONObject gr = grades.getJSONObject(g);
            JSONArray groups = gr.getJSONArray("groups");
            for (int p = 0; p < groups.length(); p++) {
                JSONObject grp = groups.getJSONObject(p);
                JSONArray subs = grp.getJSONArray("subjects");
                for (int s = 0; s < subs.length(); s++) {
                    JSONObject sj = subs.getJSONObject(s);
                    Subject t = new Subject();
                    t.grade = gr.getString("code");
                    t.gradeLabel = gr.getString("label");
                    t.group = grp.getString("name");
                    t.id = sj.getString("id");
                    t.name = sj.getString("name");
                    t.count = sj.optInt("count");
                    t.data = sj.getString("data");
                    StringBuilder h = new StringBuilder()
                            .append(t.name).append(' ').append(t.group).append(' ')
                            .append(t.gradeLabel).append(' ').append(t.grade);
                    JSONArray al = sj.optJSONArray("aliases");
                    for (int a = 0; al != null && a < al.length(); a++)
                        h.append(' ').append(al.getString(a));
                    t.hay = squash(h.toString());
                    out.add(t);
                }
            }
        }
        subjects = out;
        return out;
    }

    /**
     * 그 과목의 회차. 방금 본 것이면 다시 읽지 않는다.
     *
     * 목록에서 과목과 회차 사이를 오가는 것은 몇 걸음 안 되는 일인데, 그때마다
     * 최대 69KB 짜리 파일을 다시 읽고 다시 파싱했다. 한 벌만 들고 있으면 그
     * 왕복이 공짜가 된다 — 어차피 사람은 한 번에 한 과목을 본다.
     */
    List<Paper> papers(Subject s) throws Exception {
        if (s == lastSub && lastPapers != null) return lastPapers;
        File to = new File(api, s.grade + "-" + s.id + ".json");
        JSONObject o = new JSONObject(text(s.data, to));
        JSONArray arr = o.getJSONArray("papers");
        List<Paper> out = new ArrayList<>();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject p = arr.getJSONObject(i);
            Paper t = new Paper();
            t.id = p.optString("id");
            t.title = p.optString("title");
            t.type = p.optString("type");
            t.date = p.optString("date");
            t.source = p.optString("source");
            t.year = p.optInt("year");
            t.problem = p.optString("problem", null);
            t.answer = p.optString("answer", null);
            t.solution = p.optString("solution", null);
            out.add(t);
        }
        lastSub = s; lastPapers = out;
        return out;
    }

    // ── 검색 ────────────────────────────────────────────────────────────

    /** 띄어쓰기와 대소문자를 지운다 — '고3 생명'과 '고3생명'이 같아야 한다 */
    private static String squash(String s) {
        return s == null ? "" : s.toLowerCase(Locale.ROOT).replaceAll("\\s+", "");
    }

    /**
     * 과목 고르기.
     *
     * 줄임말을 따로 만들지 않았다 — 색인의 aliases 에 '언매'·'화작'·'생윤'이
     * 이미 들어 있다. 학년과 과목군도 함께 보므로 '고3생명'처럼 물어도 걸린다.
     */
    static List<Subject> search(List<Subject> all, String q) {
        String k = squash(q);
        if (k.isEmpty()) return all;
        List<Subject> out = new ArrayList<>();
        for (Subject s : all) if (s.hay.contains(k)) out.add(s);
        return out;
    }

    /**
     * 자료 이름에서 과목을 되짚는다.
     *
     * 페이지가 어느 과목에서 눌렀는지 함께 보내 주는 것이 정식 길이다. 다만
     * 받아둔 자료에서 띄웠거나 아직 옛 페이지를 보고 있으면 그 값이 없다.
     * 그때는 이름이 남는다 — "2026 6월 모평 생명과학Ⅰ 문제.pdf" 처럼 사람이
     * 읽는 이름에는 과목이 그대로 들어 있다.
     *
     * 겹치면 <b>긴 이름이 이긴다</b>. '생명과학Ⅰ'과 '생명과학Ⅱ'는 서로를 품지
     * 않지만 '수학'은 '수학Ⅰ'에 묻히므로, 짧은 쪽을 집으면 엉뚱한 과목으로
     * 간다. 학년까지는 이름에 없어서 고3부터 본다.
     */
    static Subject byTitle(List<Subject> all, String title) {
        String hay = squash(title);
        if (hay.isEmpty()) return null;
        Subject best = null;
        int bestLen = 0;
        for (Subject s : all) {
            String n = squash(s.name);
            if (n.isEmpty() || !hay.contains(n)) continue;
            if (best == null || n.length() > bestLen
                    || (n.length() == bestLen && rank(s) < rank(best))) {
                best = s; bestLen = n.length();
            }
        }
        return best;
    }

    private static int rank(Subject s) {          // 고3 → 고2 → 고1
        return "D300".equals(s.grade) ? 0 : "D200".equals(s.grade) ? 1 : 2;
    }

    // ── 파일 ────────────────────────────────────────────────────────────

    /**
     * 그 주소의 파일. 이미 받아 두었으면 그대로 준다.
     *
     * 앱 보관함('받아둔 자료')과는 따로 논다. 그쪽은 사람이 읽는 이름으로
     * 저장되어 있어 주소에서 이름을 되짚어야 하는데, 그 규칙이 화면 쪽에 있어
     * 여기서 다시 구현하면 어긋날 자리가 생긴다. <b>같은 주소면 같은 파일</b>
     * 하나만 믿는다.
     */
    File paper(String url) throws Exception {
        File f = new File(blob, key(url) + ext(url));
        if (f.isFile() && f.length() > 0) {
            f.setLastModified(System.currentTimeMillis());   // 방금 본 것으로 표시
            return f;
        }
        MainActivity.download(url, f);      // EBSi 주소만 받는 그 통로 그대로
        trim();
        return f;
    }

    /**
     * 오래 안 본 것부터 버린다.
     *
     * 여기 쌓이는 것은 사람이 '받아두기'로 남긴 것이 아니라, 목록에서 눌러
     * 스쳐 간 것들이다. 그냥 두면 문제지 한 장이 2~4MB라 며칠이면 수백 MB가
     * 된다. 캐시 폴더라 안드로이드가 언제든 통째로 지울 수 있으니, 여기 있는
     * 것을 잃어도 다시 받으면 그만이다.
     */
    private void trim() {
        File[] fs = blob.listFiles();
        if (fs == null || fs.length <= KEEP) return;
        java.util.Arrays.sort(fs, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));
        for (int i = KEEP; i < fs.length; i++) fs[i].delete();
    }

    private static String ext(String url) {
        String p = Uri.parse(url).getLastPathSegment();
        int i = p == null ? -1 : p.lastIndexOf('.');
        return i < 0 ? ".bin" : p.substring(i).toLowerCase(Locale.ROOT);
    }

    private static String key(String url) throws Exception {
        byte[] d = MessageDigest.getInstance("SHA-256").digest(url.getBytes(StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 10; i++) sb.append(String.format("%02x", d[i]));
        return sb.toString();
    }

    // ── 받아오기 ────────────────────────────────────────────────────────

    private String text(String path, File to) throws Exception {
        boolean fresh = to.isFile() && System.currentTimeMillis() - to.lastModified() < STALE_MS;
        if (!fresh) {
            try {
                get(SITE + path, to);
            } catch (Exception e) {
                if (!to.isFile()) throw e;
                Log.w(TAG, "새로 받지 못해 있던 것을 씁니다: " + path, e);
            }
        }
        return read(to);
    }

    /** 우리 사이트만. 색인이 엉뚱한 곳을 가리켜도 여기서 걸린다. */
    private static void get(String url, File out) throws Exception {
        HttpURLConnection c = Net.open(url, Net.SITE);
        try {
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            try (InputStream in = c.getInputStream()) {
                byte[] b = new byte[16384];
                int n;
                while ((n = in.read(b)) > 0) {
                    buf.write(b, 0, n);
                    if (buf.size() > MAX_JSON) throw new Exception("목록이 너무 큽니다");
                }
            }
            /* 다 받은 뒤에 한 번에 쓴다. 도중에 끊긴 반쪽이 캐시에 남으면
               다음 실행이 그것을 '있는 것'으로 보고 파싱에 실패한다. */
            try (OutputStream os = new FileOutputStream(out)) {
                os.write(buf.toByteArray());
            }
        } finally {
            c.disconnect();
        }
    }

    private static String read(File f) throws Exception {
        try (RandomAccessFile r = new RandomAccessFile(f, "r")) {
            byte[] b = new byte[(int) r.length()];
            r.readFully(b);
            return new String(b, StandardCharsets.UTF_8);
        }
    }
}
