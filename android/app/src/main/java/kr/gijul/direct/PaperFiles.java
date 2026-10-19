package kr.gijul.direct;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import java.io.File;
import java.io.IOException;
import java.util.Locale;

/** 저장 이름과 표시 이름을 함께 쓰고, 큰 정답 이미지의 메모리를 제한한다. */
final class PaperFiles {
    private PaperFiles() {}
    static String mime(String name) {
        String s = name == null ? "" : name.toLowerCase(Locale.ROOT);
        if (s.endsWith(".png")) return "image/png";
        if (s.endsWith(".jpg") || s.endsWith(".jpeg")) return "image/jpeg";
        if (s.endsWith(".pdf")) return "application/pdf";
        return "application/octet-stream";
    }
    static final String MANIFEST = ".gijul-files.json";
    static String cacheName(String url) {
        try {
            byte[] digest = java.security.MessageDigest.getInstance("SHA-256")
                    .digest(url.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder();
            for (byte v : digest) out.append(String.format(Locale.ROOT, "%02x", v & 255));
            String path = url.split("[?#]", 2)[0].toLowerCase(Locale.ROOT);
            return out + (path.endsWith(".png") ? ".png" : path.endsWith(".jpg") ? ".jpg"
                    : path.endsWith(".jpeg") ? ".jpeg" : ".pdf");
        } catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    static String shareName(String name, String identity) throws Exception {
        String safe = MainActivity.safe(name);
        int dot = safe.lastIndexOf('.');
        String base = dot > 0 ? safe.substring(0, dot) : safe;
        String ext = dot > 0 ? safe.substring(dot) : ".pdf";
        while (base.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 170)
            base = base.substring(0, base.offsetByCodePoints(base.length(), -1));
        return base + " [" + cacheName(identity).substring(0, 24) + "]" + ext;
    }
    static org.json.JSONArray manifest(File dir) {
        try { return new org.json.JSONArray(readManifest(dir)); }
        catch (Exception e) { return new org.json.JSONArray(); }
    }
    private static String readManifest(File dir) throws java.io.IOException {
        try (java.io.FileInputStream in = new java.io.FileInputStream(new File(dir, MANIFEST));
             java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int n;
            while ((n = in.read(buffer)) != -1) { if (out.size() + n > 65536) throw new java.io.IOException("metadata too large"); out.write(buffer, 0, n); }
            return new String(out.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
        }
    }
    static String url(File dir, File file) {
        org.json.JSONArray entries = manifest(dir);
        for (int i = 0; i < entries.length(); i++) {
            org.json.JSONObject entry = entries.optJSONObject(i);
            if (entry != null && file.getName().equals(entry.optString("name"))
                    && file.length() > 0 && file.length() == entry.optLong("size", -1))
                return entry.optString("url");
        }
        return "";
    }
    static synchronized void remember(File dir, File file, String url) throws Exception {
        org.json.JSONArray entries = manifest(dir), next = new org.json.JSONArray();
        for (int i = 0; i < entries.length(); i++) {
            org.json.JSONObject e = entries.optJSONObject(i);
            if (e != null && !file.getName().equals(e.optString("name"))) next.put(e);
        }
        next.put(new org.json.JSONObject().put("name", file.getName()).put("url", url).put("size", file.length()));
        File tmp = new File(dir, MANIFEST + ".part");
        try {
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(tmp)) {
                out.write(next.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)); out.getFD().sync();
            }
            MainActivity.replace(tmp, new File(dir, MANIFEST));
        } catch (Exception e) { tmp.delete(); throw e; }
    }
    static File saved(File root, String url) {
        if (root == null || url == null || url.isEmpty()) return null;
        File[] dirs = root.listFiles(File::isDirectory);
        if (dirs != null) for (File dir : dirs) {
            org.json.JSONArray entries = manifest(dir);
            for (int i = 0; i < entries.length(); i++) {
                org.json.JSONObject e = entries.optJSONObject(i);
                if (e == null || !url.equals(e.optString("url"))) continue;
                try {
                    File f = new File(dir, MainActivity.safe(e.getString("name")));
                    if (f.isFile() && f.length() > 0 && f.length() == e.optLong("size", -1)) return f;
                } catch (Exception ignored) { }
            }
        }
        return null;
    }
    static int sample(int width, int height) {
        int n = 1;
        while (width / n > 4096 || height / n > 4096
                || (long) (width / n) * (height / n) > 4_000_000) n *= 2;
        return n;
    }
    static Bitmap image(File file) throws IOException {
        BitmapFactory.Options opt = new BitmapFactory.Options();
        opt.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), opt);
        if (opt.outWidth <= 0 || opt.outHeight <= 0) throw new IOException("이미지를 읽지 못했습니다");
        opt.inSampleSize = sample(opt.outWidth, opt.outHeight);
        opt.inJustDecodeBounds = false;
        Bitmap b = BitmapFactory.decodeFile(file.getAbsolutePath(), opt);
        if (b == null) throw new IOException("이미지를 읽지 못했습니다");
        return b;
    }
}
