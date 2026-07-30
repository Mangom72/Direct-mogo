package kr.gijul.direct;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.core.content.FileProvider;

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
    private static final String AUTHORITY = "kr.gijul.direct.files";

    private WebView web;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage — 내 과목·테마 저장에 필요
        s.setSupportMultipleWindows(false);
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
        setContentView(web);

        if (state == null) web.loadUrl(SITE);
        else web.restoreState(state);
    }

    @Override protected void onSaveInstanceState(Bundle b) { super.onSaveInstanceState(b); web.saveState(b); }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
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
                i.setDataAndType(u, name.endsWith(".png") ? "image/png" : "application/pdf");
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

        /** 저장 위치를 사람이 읽을 형태로 */
        @JavascriptInterface
        public String where() { return root().getAbsolutePath(); }
    }

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
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(60000);
        conn.setInstanceFollowRedirects(true);
        try {
            int code = conn.getResponseCode();
            if (code != 200) throw new Exception("HTTP " + code);
            try (InputStream in = conn.getInputStream(); OutputStream os = new FileOutputStream(tmp)) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
            }
            if (out.exists()) out.delete();
            if (!tmp.renameTo(out)) throw new Exception("파일을 옮기지 못했습니다");
        } finally {
            conn.disconnect();
            if (tmp.exists()) tmp.delete();
        }
    }

    /** 결과를 페이지로 돌려준다 */
    private void report(boolean ok, int count, String message) {
        String js = "window.gijulSaveResult && window.gijulSaveResult("
                + ok + "," + count + "," + JSONObject.quote(message) + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }
}
