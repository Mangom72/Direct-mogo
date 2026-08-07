package kr.gijul.direct;

import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.core.content.FileProvider;
import androidx.webkit.WebSettingsCompat;
import androidx.webkit.WebViewFeature;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Arrays;
import java.util.Comparator;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 기출 직행을 감싸는 WebView 앱.
 *
 * 웹만으로는 저장 위치를 정할 수 없다 — 안드로이드 크롬에 File System Access API가
 * 없고 다운로드는 브라우저가 정한 폴더로만 떨어진다. 그래서 저장만 네이티브가 맡는다.
 *
 * 받은 파일은 앱 데이터 폴더(Android/data/kr.gijul.direct/files)에 회차별 하위 폴더로
 * 들어간다. 권한을 물을 필요가 없고 앱을 지우면 같이 정리된다. 다만 안드로이드 11+
 * 에서는 다른 파일 관리자가 이 경로를 열지 못하므로, 목록·열기를 앱이 직접 제공한다.
 *
 * 페이지는 window.GijulNative 가 있을 때만 이 경로를 쓴다. 다른 OS·브라우저는 그대로다.
 */
public class MainActivity extends Activity {

    private static final String TAG = "기출직행";
    private static final String SITE = "https://mangom72.github.io/Direct-mogo/";
    static final String AUTHORITY = "kr.gijul.direct.files";

    private WebView web;
    private Updater updater;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        /* 화면을 만들기 전에 건다. 페이지가 뜨고 사용자가 자료를 누르기까지는 몇 초가
           걸리므로, 쓸어내는 일과 새로 받는 일이 겹칠 틈이 사실상 없어진다. */
        io.execute(this::sweep);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage — 내 과목·테마 저장에 필요
        s.setSupportMultipleWindows(false);
        /* WebView가 색에 손대지 못하게 확실히 막는다.
           켜두면 시스템이 다크일 때, 사용자가 '밝게'를 골라 페이지가 밝은 스타일을
           내놓아도 그 위에 강제 반전을 덧씌워 화면이 뒤집혔다. 테마는 페이지가
           GijulNative.systemDark()로 직접 판단하므로 WebView가 개입할 이유가 없다.
           기본값에 기대지 않고 옛 WebView의 FORCE_DARK_AUTO까지 명시적으로 끈다. */
        if (WebViewFeature.isFeatureSupported(WebViewFeature.ALGORITHMIC_DARKENING)) {
            WebSettingsCompat.setAlgorithmicDarkeningAllowed(s, false);
        } else if (WebViewFeature.isFeatureSupported(WebViewFeature.FORCE_DARK)) {
            WebSettingsCompat.setForceDark(s, WebSettingsCompat.FORCE_DARK_OFF);
        }
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                String s = u.toString();
                if (s.startsWith(SITE)) return false;          // 사이트 안은 그대로
                /* 여기서 하는 일은 '이 창을 다른 앱에 넘긴다'이다. 그건 사용자가 링크를
                   눌렀을 때 할 일이지, 페이지 안에 박힌 틀(iframe)이 스스로 할 일이
                   아니다. 지금 이 페이지에 틀이 없더라도, 넘길지 말지를 누가 요청했는지
                   보지 않으면 그건 판단이 아니다. 틀에서 온 것은 그냥 막는다. */
                if (!r.isForMainFrame()) return true;
                /* 문제·정답·해설은 앱 안에서 읽는다. WebView에 PDF 뷰어가 없어 예전에는
                   브라우저로 넘겼는데, 자료를 열 때마다 앱이 바뀌는 건 이 앱의 요점을
                   잃는 일이었다. 그 밖의 주소(EBSi 사이트 등)는 여전히 브라우저 몫이다. */
                if (isPaper(s)) {
                    Intent i = new Intent(MainActivity.this, PdfViewActivity.class);
                    i.putExtra(PdfViewActivity.EXTRA_URL, s);
                    i.putExtra(PdfViewActivity.EXTRA_NAME, u.getLastPathSegment());
                    open(i);
                } else {
                    open(new Intent(Intent.ACTION_VIEW, u));
                }
                return true;
            }
        });
        web.addJavascriptInterface(new Bridge(), "GijulNative");
        updater = new Updater(this);
        setContentView(web);

        if (state == null) web.loadUrl(startUrl(getIntent()));
        else web.restoreState(state);
    }

    /* 이미 떠 있는 채로 링크를 받으면 여기로 온다(launchMode=singleTask) */
    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        String go = startUrl(i);
        if (!SITE.equals(go)) web.loadUrl(go);
    }

    /**
     * 링크로 열렸으면 그 자리로, 아니면 첫 화면으로.
     *
     * intent:// 로 넘어온 경우 주소에 조각(#…)을 실을 수 없어 따로 받는다 — 그 형식은
     * '#Intent;' 를 구분자로 쓰기 때문에 페이지의 해시와 자리를 다툰다.
     */
    private String startUrl(Intent i) {
        String go = SITE;
        Uri d = i == null ? null : i.getData();
        if (d != null && d.toString().startsWith(SITE)) go = d.toString();

        String frag = i == null ? null : i.getStringExtra("gijul_frag");
        if (frag != null && frag.startsWith("#") && go.indexOf('#') < 0) go += frag;
        return go;
    }

    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    /** 시스템이 지금 야간 모드인가 */
    private boolean isNight() {
        return (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
                == Configuration.UI_MODE_NIGHT_YES;
    }

    /* uiMode를 configChanges로 잡아두었으므로 액티비티가 다시 만들어지지 않는다.
       그래서 테마가 바뀐 사실을 페이지에 직접 알려줘야 한다. */
    @Override
    public void onConfigurationChanged(Configuration c) {
        super.onConfigurationChanged(c);
        web.evaluateJavascript("window.gijulThemeChanged && window.gijulThemeChanged()", null);
    }

    /* ── 창구에서 들어오는 값 검증 ──────────────────────────────────────
     *
     * 페이지에서 넘어오는 값은 신뢰 경계를 건너온 것이다. 지금 이 창구를 부르는 게
     * 우리 페이지뿐이라 해도, 경계에서 확인하지 않으면 그건 경계가 아니다.
     */

    /** 폴더·파일 이름 한 마디. 경로를 벗어나게 만드는 글자는 전부 막는다. */
    static String safe(String s) throws Exception {
        if (s == null || s.isEmpty() || s.equals(".") || s.equals("..")
                || s.indexOf('/') >= 0 || s.indexOf('\\') >= 0 || s.indexOf('\0') >= 0)
            throw new Exception("허용되지 않는 이름입니다");
        return s;
    }

    /* ── 받기와 캐시 ────────────────────────────────────────────────────
     *
     * 두 가지를 여기 한 곳에 모았다. 예전에는 받는 코드가 세 군데에 흩어져 있었고,
     * 그 셋이 똑같은 두 가지 실수를 나눠 갖고 있었다.
     *
     *   반쪽 파일  끊긴 전송이 최종 이름으로 남았다. 다음번에 '이미 있다'로 판정돼
     *              다시 받지 않으므로, 그 회차는 영영 열리지 않았다.
     *   무한 캐시  받은 것을 지우는 코드가 아예 없었다. 문제지를 볼수록 앱 용량이
     *              늘기만 하고 줄지 않았다.
     */

    /** 한 파일의 상한. 문제지는 길어야 몇 MB라 이 위는 우리 자료가 아니다. */
    private static final long MAX_FILE = 64L * 1024 * 1024;
    /* 한 번 실행 안에서만 들고 있으면 되는 양.
       오래 두고 볼 자료는 '받아둔 자료'가 따로 맡는다 — 뷰어도 캐시보다 그쪽을
       먼저 보므로(fetch 첫 줄) 이 캐시가 비어도 오프라인으로 잃는 것이 없다.
       그래서 실행이 끝나면 통째로 버리고(sweep), 여기 한도는 한 번 실행 안에서
       불어나는 것만 막는다 — 앞뒤로 넘겨보는 데는 30회차면 넉넉하다. */
    private static final long VIEW_BUDGET = 60L * 1024 * 1024;
    private static final long SHARE_BUDGET = 20L * 1024 * 1024;

    /**
     * 임시 이름으로 받아 **다 받았을 때만** 최종 이름으로 옮긴다.
     * 중간에 무엇이 잘못되든 최종 이름 자리에는 아무것도 남지 않는다.
     */
    static void download(String url, File out) throws Exception {
        File tmp = new File(out.getParentFile(), out.getName() + ".part");
        HttpURLConnection c = (HttpURLConnection) new URL(fromEbsi(url)).openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(60000);
        c.setInstanceFollowRedirects(true);
        try {
            int code = c.getResponseCode();
            if (code != 200) throw new Exception("HTTP " + code);
            long total = 0;
            try (InputStream in = c.getInputStream(); OutputStream os = new FileOutputStream(tmp)) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) {
                    total += n;
                    if (total > MAX_FILE) throw new Exception("파일이 너무 큽니다");
                    os.write(buf, 0, n);
                }
            }
            if (out.exists() && !out.delete()) throw new Exception("옛 파일을 지우지 못했습니다");
            if (!tmp.renameTo(out)) throw new Exception("파일을 옮기지 못했습니다");
        } catch (Exception e) {
            tmp.delete();          // 반쪽은 남기지 않는다 — 남으면 그 자리가 막힌다
            throw e;
        } finally {
            c.disconnect();
        }
    }

    /** 총량이 상한을 넘으면 오래 안 본 것부터 버린다 */
    static void trim(File dir, long budget) {
        File[] fs = dir.listFiles(File::isFile);
        if (fs == null) return;
        long total = 0;
        for (File f : fs) total += f.length();
        if (total <= budget) return;
        Arrays.sort(fs, Comparator.comparingLong(File::lastModified));
        for (File f : fs) {
            if (total <= budget) break;
            long n = f.length();
            if (f.delete()) total -= n;
        }
    }

    static void trimViewCache(File cacheDir) {
        trim(new File(cacheDir, "view"), VIEW_BUDGET);
    }

    /**
     * 지난 실행이 남긴 것을 통째로 버린다.
     *
     * 캐시는 한 번 앉은 자리에서 앞뒤로 넘겨보는 동안만 쓸모가 있다. 다시 열어볼
     * 자료는 '받아둔 자료'가 맡고 뷰어도 그쪽을 먼저 보므로, 실행이 끝난 뒤까지
     * 들고 있을 이유가 없다.
     *
     * 끝날 때가 아니라 **시작할 때** 버리는 이유가 있다. 안드로이드에는 '앱이
     * 닫힌다'를 확실히 알려주는 자리가 없다 — onDestroy는 불리지 않을 수 있고
     * 프로세스는 예고 없이 죽는다. 시작할 때 버리면 반드시 돌고, 사용자가 보기에는
     * '켤 때마다 깨끗하다'로 똑같다.
     *
     * 설치 파일도 여기서 걷는다. 설치 화면으로 넘긴 뒤로는 쓸모가 없는데 지우는
     * 자리가 없어 1.8MB가 계속 남아 있었다. 옛 판이 남긴 반쪽 파일(.part)도
     * 같이 치운다 — 그건 보관함 목록에 파일 수와 용량으로만 잡히고 버튼은 생기지
     * 않아서, 보이지도 지우지도 못한 채 용량만 차지했다.
     */
    private void sweep() {
        rmrf(new File(getCacheDir(), "update"));
        rmrf(new File(getCacheDir(), "view"));
        rmrf(new File(getCacheDir(), "share"));
        File[] dirs = root().listFiles(File::isDirectory);
        if (dirs != null) for (File d : dirs) {
            File[] fs = d.listFiles(f -> f.isFile() && f.getName().endsWith(".part"));
            if (fs != null) for (File f : fs) f.delete();
        }
    }

    /** 자료를 받아올 수 있는 주소인지. EBSi 말고는 받지 않는다. */
    static String fromEbsi(String url) throws Exception {
        Uri u = Uri.parse(url == null ? "" : url);
        String host = u.getHost();
        if (!"https".equals(u.getScheme()) || host == null
                || !(host.equals("ebsi.co.kr") || host.endsWith(".ebsi.co.kr")))
            throw new Exception("허용되지 않는 주소입니다");
        return url;
    }

    /** 우리가 직접 그릴 수 있는 형식인지 — 문제·해설은 PDF, 정답은 PNG다 */
    private static boolean canDraw(String name) {
        String p = name.toLowerCase();
        return p.endsWith(".pdf") || p.endsWith(".png") || p.endsWith(".jpg");
    }

    private static boolean isPaper(String url) {
        String p = Uri.parse(url).getPath();
        return p != null && canDraw(p);
    }

    /** 저장 뿌리. 외부 앱 전용 영역이라 권한이 필요 없다. */
    private File root() {
        File f = getExternalFilesDir(null);
        return f != null ? f : getFilesDir();     // 외부 저장소가 없는 기기 대비
    }

    // ── 페이지에서 부르는 창구 ────────────────────────────────────────────

    private class Bridge {

        /** 저장할 회차. {"folder":"...","files":[{"name":"...","url":"..."}]} */
        @JavascriptInterface
        public void savePaper(String json) { io.execute(() -> save(json)); }

        /** 받아둔 자료 목록. [{folder, name, size}] — 최근 저장 순 */
        @JavascriptInterface
        public String listSaved() {
            JSONArray out = new JSONArray();
            File[] dirs = root().listFiles(File::isDirectory);
            if (dirs != null) {
                Arrays.sort(dirs, Comparator.comparingLong(File::lastModified).reversed());
                for (File d : dirs) {
                    /* 받는 중인 반쪽은 목록에 넣지 않는다 — 넣으면 파일 수와 용량에는
                       잡히는데 종류를 알 수 없어 버튼이 안 생긴다. 보이지도 지우지도
                       못하는 항목이 그렇게 생겼다. */
                    File[] fs = d.listFiles(f -> f.isFile() && !f.getName().endsWith(".part"));
                    if (fs == null) continue;
                    Arrays.sort(fs, Comparator.comparing(File::getName));
                    for (File f : fs) {
                        try {
                            out.put(new JSONObject()
                                    .put("folder", d.getName())
                                    .put("name", f.getName())
                                    .put("size", f.length()));
                        } catch (Exception ignored) { }
                    }
                }
            }
            return out.toString();
        }

        /**
         * 받아둔 파일을 앱 안에서 연다.
         *
         * 예전에는 곧바로 기기의 PDF 앱으로 넘겼다. 목록의 '문제'는 앱 안 뷰어로
         * 열리는데 받아둔 자료만 밖으로 나가서, 같은 자료를 어디서 눌렀느냐에 따라
         * 다른 데로 가는 꼴이었다. 뷰어는 이미 로컬 파일을 열 줄 알았으므로
         * (EXTRA_FILE) 그리로 보낸다. 밖으로 내보내는 길은 뷰어의 '다른 앱'에
         * 그대로 남아 있고, 회차의 '보내기'도 예전처럼 공유 시트를 띄운다.
         */
        @JavascriptInterface
        public void openSaved(String folder, String name) {
            File f;
            try { f = new File(new File(root(), safe(folder)), safe(name)); }
            catch (Exception e) { report(false, 0, "잘못된 이름입니다"); return; }
            if (!f.isFile()) { report(false, 0, "파일이 없습니다"); return; }

            if (canDraw(name)) {
                Intent i = new Intent(MainActivity.this, PdfViewActivity.class);
                i.putExtra(PdfViewActivity.EXTRA_FILE, f.getAbsolutePath());
                i.putExtra(PdfViewActivity.EXTRA_NAME, name);
                open(i);
                return;
            }
            /* 우리가 그릴 수 없는 형식이면 기기에 맡긴다 */
            try {
                Uri u = FileProvider.getUriForFile(MainActivity.this, AUTHORITY, f);
                Intent i = new Intent(Intent.ACTION_VIEW);
                i.setDataAndType(u, mimeOf(name));
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                open(i);
            } catch (Exception e) {
                Log.w(TAG, "열기 실패: " + name, e);
                report(false, 0, "열지 못했습니다 — 이 형식을 볼 앱이 없을 수 있습니다");
            }
        }

        /** 회차 하나를 지운다. folder가 비면 전부 */
        @JavascriptInterface
        public void deleteSaved(String folder) {
            int n = 0;
            File[] dirs;
            if (folder == null || folder.isEmpty()) {
                dirs = root().listFiles(File::isDirectory);
            } else {
                /* 여기가 재귀 삭제라 특히 조심한다 */
                try { dirs = new File[]{ new File(root(), safe(folder)) }; }
                catch (Exception e) { report(false, 0, "잘못된 이름입니다"); return; }
            }
            if (dirs != null) for (File d : dirs) if (rmrf(d)) n++;
            report(true, n, n + "개 회차를 지웠습니다");
        }

        /**
         * 목록의 문제·정답·해설을 뷰어로 연다.
         *
         * 주소만 넘어오면 앱이 알 수 있는 이름은 EBSi 파일명뿐이라, 제목에
         * 'g_bio1_mun_3WDW7H97.pdf'가 걸렸다. 무엇을 보고 있는지 알 수 없는
         * 이름이다. 사람이 읽는 이름은 페이지가 이미 만들고 있으므로(보내기와
         * 받아둔 자료가 쓰는 그 이름) 여기서 같이 받는다.
         *
         * 이름은 화면에 쓸 뿐 파일을 만드는 데는 쓰지 않는다 — 받아 둘 자리는
         * 여전히 주소에서 뽑는다. 그래도 경계를 건너온 값이라 확인은 한다.
         */
        @JavascriptInterface
        public void openPaper(String url, String name) {
            String title;
            try {
                fromEbsi(url);
                title = safe(name);
            } catch (Exception e) {
                Log.w(TAG, "열 수 없는 자료: " + url, e);
                report(false, 0, "열 수 없는 자료입니다");
                return;
            }
            Intent i = new Intent(MainActivity.this, PdfViewActivity.class);
            i.putExtra(PdfViewActivity.EXTRA_URL, url);
            i.putExtra(PdfViewActivity.EXTRA_NAME, title);
            open(i);
        }

        /** 파일 하나를 시스템 공유 시트로 넘긴다 */
        @JavascriptInterface
        public void shareFile(String name, String url) { io.execute(() -> share(name, url)); }

        /** 시스템 다크모드 여부. WebView의 prefers-color-scheme를 믿을 수 없어 직접 알려준다. */
        @JavascriptInterface
        public boolean systemDark() { return isNight(); }

        /** 저장 위치를 사람이 읽을 형태로 */
        @JavascriptInterface
        public String where() { return root().getAbsolutePath(); }

        /** 설치된 버전. {"code":6,"name":"1.5"} */
        @JavascriptInterface
        public String appVersion() { return updater.version(); }

        /**
         * 새 버전 확인. 실행할 때마다 부르므로 조용해야 한다 — 새 버전이 있을 때만
         * 페이지에 알린다. announce가 켜져 있으면(사용자가 직접 눌렀으면) 최신이라는
         * 사실도 알린다. 결과는 네트워크를 타므로 돌려주지 못하고 창구로 넘어간다.
         */
        @JavascriptInterface
        public void checkUpdate(boolean announce) {
            io.execute(() -> {
                String r = updater.check();
                try {
                    JSONObject o = new JSONObject(r);
                    if (!"available".equals(o.optString("state"))) {
                        /* 저장 결과 창구(gijulSaveResult)로 보내면 안 된다 — 그쪽은
                           보내기 시트를 되살리고 보관함을 다시 연다. */
                        if (announce) {
                            boolean bad = "error".equals(o.optString("state"));
                            String js = "window.gijulUpdate && window.gijulUpdate("
                                    + JSONObject.quote(bad ? "error" : "latest") + ","
                                    + JSONObject.quote(bad ? "새 버전을 확인하지 못했습니다"
                                                           : "이미 최신 버전입니다") + ")";
                            runOnUiThread(() -> web.evaluateJavascript(js, null));
                        }
                        return;
                    }
                    String js = "window.gijulUpdateFound && window.gijulUpdateFound("
                            + JSONObject.quote(r) + ")";
                    runOnUiThread(() -> web.evaluateJavascript(js, null));
                } catch (Exception ignored) { }
            });
        }

        /** 확인된 새 버전을 받아 설치 화면으로 넘긴다 */
        @JavascriptInterface
        public void installUpdate() { io.execute(() -> updater.install()); }
    }

    /** Updater가 페이지로 상태를 돌려줄 때 쓴다 */
    void eval(String js) { web.evaluateJavascript(js, null); }

    private boolean rmrf(File d) {
        if (!d.exists()) return false;
        File[] fs = d.listFiles();
        if (fs != null) for (File f : fs) { if (f.isDirectory()) rmrf(f); else f.delete(); }
        return d.delete();
    }

    private void open(Intent i) {
        runOnUiThread(() -> {
            try { startActivity(i); }
            catch (Exception e) { report(false, 0, "열 수 있는 앱이 없습니다"); }
        });
    }

    // ── 실제 저장 ────────────────────────────────────────────────────────

    private void save(String json) {
        int ok = 0, fail = 0;
        String where = "";
        try {
            JSONObject o = new JSONObject(json);
            JSONArray files = o.getJSONArray("files");
            where = safe(o.getString("folder"));
            File dir = new File(root(), where);
            if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("폴더를 만들지 못했습니다");

            for (int i = 0; i < files.length(); i++) {
                JSONObject f = files.getJSONObject(i);
                try {
                    download(f.getString("url"), new File(dir, safe(f.getString("name"))));
                    ok++;
                } catch (Exception e) {
                    Log.w(TAG, "파일 저장 실패: " + f.optString("name"), e);
                    fail++;
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "저장 실패", e);
            report(false, ok, "저장하지 못했습니다: " + e.getMessage());
            return;
        }
        report(fail == 0, ok, fail == 0
                ? "'" + where + "'에 " + ok + "개 담았습니다"
                : ok + "개 저장, " + fail + "개 실패");
    }

    private static String mimeOf(String name) {
        return name.endsWith(".png") ? "image/png"
                : name.endsWith(".pdf") ? "application/pdf" : "application/octet-stream";
    }

    /** 이미 받아둔 파일이 있으면 다시 받지 않는다 */
    private File findSaved(String name) {
        File[] dirs = root().listFiles(File::isDirectory);
        if (dirs != null) for (File d : dirs) {
            File f = new File(d, name);
            if (f.isFile()) return f;
        }
        return null;
    }

    /**
     * WebView에는 Web Share API가 없다 — navigator.share 가 아예 없어서 페이지 혼자서는
     * 공유 시트를 띄울 수 없다. 그래서 앱 안에서는 이 창구로 넘긴다.
     */
    private void share(String name, String url) {
        try {
            safe(name);
            File f = findSaved(name);
            if (f == null) {
                File dir = new File(getCacheDir(), "share");
                if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("임시 폴더를 만들지 못했습니다");
                f = new File(dir, name);
                /* 다 받은 것만 최종 이름에 있으므로, 있으면 그대로 쓴다 */
                if (!f.isFile()) { download(url, f); trim(dir, SHARE_BUDGET); }
                else f.setLastModified(System.currentTimeMillis());   // 방금 쓴 것은 늦게 버린다
            }
            Uri u = FileProvider.getUriForFile(MainActivity.this, AUTHORITY, f);
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType(mimeOf(name));
            i.putExtra(Intent.EXTRA_STREAM, u);
            i.putExtra(Intent.EXTRA_TITLE, name);
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Intent chooser = Intent.createChooser(i, name);
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            open(chooser);
            shareDone(true, "");
        } catch (Exception e) {
            Log.w(TAG, "공유 실패: " + name, e);
            shareDone(false, "공유하지 못했습니다: " + e.getMessage());
        }
    }

    private void shareDone(boolean ok, String message) {
        String js = "window.gijulShareDone && window.gijulShareDone("
                + ok + "," + JSONObject.quote(message) + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }

    /** 결과를 페이지로 돌려준다 */
    private void report(boolean ok, int count, String message) {
        String js = "window.gijulSaveResult && window.gijulSaveResult("
                + ok + "," + count + "," + JSONObject.quote(message) + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }
}
