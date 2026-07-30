package kr.gijul.direct;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 기출 직행을 감싸는 WebView 앱.
 *
 * 웹만으로는 저장 위치를 정할 수 없다 — 안드로이드 크롬에는 File System Access API가
 * 없고, 다운로드는 브라우저가 정한 폴더로만 떨어진다. 그래서 저장만 네이티브가 맡는다:
 * 사용자가 폴더를 한 번 고르면(SAF 문서 트리) 그 권한을 지속 보관하고, 회차마다
 * 하위 폴더를 만들어 문제·정답·해설을 그 안에 넣는다.
 *
 * 페이지는 window.GijulNative 가 있을 때만 이 경로를 쓴다. 다른 OS·브라우저는 그대로다.
 */
public class MainActivity extends Activity {

    private static final String TAG = "기출직행";
    private static final String SITE = "https://mangom72.github.io/Direct-mogo/";
    private static final String PREFS = "gijul";
    private static final String KEY_TREE = "treeUri";
    private static final int REQ_TREE = 1001;

    private WebView web;
    private SharedPreferences prefs;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    /** 폴더를 아직 안 골랐을 때, 고른 직후 이어서 처리할 요청 */
    private String pending;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage — 내 과목·테마 저장에 필요
        s.setSupportMultipleWindows(false);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                // 사이트 안은 앱에서, 바깥(EBSi PDF 등)은 기본 브라우저로
                if (u.toString().startsWith(SITE)) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u));
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

    // ── 페이지에서 부르는 창구 ────────────────────────────────────────────

    private class Bridge {
        /** 저장할 회차. {"folder":"...","files":[{"name":"...","url":"..."}]} */
        @JavascriptInterface
        public void savePaper(String json) {
            String tree = prefs.getString(KEY_TREE, null);
            if (tree == null) { pending = json; askFolder(); return; }
            io.execute(() -> save(Uri.parse(tree), json));
        }

        /** 저장 폴더를 다시 고른다 */
        @JavascriptInterface
        public void pickFolder() { pending = null; askFolder(); }

        /** 지금 저장 폴더가 정해져 있는지 */
        @JavascriptInterface
        public boolean hasFolder() { return prefs.getString(KEY_TREE, null) != null; }
    }

    private void askFolder() {
        runOnUiThread(() -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            startActivityForResult(i, REQ_TREE);
        });
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_TREE) return;
        if (res != RESULT_OK || data == null || data.getData() == null) {
            report(false, 0, "폴더를 고르지 않았습니다");
            pending = null;
            return;
        }
        Uri tree = data.getData();
        getContentResolver().takePersistableUriPermission(tree,
                Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        prefs.edit().putString(KEY_TREE, tree.toString()).apply();

        String job = pending;
        pending = null;
        if (job != null) io.execute(() -> save(tree, job));
        else report(true, 0, "저장 폴더를 정했습니다");
    }

    // ── 실제 저장 ────────────────────────────────────────────────────────

    private void save(Uri tree, String json) {
        int ok = 0, fail = 0;
        String where = "";
        try {
            JSONObject o = new JSONObject(json);
            JSONArray files = o.getJSONArray("files");
            ContentResolver cr = getContentResolver();
            Uri root = DocumentsContract.buildDocumentUriUsingTree(
                    tree, DocumentsContract.getTreeDocumentId(tree));
            Uri dir = findOrCreateDir(cr, tree, root, o.getString("folder"));
            where = o.getString("folder");

            for (int i = 0; i < files.length(); i++) {
                JSONObject f = files.getJSONObject(i);
                try {
                    writeOne(cr, dir, f.getString("name"), f.getString("url"));
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
                ? "'" + where + "' 폴더에 " + ok + "개 저장했습니다"
                : ok + "개 저장, " + fail + "개 실패");
    }

    /** 같은 이름 폴더가 있으면 재사용한다 — 없으면 createDocument가 "(1)"을 붙여 늘어난다 */
    private Uri findOrCreateDir(ContentResolver cr, Uri tree, Uri parent, String name)
            throws Exception {
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(
                tree, DocumentsContract.getDocumentId(parent));
        try (android.database.Cursor c = cr.query(children, new String[]{
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE}, null, null, null)) {
            while (c != null && c.moveToNext()) {
                if (name.equals(c.getString(1))
                        && DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2))) {
                    return DocumentsContract.buildDocumentUriUsingTree(tree, c.getString(0));
                }
            }
        }
        return DocumentsContract.createDocument(
                cr, parent, DocumentsContract.Document.MIME_TYPE_DIR, name);
    }

    private void writeOne(ContentResolver cr, Uri dir, String name, String url) throws Exception {
        String mime = name.endsWith(".png") ? "image/png"
                : name.endsWith(".pdf") ? "application/pdf" : "application/octet-stream";
        Uri file = DocumentsContract.createDocument(cr, dir, mime, name);
        if (file == null) throw new Exception("파일을 만들지 못했습니다");

        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(60000);
        conn.setInstanceFollowRedirects(true);
        try {
            int code = conn.getResponseCode();
            if (code != 200) throw new Exception("HTTP " + code);
            try (InputStream in = conn.getInputStream();
                 OutputStream out = cr.openOutputStream(file)) {
                byte[] buf = new byte[16384];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            }
        } finally {
            conn.disconnect();
        }
    }

    /** 결과를 페이지로 돌려준다 */
    private void report(boolean ok, int count, String message) {
        String js = "window.gijulSaveResult && window.gijulSaveResult("
                + ok + "," + count + "," + JSONObject.quote(message) + ")";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }
}
