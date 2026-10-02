package kr.gijul.direct;

import android.util.AtomicFile;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/** SAF에 원자적 교체가 없더라도 이 기기의 정상 사본은 쓰기 전에 지킨다. */
final class BackupIO {
    static String fingerprint(String text) throws Exception {
        byte[] bytes = java.security.MessageDigest.getInstance("SHA-256")
                .digest(text.getBytes(StandardCharsets.UTF_8));
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        return out.toString();
    }

    static boolean valid(String text) {
        try {
            JSONObject json = new JSONObject(text);
            return json.optInt("v", 0) == 1 && json.optJSONObject("solved") != null;
        } catch (Exception e) { return false; }
    }

    static void keep(File directory, String name, String text) throws Exception {
        if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("복구 사본 폴더를 만들지 못했습니다");
        AtomicFile file = new AtomicFile(new File(directory, name));
        FileOutputStream out = file.startWrite();
        try {
            out.write(text.getBytes(StandardCharsets.UTF_8));
            file.finishWrite(out);
        } catch (Exception e) { file.failWrite(out); throw e; }
    }

    private BackupIO() { }
}
