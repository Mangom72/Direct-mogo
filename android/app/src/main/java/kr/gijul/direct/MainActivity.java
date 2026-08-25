package kr.gijul.direct;

import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

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
        /* 창구(GijulNative)가 붙어 있는 웹뷰다. 여는 것은 우리 사이트뿐이고 그
           밖은 shouldOverrideUrlLoading 이 넘기지만, 열 수 있는 것을 좁혀 두는
           일과 열지 않기로 하는 일은 다르다. file:// 과 content:// 는 이 앱이
           쓸 일이 없으므로 아예 닫는다 — 안드로이드 10 아래에서는 기본이 켜짐이다. */
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setGeolocationEnabled(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
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
        String frag = i == null ? null : i.getStringExtra("gijul_frag");
        /* 달력은 주소가 아니라 화면 위에 뜨는 것이라, 주소만 바꿔서는 열리지
           않는다. 이미 떠 있는 페이지에 직접 이른다. 과목(#/…)은 페이지의
           hashchange 가 받으므로 그냥 실어 보내면 된다. */
        if (Widgets.CAL.equals(frag)) {
            web.evaluateJavascript("window.gijulOpenCal&&window.gijulOpenCal()", null);
            return;
        }
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

    /* 뷰어에서 시간을 재고 돌아오면 그것을 페이지가 가져가야 한다. 웹뷰의
       visibilitychange 만 믿지 않고 여기서도 한 번 깨운다 — 둘 다 와도 탈이
       없다(가져간 것은 앱 쪽에서 지워지므로 두 번째는 빈손이다). */
    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.evaluateJavascript(
                "(function(){try{if(window.takeTimings&&takeTimings())render()}catch(e){}})()", null);
    }

    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }

    /* 뒤로가기.

       예전에는 한 번 누르면 곧장 앱이 닫혔다. 시트나 크게 보기를 열어 둔 채로
       눌러도 마찬가지여서, 닫으려던 사람이 앱을 껐다.

       이제 순서가 있다. 화면에 열어 둔 것이 있으면 그것부터 하나씩 닫고(페이지의
       gijulBack이 무엇을 닫았는지 알려준다), 그다음 방문 기록을 되짚고, 더 되짚을
       것이 없을 때에만 종료로 넘어간다. 종료는 두 번 눌러야 한다 — 마지막 한 번이
       실수이기 쉬운 자리다.

       무엇이든 닫았거나 되짚었으면 '한 번 더' 대기를 푼다. 그러지 않으면 시트를
       닫은 다음 눌린 뒤로가기가 종료로 이어져, 닫는 동작이 종료 수를 대신 세는
       꼴이 된다. */
    private boolean exitArmed = false;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Runnable disarm = () -> exitArmed = false;

    @Override
    public void onBackPressed() {
        /* 페이지가 자기 것을 먼저 닫는다. 답은 비동기로 오지만, 그 사이 다른 일이
           끼어들 여지가 없어(같은 UI 스레드로 돌아온다) 순서가 어긋나지 않는다. */
        web.evaluateJavascript(
                "(function(){try{return !!(window.gijulBack&&window.gijulBack())}"
                + "catch(e){return false}})()",
                value -> {
                    if ("true".equals(value)) { rearm(); return; }
                    if (web.canGoBack()) { web.goBack(); rearm(); return; }
                    if (exitArmed) { finish(); return; }
                    exitArmed = true;
                    Toast.makeText(this, "한 번 더 누르면 종료합니다", Toast.LENGTH_SHORT).show();
                    ui.postDelayed(disarm, 2000);
                });
    }

    /** 무언가 닫혔다 — 종료 대기를 푼다. */
    private void rearm() {
        exitArmed = false;
        ui.removeCallbacks(disarm);
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
    /* 셈 자체는 Names 에 있다 — 안드로이드 없이 값을 넣어 볼 수 있어야 해서다.
       여기 이름은 부르는 자리가 아홉 곳이라 그대로 둔다. */
    static String safe(String s) throws Exception { return Names.safe(s); }

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
        HttpURLConnection c = Net.open(url, Net.EBSI);
        try {
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

    /** 한 벌 뜬다. 받는 쪽에 보일 이름을 맞추려고 쓴다 — 임시 이름을 거치는 것은 받기와 같다. */
    static void copy(File from, File to) throws Exception {
        File tmp = new File(to.getParentFile(), to.getName() + ".part");
        try {
            try (InputStream in = new java.io.FileInputStream(from);
                 OutputStream os = new FileOutputStream(tmp)) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
            }
            if (to.exists() && !to.delete()) throw new Exception("옛 파일을 지우지 못했습니다");
            if (!tmp.renameTo(to)) throw new Exception("파일을 옮기지 못했습니다");
        } catch (Exception e) {
            tmp.delete();
            throw e;
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
        public void openPaper(String url, String name) { openPaperIn(url, name, null, null); }

        /**
         * 같은 뷰어로 열되 <b>회차 열쇠</b>까지 받는다. 잰 시간을 그 회차에
         * 남기려면 어느 회차인지 알아야 하는데, 주소만으로는 알 수 없다.
         *
         * 인자를 더 붙인 메서드를 따로 내는 것은, 있던 메서드에 인자를 더하면
         * 옛 앱에서 맞는 메서드가 없어 통째로 실패하기 때문이다. 페이지는 앱보다
         * 먼저 갱신되므로 그 사이 자료가 안 열린다.
         */
        @JavascriptInterface
        public void openPaperAt(String url, String name, String grade, String sub, String key) {
            open(paperIntent(url, name, grade, sub, key));
        }

        /** 앱이 재어 둔 시간을 페이지가 가져간다. 한 번 넘긴 것은 지운다. */
        @JavascriptInterface
        public String takeTimings() { return Timing.takeRecords(MainActivity.this); }

        /**
         * 같은 뷰어로 열되, <b>어느 과목에서 왔는지</b>도 함께 받는다.
         *
         * 띄워 둔 창의 목록이 이 값으로 첫 화면을 정한다 — 보던 과목의 회차부터
         * 보여주면 대개 찾던 것이 거기 있다. 주소만으로는 알 수 없다. 회차 파일은
         * 과목마다 따로 있어서, 주소 하나가 어느 과목 것인지 되짚으려면 과목
         * 파일을 전부 받아 뒤져야 한다.
         *
         * <b>이름을 새로 만든 것은 옛 앱을 위해서다.</b> openPaper 에 인자를 둘
         * 더 붙이면 옛 앱에는 맞는 메서드가 없어 호출이 통째로 실패하고, 페이지는
         * 앱보다 먼저 갱신되므로 그 사이 자료가 안 열린다. 페이지가 이 이름이
         * 있는지 보고 고르게 두면 옛 앱은 옛 길로 그대로 간다.
         */
        @JavascriptInterface
        public void openPaperIn(String url, String name, String grade, String sub) {
            open(paperIntent(url, name, grade, sub, null));
        }



        /** 파일 하나를 시스템 공유 시트로 넘긴다 */
        @JavascriptInterface
        public void shareFile(String name, String url) { io.execute(() -> share(name, url)); }

        /** 시스템 다크모드 여부. WebView의 prefers-color-scheme를 믿을 수 없어 직접 알려준다. */
        @JavascriptInterface
        public boolean systemDark() { return isNight(); }

        /**
         * 찍어 둔 '푼 회차'를 앱 쪽에 옮겨 적는다.
         *
         * 위젯은 <b>다른 프로세스</b>라 웹뷰의 localStorage 에 손이 닿지 않는다.
         * 페이지가 열릴 때마다 통째로 건네주면 앱이 제 저장소에 적고, 위젯은
         * 그것만 읽는다. 숨길 수 없는 결과가 하나 따라온다 — <b>페이지를 한 번은
         * 열어야</b> 위젯이 최신이 된다.
         *
         * 바뀐 것이 없으면 아무것도 하지 않는다. 페이지를 열 때마다 홈 화면의
         * 위젯을 다시 그리게 하면, 아무것도 안 바뀐 날에도 그 일이 돈다.
         */
        @JavascriptInterface
        public void setSolved(String json) {
            try {
                if (!Solved.put(MainActivity.this, json)) return;
                Widgets.refresh(MainActivity.this);
                /* 바뀐 때만 쓴다. 페이지는 열 때마다 한 번씩 건네므로, 안 바뀐
                   것까지 쓰면 아무 일도 안 한 날에도 파일 시각이 움직인다. */
                io.execute(MainActivity.this::writeAuto);
            } catch (Exception e) {
                Log.w(TAG, "표시를 옮겨 적지 못했습니다", e);
            }
        }

        /**
         * 백업 파일을 만들어 공유 시트로 넘긴다.
         *
         * 웹에서는 {@code <a download>} 한 줄이면 되는데 웹뷰에서는 아무 일도
         * 일어나지 않는다 — 내려받기를 받아 줄 것이 붙어 있지 않아서다. 그런데
         * 백업이 가장 절실한 쪽이 앱 사용자다(브라우저와 달리 앱을 지우면 통째로
         * 사라진다). 그래서 여기로 받는다.
         */
        @JavascriptInterface
        public void saveBackup(String json, String name) {
            io.execute(() -> {
                try {
                    File dir = new File(getCacheDir(), "share");
                    if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("임시 폴더를 만들지 못했습니다");
                    File f = new File(dir, safe(name));
                    try (OutputStream os = new FileOutputStream(f)) {
                        os.write(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                    }
                    Uri u = FileProvider.getUriForFile(MainActivity.this, AUTHORITY, f);
                    Intent i = new Intent(Intent.ACTION_SEND);
                    i.setType("application/json");
                    i.putExtra(Intent.EXTRA_STREAM, u);
                    i.putExtra(Intent.EXTRA_TITLE, name);
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    Intent chooser = Intent.createChooser(i, name);
                    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    open(chooser);
                    shareDone(true, "");
                } catch (Exception e) {
                    Log.w(TAG, "백업을 내보내지 못했습니다", e);
                    shareDone(false, "내보내지 못했습니다: " + e.getMessage());
                }
            });
        }

        /** 백업 파일을 고르게 한다. 고른 것은 onActivityResult 가 페이지로 넘긴다. */
        @JavascriptInterface
        public void pickBackup() {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    /* 내보낼 때 json 으로 적었지만, 저장한 앱에 따라 종류가 다르게
                       붙어 오는 일이 있다. 걸러 놓고 못 고르는 것보다 낫다. */
                    i.setType("*/*");
                    startActivityForResult(i, REQ_BACKUP);
                } catch (Exception e) {
                    Log.w(TAG, "파일 고르기를 열지 못했습니다", e);
                    backupPicked(null);
                }
            });
        }

        /**
         * 앱이 들고 있는 표시 사본. 위젯이 읽는 그것이다.
         *
         * 웹뷰의 자료가 날아가도 이 사본은 남는다. 페이지가 비었는데 여기 있으면
         * 되살릴지 묻는다 — 백업을 안 해 둔 사람에게 남는 마지막 줄이다.
         * 페이지가 읽을 수 있게 <b>백업 파일과 같은 모양</b>으로 돌려준다.
         */
        @JavascriptInterface
        public String savedSolved() {
            try {
                android.content.SharedPreferences pr = Solved.prefs(MainActivity.this);
                String raw = pr.getString("json", null);
                if (raw == null) return "{}";
                JSONObject marks = new JSONObject(raw).optJSONObject("marks");
                if (marks == null) return "{}";
                return new JSONObject()
                        .put("v", 1)
                        .put("at", new java.text.SimpleDateFormat(
                                "yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US)
                                .format(new java.util.Date(pr.getLong("at", 0))))
                        .put("subs", new JSONArray())
                        .put("solved", marks)
                        .toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        /**
         * 자동 백업할 자리를 한 번 고르게 한다.
         *
         * 고르고 나면 그 뒤로는 표시가 바뀔 때마다 앱이 조용히 덮어쓴다. 사람이
         * 기억해서 눌러야 하는 백업은 결국 안 하게 되는데, 안 한 것을 알아차리는
         * 때는 이미 늦은 뒤다.
         *
         * 고른 자리를 드라이브·원드라이브 같은 동기화 폴더로 두면 그것이 곧
         * 클라우드 백업이 된다 — 로그인도 심사도 없이.
         */
        @JavascriptInterface
        public void pickAutoBackup() {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    i.setType("application/json");
                    i.putExtra(Intent.EXTRA_TITLE, "기출직행-백업.json");
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                    startActivityForResult(i, REQ_AUTO);
                } catch (Exception e) {
                    Log.w(TAG, "자동 백업 자리를 고르지 못했습니다", e);
                    autoState();
                }
            });
        }

        /** 지금 어디에 쓰고 있는지. 없으면 빈 이름. */
        @JavascriptInterface
        public String autoBackup() { return autoJson(); }

        /** 그만둔다. 권한도 함께 놓는다 — 안 쓸 자리를 붙들고 있을 까닭이 없다. */
        @JavascriptInterface
        public void stopAutoBackup() {
            Uri u = autoUri();
            if (u != null) {
                try {
                    getContentResolver().releasePersistableUriPermission(u,
                            Intent.FLAG_GRANT_READ_URI_PERMISSION
                                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                } catch (Exception ignored) { }
            }
            prefs().edit().remove(AUTO_URI).remove(AUTO_NAME).remove(AUTO_FAIL).apply();
            autoState();
        }

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

    /** 학년·과목처럼 자리 이름으로 쓰이는 값인가. 모양이 아닌 것은 아예 안 들인다. */
    private static boolean tag(String v) {
        return v != null && !v.isEmpty() && v.length() <= 32
                && v.matches("[A-Za-z0-9_-]+");
    }

    /** 뷰어로 보낼 인텐트. openPaper·openPaperIn·openPaperAt 이 함께 쓴다. */
    private Intent paperIntent(String url, String name, String grade, String sub, String key) {
        String title;
        try {
            fromEbsi(url);
            title = safe(name);
        } catch (Exception e) {
            Log.w(TAG, "열 수 없는 자료: " + url, e);
            report(false, 0, "열 수 없는 자료입니다");
            return null;
        }
        Intent i = new Intent(MainActivity.this, PdfViewActivity.class);
        i.putExtra(PdfViewActivity.EXTRA_URL, url);
        i.putExtra(PdfViewActivity.EXTRA_NAME, title);
        /* 경계를 건너온 값이다. 파일 이름도 주소도 아니고 목록에서 과목을
           찾아보는 데만 쓰지만, 모양이 아닌 것은 아예 들이지 않는다. */
        if (tag(grade) && tag(sub)) {
            i.putExtra(PdfViewActivity.EXTRA_GRADE, grade);
            i.putExtra(PdfViewActivity.EXTRA_SUBJECT, sub);
        }
        /* 열쇠는 '학년/과목/시행일/회차이름'이다. 잰 시간을 페이지에 돌려줄 때
           그대로 되돌려 보낼 뿐 파일을 만드는 데는 쓰지 않지만, 길이는 본다. */
        if (key != null && !key.isEmpty() && key.length() < 300) {
            i.putExtra(PdfViewActivity.EXTRA_KEY, key);
        }
        return i;
    }

    private static final int REQ_BACKUP = 4101;
    private static final int REQ_AUTO = 4102;
    private static final String AUTO_URI = "auto.uri";
    private static final String AUTO_NAME = "auto.name";
    private static final String AUTO_FAIL = "auto.fail";

    private android.content.SharedPreferences prefs() {
        return getSharedPreferences("app", MODE_PRIVATE);
    }

    private Uri autoUri() {
        String s = prefs().getString(AUTO_URI, null);
        try { return s == null ? null : Uri.parse(s); } catch (Exception e) { return null; }
    }

    /**
     * 자동 백업 파일을 덮어쓴다.
     *
     * <b>실패를 삼키지 않는다.</b> 사람이 고른 자리는 나중에 사라질 수 있다 —
     * 파일을 지웠거나, 그 앱을 지웠거나, 권한이 풀렸거나. 조용히 멈춘 자동 백업은
     * 없는 것보다 나쁘다. 되고 있다고 믿게 만들기 때문이다. 그래서 어긋난 것을
     * 적어 두고 화면이 그것을 말한다.
     */
    private void writeAuto() {
        Uri u = autoUri();
        if (u == null) return;
        String json = Solved.backup(this);
        if (json == null) return;
        try (OutputStream os = getContentResolver().openOutputStream(u, "wt")) {
            if (os == null) throw new Exception("열지 못했습니다");
            os.write(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            if (prefs().getString(AUTO_FAIL, null) != null) {
                prefs().edit().remove(AUTO_FAIL).apply();
                autoState();
            }
        } catch (Exception e) {
            Log.w(TAG, "자동 백업을 쓰지 못했습니다", e);
            prefs().edit().putString(AUTO_FAIL,
                    e.getMessage() == null ? "쓰지 못했습니다" : e.getMessage()).apply();
            autoState();
        }
    }

    /** 고른 자리의 사람이 읽는 이름. 못 읽으면 주소 끝자락이라도. */
    private String autoName(Uri u) {
        try (android.database.Cursor c = getContentResolver().query(u,
                new String[]{android.provider.OpenableColumns.DISPLAY_NAME},
                null, null, null)) {
            if (c != null && c.moveToFirst() && !c.isNull(0)) return c.getString(0);
        } catch (Exception ignored) { }
        String s = u.getLastPathSegment();
        return s == null ? "고른 자리" : s.substring(s.lastIndexOf('/') + 1);
    }

    private String autoJson() {
        try {
            Uri u = autoUri();
            return new JSONObject()
                    .put("on", u != null)
                    .put("name", prefs().getString(AUTO_NAME, ""))
                    .put("error", prefs().getString(AUTO_FAIL, ""))
                    .toString();
        } catch (Exception e) { return "{\"on\":false}"; }
    }

    private void autoState() {
        String js = "window.gijulAutoBackup && window.gijulAutoBackup(" + autoJson() + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }

    /** 백업 파일 한도. 표시가 5,059개라도 300KB 남짓이라 이 위는 우리 것이 아니다. */
    private static final int MAX_BACKUP = 4 * 1024 * 1024;

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_AUTO) {
            Uri picked = (res == RESULT_OK && data != null) ? data.getData() : null;
            if (picked == null) { autoState(); return; }
            try {
                getContentResolver().takePersistableUriPermission(picked,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION
                                | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            } catch (Exception e) {
                /* 권한을 못 잡으면 지금은 써져도 다음 실행에는 못 쓴다. 그때 가서
                   조용히 실패하느니 여기서 안 된다고 말하는 편이 낫다. */
                Log.w(TAG, "자리 권한을 이어받지 못했습니다", e);
                prefs().edit().putString(AUTO_FAIL, "이 자리는 다음 실행에 다시 물어봅니다").apply();
            }
            prefs().edit().putString(AUTO_URI, picked.toString())
                    .putString(AUTO_NAME, autoName(picked)).apply();
            io.execute(() -> { writeAuto(); autoState(); });
            return;
        }
        if (req != REQ_BACKUP) return;
        final Uri u = (res == RESULT_OK && data != null) ? data.getData() : null;
        if (u == null) { backupPicked(null); return; }
        io.execute(() -> {
            try (InputStream in = getContentResolver().openInputStream(u)) {
                if (in == null) throw new Exception("파일을 열지 못했습니다");
                java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) {
                    b.write(buf, 0, n);
                    if (b.size() > MAX_BACKUP) throw new Exception("파일이 너무 큽니다");
                }
                backupPicked(new String(b.toByteArray(), java.nio.charset.StandardCharsets.UTF_8));
            } catch (Exception e) {
                Log.w(TAG, "백업 파일을 읽지 못했습니다", e);
                backupPicked(null);
            }
        });
    }

    /* 읽은 내용을 그대로 페이지에 넘긴다. 무엇이 맞는 백업인지는 페이지가 안다 —
       과목 번호와 회차 열쇠를 아는 쪽이 거기라, 여기서 또 보면 규칙이 두 벌이 된다. */
    private void backupPicked(String text) {
        String js = "window.gijulBackupPicked && window.gijulBackupPicked("
                + (text == null ? "null" : JSONObject.quote(text)) + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
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
