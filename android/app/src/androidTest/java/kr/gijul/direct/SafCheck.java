package kr.gijul.direct;

import android.app.Instrumentation;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;

/** 추가 의존성 없이 에뮬레이터에서 실행하는 SAF 회귀 시험. */
public class SafCheck extends Instrumentation {
    MainActivity activity;
    SharedPreferences prefs;
    static void require(boolean value, String reason) { if (!value) throw new AssertionError(reason); }
    Field field(String name) throws Exception {
        Field f = MainActivity.class.getDeclaredField(name); f.setAccessible(true); return f;
    }
    void pick(String id, int flags, String text) {
        runOnMainSync(() -> activity.startActivityForResult(new Intent()
                .setClassName("kr.gijul.direct.test", "kr.gijul.direct.SafGrantActivity")
                .putExtra("document", id).putExtra("grants", flags).putExtra("text", text), 4103));
        SystemClock.sleep(1800);
    }
    @Override public void onCreate(Bundle bundle) { super.onCreate(bundle); start(); }
    @Override public void onStart() {
        Bundle result = new Bundle(); int code = -1;
        try {
            activity = (MainActivity)startActivitySync(new Intent(getTargetContext(), MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            // 실제 앱 prefs 이름을 사용한다.
            Method prefsMethod = MainActivity.class.getDeclaredMethod("prefs"); prefsMethod.setAccessible(true);
            prefs = (SharedPreferences)prefsMethod.invoke(activity);
            field("autoMergePending").setBoolean(activity, true);
            String before = "{\"v\":1,\"subs\":[],\"solved\":{\"D300/158/20250101/시험\":\"20250101\"},\"times\":{}}";
            pick("good", 3, before);
            Uri good = Uri.parse(prefs.getString("auto.uri", ""));
            require(DocumentAccess.persisted(activity.getContentResolver(), good), "Result grant was not persisted");
            pick("readonly", 1, before);
            require(good.toString().equals(prefs.getString("auto.uri", "")), "Read-only result replaced auto URI");
            pick("failed", 3, before);
            Uri failed = Uri.parse(prefs.getString("auto.uri", ""));
            require(failed.toString().endsWith("/failed"), "Write-failure fixture was not selected");
            prefs.edit().putString("auto.hash", BackupIO.fingerprint(before)).commit();
            Solved.put(activity, "{\"v\":1,\"marks\":{\"D300/158/20250102/시험\":\"20250102\"},\"times\":{\"D300/158/20250102/시험\":{\"spent\":600,\"limit\":1200}}}");
            field("autoMergePending").setBoolean(activity, false);
            Method write = MainActivity.class.getDeclaredMethod("writeAuto"); write.setAccessible(true);
            ((ExecutorService)field("io").get(activity)).submit(() -> {
                try { write.invoke(activity); } catch(Exception e) {throw new RuntimeException(e);}
            }).get();
            try (java.io.InputStream in = activity.getContentResolver().openInputStream(failed)) {
                require(in != null && in.read() == -1, "Provider did not reproduce zero-byte truncation");
            }
            File recovery = new File(getTargetContext().getFilesDir(), "auto-backup");
            String kept = new String(new android.util.AtomicFile(new File(recovery, "last-good.json")).readFully(), StandardCharsets.UTF_8);
            require(before.equals(kept), "Pre-truncate recovery copy changed");
            String pending = new String(new android.util.AtomicFile(new File(recovery, "pending.json")).readFully(), StandardCharsets.UTF_8);
            require(new org.json.JSONObject(pending).getJSONObject("times").length() == 1, "Recovery omitted times");
            require(prefs.contains("auto.fail"), "Write failure did not surface");
            DocumentAccess.release(activity.getContentResolver(), failed);
            Method autoUri = MainActivity.class.getDeclaredMethod("autoUri"); autoUri.setAccessible(true);
            require(autoUri.invoke(activity) == null && !prefs.contains("auto.uri"), "Stale URI was not detached");
            result.putString("stream", "PASS: actual result grant persistence, read-only rejection, provider truncate failure recovery, missing LAST_MODIFIED, stale grant cleanup\n");
        } catch (Throwable t) {code=0;result.putString("stream",android.util.Log.getStackTraceString(t));}
        finally {if(activity!=null)runOnMainSync(() -> activity.finish());}
        finish(code,result);
    }
}
