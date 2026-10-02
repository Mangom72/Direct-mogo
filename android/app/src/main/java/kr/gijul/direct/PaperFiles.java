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
    static File saved(File root, String name) {
        if (root == null || name == null || name.isEmpty()) return null;
        try { MainActivity.safe(name); } catch (Exception e) { return null; }
        File[] dirs = root.listFiles(File::isDirectory);
        if (dirs != null) for (File dir : dirs) {
            File f = new File(dir, name);
            if (f.isFile()) return f;
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
