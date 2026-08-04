package kr.gijul.direct;

import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.util.Log;
import android.view.Gravity;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.core.content.FileProvider;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 문제지를 앱 안에서 읽는 화면.
 *
 * WebView에는 PDF 뷰어가 없다. 그래서 처음에는 EBSi 주소를 기본 브라우저로 넘겼는데,
 * 문제를 열 때마다 앱이 크롬으로 바뀌는 건 이 앱의 요점을 잃는 일이었다. PdfRenderer는
 * API 21부터 있으므로 직접 그린다.
 *
 * 페이지는 RecyclerView로 필요한 것만 그린다 — 국어 문제지처럼 20쪽이 넘는 자료를
 * 통째로 비트맵으로 들고 있으면 메모리가 남아나지 않는다. 대신 화면 너비의 1.5배로
 * 렌더링해 두고 확대는 뷰 변형으로 처리한다. 그 배율까지는 선명하고, 확대할 때마다
 * 다시 그리지 않아 손가락을 따라온다.
 *
 * 정답은 PDF가 아니라 PNG라서, 같은 화면에서 한 장짜리로 보여준다.
 */
public class PdfViewActivity extends Activity {

    static final String EXTRA_URL = "url";      // 받아서 열 주소
    static final String EXTRA_FILE = "file";    // 이미 받아둔 파일의 절대 경로
    static final String EXTRA_NAME = "name";    // 표시할 이름

    private static final String TAG = "기출직행";
    private static final float RENDER_SCALE = 1.5f;   // 화면 너비 대비 렌더링 배율
    private static final float MAX_ZOOM = 2.5f;

    private final ExecutorService io = Executors.newSingleThreadExecutor();

    private Stage stage;
    private RecyclerView list;
    private TextView status;
    private TextView pageLabel;
    private PdfRenderer pdf;
    private ParcelFileDescriptor fd;
    private Bitmap image;               // PNG일 때
    private File file;
    private String name = "";

    private float zoom = 1f, panX = 0f, panY = 0f;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String n = getIntent().getStringExtra(EXTRA_NAME);
        name = n == null ? "" : n;
        setContentView(build());

        String path = getIntent().getStringExtra(EXTRA_FILE);
        String url = getIntent().getStringExtra(EXTRA_URL);
        if (path != null) {
            io.execute(() -> load(new File(path)));
        } else if (url != null) {
            status.setText("받는 중입니다…");
            io.execute(() -> fetch(url));
        } else {
            fail("열 파일이 없습니다");
        }
    }

    // ── 화면 ────────────────────────────────────────────────────────────

    private View build() {
        boolean night = (getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        int bg = night ? 0xFF14120E : 0xFFF3F1EC;
        int ink = night ? 0xFFEDE8DF : 0xFF221F1A;

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(bg);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        int pad = dp(10);
        bar.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText(name);
        title.setTextColor(ink);
        title.setTextSize(15);
        title.setMaxLines(1);
        title.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);
        bar.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        /* 몇 쪽짜리인지, 지금 어디인지. 20쪽 문제지를 위치 감각 없이 넘기게 두면
           찾던 문항을 지나쳤는지도 모른다. 한 장짜리(정답 이미지)면 숨긴다. */
        pageLabel = new TextView(this);
        pageLabel.setTextColor(ink);
        pageLabel.setTextSize(13);
        pageLabel.setPadding(0, 0, dp(10), 0);
        pageLabel.setVisibility(View.GONE);
        bar.addView(pageLabel);

        /* 앱 안에서 읽는 게 기본이지만, 필기 앱이나 인쇄로 넘기고 싶을 때가 있다 */
        Button out = new Button(this);
        out.setText("다른 앱");
        out.setTextSize(13);
        out.setAllCaps(false);
        out.setOnClickListener(v -> openElsewhere());
        bar.addView(out);

        root.addView(bar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        stage = new Stage(this);
        list = new RecyclerView(this);
        list.setLayoutManager(new LinearLayoutManager(this));
        list.setItemViewCacheSize(1);          // 확대 상태에서 비트맵이 쌓이지 않게
        list.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override public void onScrolled(@NonNull RecyclerView v, int dx, int dy) { showPage(); }
        });
        stage.addView(list, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        status = new TextView(this);
        status.setTextColor(ink);
        status.setGravity(Gravity.CENTER);
        status.setText("여는 중입니다…");
        stage.addView(status, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        root.addView(stage, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        return root;
    }

    /**
     * 확대·이동을 받는 판.
     *
     * 손짓은 dispatchTouchEvent에서 가로챈다. OnTouchListener로는 잡히지 않는다 —
     * 그 콜백은 자식이 아무도 이벤트를 먹지 않았을 때만 불리는데, 스크롤하는
     * RecyclerView는 항상 먹는다. 그래서 확대가 통째로 죽는다.
     *
     * 확대는 다시 그리지 않고 뷰를 변형해서 처리한다. 안드로이드가 터치 좌표를 같은
     * 행렬로 되돌려주므로, 확대한 상태에서도 목록 스크롤은 그대로 동작한다.
     */
    private class Stage extends FrameLayout {
        private final ScaleGestureDetector scale;
        private final GestureDetector tap;
        private boolean cancelled;      // 두 번째 손가락이 닿는 순간 목록의 스크롤을 끊는다

        Stage(PdfViewActivity a) {
            super(a);
            scale = new ScaleGestureDetector(a, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
                @Override
                public boolean onScale(ScaleGestureDetector d) {
                    setZoom(zoom * d.getScaleFactor());
                    return true;
                }
            });
            tap = new GestureDetector(a, new GestureDetector.SimpleOnGestureListener() {
                @Override
                public boolean onDoubleTap(MotionEvent e) {
                    setZoom(zoom > 1.2f ? 1f : 2f);
                    return true;
                }
                @Override
                public boolean onScroll(MotionEvent a, MotionEvent b, float dx, float dy) {
                    if (zoom <= 1f) return false;    // 원래 크기면 목록이 세로로 스크롤한다
                    panX -= dx;
                    clampPan();
                    apply();
                    return false;                     // 세로 스크롤은 목록 몫으로 남긴다
                }
            });
        }

        @Override
        public boolean dispatchTouchEvent(MotionEvent e) {
            scale.onTouchEvent(e);
            tap.onTouchEvent(e);

            if (e.getPointerCount() > 1 || scale.isInProgress()) {
                /* 손가락 두 개는 확대 전용이다. 목록이 같이 스크롤하면 화면이 튄다. */
                if (!cancelled) {
                    MotionEvent c = MotionEvent.obtain(e);
                    c.setAction(MotionEvent.ACTION_CANCEL);
                    super.dispatchTouchEvent(c);
                    c.recycle();
                    cancelled = true;
                }
                return true;
            }
            int a = e.getActionMasked();
            if (a == MotionEvent.ACTION_DOWN) cancelled = false;
            if (cancelled) {
                // 확대가 끝난 뒤 남은 손가락으로 목록이 갑자기 튀지 않게, 뗄 때까지 무시한다
                if (a == MotionEvent.ACTION_UP || a == MotionEvent.ACTION_CANCEL) cancelled = false;
                return true;
            }
            return super.dispatchTouchEvent(e);
        }
    }

    private void setZoom(float z) {
        zoom = Math.max(1f, Math.min(MAX_ZOOM, z));
        if (zoom == 1f) panX = panY = 0f;
        clampPan();
        apply();
    }

    private void clampPan() {
        float slack = list.getWidth() * (zoom - 1f) / 2f;
        panX = Math.max(-slack, Math.min(slack, panX));
        panY = 0f;
    }

    private void apply() {
        list.setPivotX(list.getWidth() / 2f);
        list.setPivotY(0f);
        list.setScaleX(zoom);
        list.setScaleY(zoom);
        list.setTranslationX(panX);
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    /** 화면을 가장 많이 차지한 쪽을 '지금 쪽'으로 본다 */
    private void showPage() {
        RecyclerView.Adapter<?> a = list.getAdapter();
        LinearLayoutManager lm = (LinearLayoutManager) list.getLayoutManager();
        if (a == null || lm == null || a.getItemCount() <= 1) return;
        int i = lm.findFirstCompletelyVisibleItemPosition();
        if (i == RecyclerView.NO_POSITION) i = lm.findFirstVisibleItemPosition();
        if (i == RecyclerView.NO_POSITION) return;
        pageLabel.setText((i + 1) + " / " + a.getItemCount());
        pageLabel.setVisibility(View.VISIBLE);
    }

    // ── 읽어들이기 ──────────────────────────────────────────────────────

    private void fetch(String url) {
        try {
            /* 이미 '받아둔 자료'에 있으면 그걸 쓴다 — 같은 파일을 두 번 받을 이유가 없다 */
            File saved = findSaved(nameOf(url));
            if (saved != null) { load(saved); return; }

            File dir = new File(getCacheDir(), "view");
            if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("임시 폴더를 만들지 못했습니다");
            File to = new File(dir, nameOf(url));
            if (!to.isFile() || to.length() == 0) {
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(20000);
                c.setReadTimeout(60000);
                c.setInstanceFollowRedirects(true);
                try {
                    if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                    try (InputStream in = c.getInputStream(); OutputStream os = new FileOutputStream(to)) {
                        byte[] buf = new byte[16384];
                        int n;
                        while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
                    }
                } finally { c.disconnect(); }
            }
            load(to);
        } catch (Exception e) {
            Log.w(TAG, "자료를 받지 못했습니다: " + url, e);
            fail("자료를 받지 못했습니다");
        }
    }

    private File findSaved(String fileName) {
        File root = getExternalFilesDir(null);
        File[] dirs = root == null ? null : root.listFiles(File::isDirectory);
        if (dirs != null) for (File d : dirs) {
            File[] fs = d.listFiles(File::isFile);
            if (fs != null) for (File f : fs) if (f.getName().endsWith(fileName)) return f;
        }
        return null;
    }

    private static String nameOf(String url) {
        String s = Uri.parse(url).getLastPathSegment();
        return s == null || s.isEmpty() ? "paper.pdf" : s;
    }

    private void load(File f) {
        file = f;
        try {
            if (f.getName().toLowerCase().endsWith(".png")
                    || f.getName().toLowerCase().endsWith(".jpg")) {
                image = BitmapFactory.decodeFile(f.getAbsolutePath());
                if (image == null) throw new Exception("이미지를 읽지 못했습니다");
            } else {
                fd = ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
                pdf = new PdfRenderer(fd);
            }
            runOnUiThread(() -> {
                status.setVisibility(View.GONE);
                list.setAdapter(new Pages());
                list.post(this::showPage);      // 스크롤하기 전에도 '1 / 16'이 보이게
            });
        } catch (Exception e) {
            Log.w(TAG, "열지 못했습니다: " + f, e);
            fail("이 자료를 열지 못했습니다");
        }
    }

    private void fail(String message) {
        runOnUiThread(() -> { status.setVisibility(View.VISIBLE); status.setText(message); });
    }

    private void openElsewhere() {
        if (file == null) return;
        try {
            Uri u = FileProvider.getUriForFile(this, MainActivity.AUTHORITY, file);
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(u, file.getName().endsWith(".png") ? "image/png" : "application/pdf");
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(i, name));
        } catch (Exception e) {
            fail("열 수 있는 앱이 없습니다");
        }
    }

    @Override
    public void onConfigurationChanged(Configuration c) {
        super.onConfigurationChanged(c);
        setZoom(1f);
        if (list.getAdapter() != null) list.getAdapter().notifyDataSetChanged();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
        try { if (pdf != null) pdf.close(); } catch (Exception ignored) { }
        try { if (fd != null) fd.close(); } catch (Exception ignored) { }
        if (image != null) image.recycle();
    }

    // ── 페이지 ──────────────────────────────────────────────────────────

    private class Pages extends RecyclerView.Adapter<Page> {

        @NonNull
        @Override
        public Page onCreateViewHolder(@NonNull ViewGroup parent, int type) {
            ImageView iv = new ImageView(PdfViewActivity.this);
            iv.setAdjustViewBounds(true);
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            iv.setBackgroundColor(Color.WHITE);        // 문제지는 흰 종이다. 어두운 테마에서도 뒤집지 않는다.
            iv.setLayoutParams(new RecyclerView.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            return new Page(iv);
        }

        @Override
        public void onBindViewHolder(@NonNull Page h, int i) { h.show(i); }

        @Override
        public int getItemCount() { return image != null ? 1 : (pdf == null ? 0 : pdf.getPageCount()); }

        @Override
        public void onViewRecycled(@NonNull Page h) { h.clear(); }
    }

    private class Page extends RecyclerView.ViewHolder {
        private final ImageView iv;
        private Bitmap bmp;
        private int shown = -1;

        Page(ImageView iv) { super(iv); this.iv = iv; }

        void show(int i) {
            clear();
            shown = i;
            if (image != null) { iv.setImageBitmap(image); return; }

            int w = Math.round(Math.max(list.getWidth(), 720) * RENDER_SCALE);
            io.execute(() -> {
                Bitmap b = render(i, w);
                if (b == null) return;
                iv.post(() -> {
                    if (shown != i) { b.recycle(); return; }   // 그리는 사이 다른 쪽으로 넘어갔다
                    clear();
                    bmp = b;
                    iv.setImageBitmap(b);
                });
            });
        }

        void clear() {
            iv.setImageDrawable(null);
            if (bmp != null && bmp != image) bmp.recycle();
            bmp = null;
        }
    }

    /* PdfRenderer는 페이지를 한 번에 하나만 열 수 있다. 렌더링을 단일 스레드에
       몰아둔 이유가 이것이다 — 여기서만 부른다. */
    private Bitmap render(int index, int width) {
        try {
            if (pdf == null || index >= pdf.getPageCount()) return null;
            try (PdfRenderer.Page p = pdf.openPage(index)) {
                int h = Math.max(1, Math.round(width * (float) p.getHeight() / p.getWidth()));
                Bitmap b = Bitmap.createBitmap(width, h, Bitmap.Config.ARGB_8888);
                b.eraseColor(Color.WHITE);            // 투명 배경으로 두면 글자만 떠 보인다
                p.render(b, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                return b;
            }
        } catch (OutOfMemoryError e) {
            /* OOM은 Exception이 아니라 Error다 — 아래 catch로는 잡히지 않아 앱이 죽는다.
               쪽수가 많은 문제지를 낮은 사양에서 열 때 실제로 닿을 수 있는 경계다. */
            Log.w(TAG, "메모리가 모자라 페이지를 그리지 못했습니다: " + index, e);
            fail("이 자료는 너무 커서 열지 못했습니다 — '다른 앱'으로 열어 보세요");
            return null;
        } catch (Exception e) {
            Log.w(TAG, "페이지를 그리지 못했습니다: " + index, e);
            return null;
        }
    }
}
