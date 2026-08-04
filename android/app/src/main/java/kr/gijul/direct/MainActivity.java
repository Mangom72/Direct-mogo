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
                // 사이트 안은 앱에서, 바깥(EBSi 원본 등)은 기본 브라우저로
                if (u.toString().startsWith(SITE)) return false;
                open(new Intent(Intent.ACTION_VIEW, u));
                return true;
            }
        });
        web.addJavascriptInterface(new Bridge(), "GijulNative");
        updater = new Updater(this);
        setContentView(web);

        if (state == null) web.loadUrl(SITE);
        else web.restoreState(state);
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
                    File[] fs = d.listFiles(File::isFile);
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

        /** 받아둔 파일을 기기의 뷰어로 연다 */
        @JavascriptInterface
        public void openSaved(String folder, String name) {
            File f = new File(new File(root(), folder), name);
            if (!f.isFile()) { report(false, 0, "파일이 없습니다"); return; }
            try {
                Uri u = FileProvider.getUriForFile(MainActivity.this, AUTHORITY, f);
                Intent i = new Intent(Intent.ACTION_VIEW);
                i.setDataAndType(u, mimeOf(name));
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                open(i);
            } catch (Exception e) {
                Log.w(TAG, "열기 실패: " + name, e);
                report(false, 0, "열지 못했습니다 — PDF를 볼 앱이 없을 수 있습니다");
            }
        }

        /** 회차 하나를 지운다. folder가 비면 전부 */
        @JavascriptInterface
        public void deleteSaved(String folder) {
            int n = 0;
            File[] dirs = folder == null || folder.isEmpty()
                    ? root().listFiles(File::isDirectory)
                    : new File[]{ new File(root(), folder) };
            if (dirs != null) for (File d : dirs) if (rmrf(d)) n++;
            report(true, n, n + "개 회차를 지웠습니다");
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

        /* 새 버전 확인은 네트워크를 타므로 결과를 돌려줄 수 없다.
           페이지는 window.gijulUpdate(state, message)로 받는다. */
        @JavascriptInterface
        public void checkUpdate(boolean force) {
            io.execute(() -> {
                String r = updater.check(force);
                try {
                    JSONObject o = new JSONObject(r);
                    if (!"available".equals(o.optString("state"))) {
                        if (force) report(false, 0, "이미 최신 버전입니다");
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
            where = o.getString("folder");
            File dir = new File(root(), where);
            if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("폴더를 만들지 못했습니다");

            for (int i = 0; i < files.length(); i++) {
                JSONObject f = files.getJSONObject(i);
                try {
                    writeOne(dir, f.getString("name"), f.getString("url"));
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

    private void writeOne(File dir, String name, String url) throws Exception {
        File out = new File(dir, name);
        File tmp = new File(dir, name + ".part");   // 중간에 끊겨도 반쪽 파일이 남지 않게
        download(url, tmp);
        if (out.exists()) out.delete();
        if (!tmp.renameTo(out)) { tmp.delete(); throw new Exception("파일을 옮기지 못했습니다"); }
    }

    private void download(String url, File to) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(60000);
        conn.setInstanceFollowRedirects(true);
        try {
            int code = conn.getResponseCode();
            if (code != 200) throw new Exception("HTTP " + code);
            try (InputStream in = conn.getInputStream(); OutputStream os = new FileOutputStream(to)) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
            }
        } finally {
            conn.disconnect();
        }
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
            File f = findSaved(name);
            if (f == null) {
                File dir = new File(getCacheDir(), "share");
                if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("임시 폴더를 만들지 못했습니다");
                f = new File(dir, name);
                if (!f.isFile() || f.length() == 0) download(url, f);
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
