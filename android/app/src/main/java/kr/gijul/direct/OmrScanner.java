package kr.gijul.direct;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.util.Base64;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.IntentSenderRequest;
import androidx.activity.result.contract.ActivityResultContracts;

import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions;
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning;
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;

/** One-page, on-device document scan. Images are transient and never uploaded. */
final class OmrScanner {
    interface Result { void receive(String id, boolean ok, String value); }
    private final ComponentActivity activity;
    private final ExecutorService io;
    private final Result result;
    private final ActivityResultLauncher<IntentSenderRequest> scanLauncher;
    private final ActivityResultLauncher<String[]> pickLauncher;
    private volatile String active;
    private volatile boolean closed;
    private boolean busy;

    OmrScanner(ComponentActivity activity, ExecutorService io, Result result) {
        this.activity = activity;
        this.io = io;
        this.result = result;
        scanLauncher = activity.registerForActivityResult(
                new ActivityResultContracts.StartIntentSenderForResult(), response -> {
                    busy = false;
                    String id = active;
                    if (id == null || closed) return;
                    GmsDocumentScanningResult scanned = response.getResultCode() == android.app.Activity.RESULT_OK
                            ? GmsDocumentScanningResult.fromActivityResultIntent(response.getData()) : null;
                    if (scanned == null || scanned.getPages() == null || scanned.getPages().isEmpty()) {
                        finish(id, false, "취소했습니다");
                        return;
                    }
                    read(id, scanned.getPages().get(0).getImageUri());
                });
        pickLauncher = activity.registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
            busy = false;
            String id = active;
            if (id == null || closed) return;
            if (uri == null) finish(id, false, "취소했습니다"); else read(id, uri);
        });
    }

    void start(String id, boolean pick) {
        if (closed || id == null || !id.matches("[A-Za-z0-9_-]{1,80}")) return;
        if (busy || active != null) { result.receive(id, false, "이전 사진 작업을 먼저 닫아 주세요"); return; }
        active = id;
        busy = true;
        if (pick) {
            try { pickLauncher.launch(new String[]{"image/jpeg", "image/png"}); }
            catch (Exception e) { busy = false; finish(id, false, "사진 선택을 열지 못했습니다"); }
            return;
        }
        GmsDocumentScannerOptions options = new GmsDocumentScannerOptions.Builder()
                .setGalleryImportAllowed(true).setPageLimit(1)
                .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
                // OMR marks must survive scanning; ML stain/ink removal is unsuitable here.
                .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_BASE)
                .build();
        GmsDocumentScanning.getClient(options).getStartScanIntent(activity)
                .addOnSuccessListener(sender -> {
                    if (closed || !id.equals(active)) { busy = false; return; }
                    try { scanLauncher.launch(new IntentSenderRequest.Builder(sender).build()); }
                    catch (Exception e) { busy = false; finish(id, false, "스캐너를 열지 못했습니다. 사진에서 가져오기를 사용해 주세요"); }
                })
                .addOnFailureListener(error -> {
                    busy = false;
                    finish(id, false, "문서 스캐너를 사용할 수 없습니다. Google Play 서비스와 인터넷 연결을 확인하거나 사진에서 가져오기를 사용해 주세요");
                });
    }

    void cancel(String id) { if (id != null && id.equals(active)) active = null; }
    void close() { closed = true; active = null; }

    private void read(String id, Uri uri) {
        try { io.execute(() -> {
            Bitmap bitmap = null;
            try {
                if (closed || !id.equals(active)) return;
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inJustDecodeBounds = true;
                try (InputStream stream = activity.getContentResolver().openInputStream(uri)) {
                    BitmapFactory.decodeStream(stream, null, options);
                }
                if (options.outWidth <= 0 || options.outHeight <= 0
                        || (long) options.outWidth * options.outHeight > 40_000_000L)
                    throw new IllegalArgumentException("읽을 수 없는 이미지입니다");
                int sample = 1;
                while (Math.max(options.outWidth, options.outHeight) / sample > 2400) sample *= 2;
                options.inSampleSize = sample;
                options.inJustDecodeBounds = false;
                try (InputStream stream = activity.getContentResolver().openInputStream(uri)) {
                    bitmap = BitmapFactory.decodeStream(stream, null, options);
                }
                if (bitmap == null) throw new IllegalArgumentException("사진을 읽지 못했습니다");
                int longest = Math.max(bitmap.getWidth(), bitmap.getHeight());
                if (longest > 1800) {
                    Bitmap smaller = Bitmap.createScaledBitmap(bitmap,
                            Math.max(1, bitmap.getWidth() * 1800 / longest),
                            Math.max(1, bitmap.getHeight() * 1800 / longest), true);
                    if (smaller != bitmap) { bitmap.recycle(); bitmap = smaller; }
                }
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 90, bytes) || bytes.size() > 2 * 1024 * 1024)
                    throw new IllegalArgumentException("이미지가 너무 큽니다. 사진 크기를 줄여 주세요");
                finish(id, true, "data:image/jpeg;base64," + Base64.encodeToString(bytes.toByteArray(), Base64.NO_WRAP));
            } catch (Exception e) {
                finish(id, false, "사진을 읽지 못했습니다. JPEG 또는 PNG 사진을 다시 골라 주세요");
            } finally { if (bitmap != null) bitmap.recycle(); }
        }); } catch (java.util.concurrent.RejectedExecutionException e) {
            finish(id, false, "사진 작업이 종료되었습니다");
        }
    }

    private void finish(String id, boolean ok, String value) {
        activity.runOnUiThread(() -> {
            if (closed || !id.equals(active)) return;
            active = null;
            result.receive(id, ok, value);
        });
    }
}
