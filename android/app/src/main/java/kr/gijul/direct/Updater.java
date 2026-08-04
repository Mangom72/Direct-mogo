package kr.gijul.direct;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.util.Log;

import androidx.core.content.FileProvider;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Arrays;

/**
 * 새 버전 확인과 설치.
 *
 * 이 앱은 스토어를 거치지 않으므로 업데이트를 알려줄 주체가 없다. 그래서 사이트에
 * 같이 올려둔 작은 명세(app/latest.json)를 앱이 직접 읽고, 설치된 versionCode보다
 * 크면 사용자에게 물어 APK를 받아 시스템 설치 화면으로 넘긴다.
 *
 * 신뢰 경계가 여기에 있다 — 명세는 우리 사이트에서 HTTPS로 오지만, 그 말만 믿고
 * 아무 APK나 설치 화면에 올리면 안 된다. 그래서 설치 직전에 받은 파일을 직접 뜯어
 * 세 가지를 확인한다:
 *
 *   1. SHA-256이 명세와 같은가 (전송 중 손상·중간자)
 *   2. 패키지 이름이 우리 것인가 (다른 앱을 설치시키려는 시도)
 *   3. 서명 인증서가 지금 실행 중인 앱과 같은가 (우리 키로 서명된 빌드인가)
 *
 * 3번은 안드로이드도 업데이트 설치 때 강제하지만, 그건 이미 설치 화면이 뜬 뒤의
 * 이야기다. 사용자에게 설치 화면을 보여주기 전에 우리가 먼저 거른다.
 */
class Updater {

    private static final String TAG = "기출직행";
    private static final String MANIFEST = "https://mangom72.github.io/Direct-mogo/app/latest.json";
    private static final int MAX_APK = 64 * 1024 * 1024;   // 명세가 거짓말을 해도 디스크를 채우지 못하게

    private final Activity act;
    private JSONObject pending;      // 확인된 새 버전. 설치는 사용자가 누른 뒤에만.

    Updater(Activity act) { this.act = act; }

    // ── 확인 ────────────────────────────────────────────────────────────

    /**
     * 명세를 읽어 새 버전이 있는지 본다. 실행할 때마다 부른다 — 명세가 200바이트
     * 남짓이라 아낄 것이 없고, 미루면 고쳐둔 것이 며칠씩 사용자에게 닿지 않는다.
     *
     * @return 페이지에 돌려줄 JSON. state = none|available|error
     */
    String check() {
        try {
            JSONObject m = new JSONObject(get(MANIFEST));

            long here = installedCode();
            long there = m.getLong("versionCode");
            if (there <= here) return state("none");

            pending = m;
            return new JSONObject()
                    .put("state", "available")
                    .put("versionName", m.optString("versionName", String.valueOf(there)))
                    .put("notes", m.optString("notes", ""))
                    .put("size", m.optLong("size", 0))
                    .toString();
        } catch (Exception e) {
            Log.w(TAG, "업데이트 확인 실패", e);
            return state("error");     // 조용히 넘긴다 — 네트워크가 없을 뿐일 수 있다
        }
    }

    private static String state(String s) {
        try { return new JSONObject().put("state", s).toString(); }
        catch (Exception e) { return "{\"state\":\"error\"}"; }
    }

    private long installedCode() throws Exception {
        PackageInfo pi = act.getPackageManager().getPackageInfo(act.getPackageName(), 0);
        return Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode;
    }

    String version() {
        try {
            PackageInfo pi = act.getPackageManager().getPackageInfo(act.getPackageName(), 0);
            return new JSONObject()
                    .put("code", Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode)
                    .put("name", pi.versionName).toString();
        } catch (Exception e) { return "{}"; }
    }

    // ── 설치 ────────────────────────────────────────────────────────────

    /** 받아서 검사하고 시스템 설치 화면으로 넘긴다. 실행 스레드에서 부르지 말 것. */
    void install() {
        JSONObject m = pending;
        if (m == null) { report("error", "먼저 새 버전을 확인해야 합니다"); return; }

        /* 안드로이드 8부터는 앱마다 '이 출처 허용'을 받아야 한다. 없으면 설치 화면이
           그냥 튕기므로, 튕기기 전에 해당 설정 화면으로 보낸다. */
        if (Build.VERSION.SDK_INT >= 26 && !act.getPackageManager().canRequestPackageInstalls()) {
            report("permission", "이 앱에서 설치를 허용해 주세요");
            act.runOnUiThread(() -> {
                try {
                    act.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:" + act.getPackageName())));
                } catch (Exception e) {
                    report("error", "설치 권한 설정을 열지 못했습니다");
                }
            });
            return;
        }

        File dir = new File(act.getCacheDir(), "update");
        File apk = new File(dir, "update.apk");
        try {
            report("downloading", "");
            if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("임시 폴더를 만들지 못했습니다");
            download(m.getString("url"), apk);

            String want = m.optString("sha256", "");
            String got = sha256(apk);
            if (!want.isEmpty() && !want.equalsIgnoreCase(got))
                throw new Exception("내려받은 파일이 손상되었습니다");

            verifyIsOurs(apk);

            Uri u = FileProvider.getUriForFile(act, MainActivity.AUTHORITY, apk);
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(u, "application/vnd.android.package-archive");
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            act.runOnUiThread(() -> {
                try { act.startActivity(i); report("installing", ""); }
                catch (Exception e) { report("error", "설치 화면을 열지 못했습니다"); }
            });
        } catch (Exception e) {
            Log.w(TAG, "업데이트 설치 실패", e);
            apk.delete();
            report("error", e.getMessage() == null ? "업데이트하지 못했습니다" : e.getMessage());
        }
    }

    /** 받은 APK가 정말 이 앱의 새 버전인지 — 패키지 이름과 서명 인증서로 확인한다 */
    private void verifyIsOurs(File apk) throws Exception {
        PackageManager pm = act.getPackageManager();
        int flag = Build.VERSION.SDK_INT >= 28
                ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageInfo got = pm.getPackageArchiveInfo(apk.getAbsolutePath(), flag);
        if (got == null) throw new Exception("APK를 읽지 못했습니다");
        if (!act.getPackageName().equals(got.packageName))
            throw new Exception("다른 앱의 설치 파일입니다");

        PackageInfo mine = pm.getPackageInfo(act.getPackageName(), flag);
        if (!sameSigner(certs(mine), certs(got)))
            throw new Exception("서명이 이 앱과 다릅니다");
    }

    @SuppressWarnings("deprecation")
    private static Signature[] certs(PackageInfo pi) throws Exception {
        if (Build.VERSION.SDK_INT >= 28) {
            SigningInfo si = pi.signingInfo;
            if (si == null) throw new Exception("서명 정보가 없습니다");
            return si.hasMultipleSigners() ? si.getApkContentsSigners() : si.getSigningCertificateHistory();
        }
        if (pi.signatures == null) throw new Exception("서명 정보가 없습니다");
        return pi.signatures;
    }

    /* 서명 이력에 겹치는 인증서가 하나라도 있으면 같은 계보로 본다 —
       v3로 키를 교체하면 새 APK가 옛 인증서를 이력에 담고 오기 때문이다. */
    private static boolean sameSigner(Signature[] a, Signature[] b) {
        for (Signature x : a) for (Signature y : b) if (x.equals(y)) return true;
        return false;
    }

    // ── 그물망 ──────────────────────────────────────────────────────────

    private static String get(String url) throws Exception {
        HttpURLConnection c = open(url);
        try (InputStream in = c.getInputStream()) {
            ByteArrayBuilder b = new ByteArrayBuilder();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) { b.add(buf, n); if (b.size() > 64 * 1024) break; }
            return b.text();
        } finally { c.disconnect(); }
    }

    private static void download(String url, File to) throws Exception {
        HttpURLConnection c = open(url);
        try (InputStream in = c.getInputStream(); OutputStream os = new FileOutputStream(to)) {
            byte[] buf = new byte[16384];
            int n;
            long total = 0;
            while ((n = in.read(buf)) > 0) {
                total += n;
                if (total > MAX_APK) throw new Exception("파일이 너무 큽니다");
                os.write(buf, 0, n);
            }
        } finally { c.disconnect(); }
    }

    private static HttpURLConnection open(String url) throws Exception {
        if (!url.startsWith("https://")) throw new Exception("안전하지 않은 주소입니다");
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(60000);
        c.setInstanceFollowRedirects(true);
        int code = c.getResponseCode();
        if (code != 200) { c.disconnect(); throw new Exception("HTTP " + code); }
        return c;
    }

    private static String sha256(File f) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(f)) {
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) md.update(buf, 0, n);
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    private void report(String state, String message) {
        String js = "window.gijulUpdate && window.gijulUpdate("
                + JSONObject.quote(state) + "," + JSONObject.quote(message) + ")";
        act.runOnUiThread(() -> ((MainActivity) act).eval(js));
    }

    /** 명세가 작아서 스트림을 통째로 모으는 편이 간단하다 */
    private static class ByteArrayBuilder {
        private byte[] a = new byte[8192];
        private int n = 0;
        void add(byte[] buf, int len) {
            if (n + len > a.length) a = Arrays.copyOf(a, Math.max(a.length * 2, n + len));
            System.arraycopy(buf, 0, a, n, len);
            n += len;
        }
        int size() { return n; }
        String text() { return new String(a, 0, n, java.nio.charset.StandardCharsets.UTF_8); }
    }
}
