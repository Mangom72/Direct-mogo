package kr.gijul.direct;

import android.animation.ValueAnimator;
import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.util.Log;
import android.view.Gravity;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.animation.DecelerateInterpolator;
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
 * 통째로 비트맵으로 들고 있으면 메모리가 남아나지 않는다. 대신 화면 너비보다 조금 크게
 * (RENDER_SCALE) 렌더링해 두고 확대는 뷰 변형으로 처리한다. 그 배율까지는 선명하고,
 * 확대할 때마다 다시 그리지 않아 손가락을 따라온다.
 *
 * 보고 있는 쪽 앞뒤로 미리 그려 둔다. 넘길 때마다 흰 종이를 보고 기다리지 않게
 * 하려는 것이고, 그려둔 것은 바이트로 한도를 건 캐시에 담긴다. 축소는 1배 아래로도
 * 내려가 양옆에 여백이 생기며, 그만큼 여러 쪽이 한눈에 들어온다.
 *
 * 정답은 PDF가 아니라 PNG라서, 같은 화면에서 한 장짜리로 보여준다.
 */
public class PdfViewActivity extends Activity {

    static final String EXTRA_URL = "url";      // 받아서 열 주소
    static final String EXTRA_FILE = "file";    // 이미 받아둔 파일의 절대 경로
    static final String EXTRA_NAME = "name";    // 표시할 이름

    private static final String TAG = "기출직행";
    /* 화면 너비 대비 렌더링 배율. 올리면 확대했을 때 선명하지만 비트맵이 그만큼
       무거워지고, 그 무게가 쪽을 넘길 때의 걸림으로 그대로 나온다 — 1080px 화면에서
       1.5배면 한 장에 15MB다. 확대는 2.5배까지 가지만 거기서 조금 무른 편이
       넘길 때마다 걸리는 것보다 낫다. */
    private static final float RENDER_SCALE = 1.25f;
    private static final float MAX_ZOOM = 2.5f;
    /* 1보다 작게도 줄인다 — 양옆에 여백이 생기면서 여러 쪽이 한눈에 들어온다.
       더 줄여봐야 글자를 못 읽으니 여기서 멈춘다. */
    private static final float MIN_ZOOM = 0.5f;

    private final ExecutorService io = Executors.newSingleThreadExecutor();

    /* 그려둔 쪽. 미리 그린 것도 여기 들어가고, 되돌아갈 때도 여기서 나온다.
       비트맵은 한 쪽에 십수 MB라 개수가 아니라 바이트로 한도를 잡아야 한다.
       비트맵을 직접 recycle하지 않는 이유는, 아직 화면에 걸린 것을 지우면
       그 자리에서 죽기 때문이다. 한도를 지키는 쪽이 훨씬 안전하다. */
    private final android.util.LruCache<Integer, Bitmap> cache =
            new android.util.LruCache<Integer, Bitmap>(
                    (int) Math.min(Runtime.getRuntime().maxMemory() / 4, Integer.MAX_VALUE)) {
                @Override protected int sizeOf(Integer k, Bitmap b) { return b.getByteCount(); }
            };

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
    private boolean pinching;
    private ValueAnimator settle;      // 제자리 찾아가는 중. 새 손짓이 오면 양보한다.

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
        /* 목록 크기가 내용에 따라 변하지 않는다고 알려주면 항목마다 전체 배치를
           다시 하지 않는다. 쪽을 넘길 때 도는 일이 그만큼 준다. */
        list.setHasFixedSize(true);
        list.setItemViewCacheSize(3);          // 왔다 갔다 할 때 다시 붙이지 않도록
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
                public boolean onScaleBegin(ScaleGestureDetector d) {
                    /* 줄이면 화면에 여러 쪽이 들어온다. 다 줄이고 나서 그리기 시작하면
                       아래쪽이 한 박자 늦게 차오른다. 손짓이 시작될 때 미리 건다. */
                    pinching = true;
                    stopSettle();      // 미끄러지는 중에 다시 잡으면 손이 이긴다
                    /* 줄이는 동안 목록이 화면보다 짧아져 아래가 빈 채로 남는다. 다 줄인
                       뒤에 늘리면 그 빈 자리가 눈에 보이므로, 최대로 줄였을 때를 미리
                       잡아둔다. 손짓 내내 재배치가 없고 아래도 비지 않는다. */
                    setListHeight(Math.round(stage.getHeight() / MIN_ZOOM));
                    ahead(focus);
                    return true;
                }
                @Override
                public boolean onScale(ScaleGestureDetector d) {
                    zoomAt(zoom * d.getScaleFactor(), d.getFocusX(), d.getFocusY());
                    return true;
                }
                @Override
                public void onScaleEnd(ScaleGestureDetector d) {
                    pinching = false;
                    fitHeight();
                    settlePan();
                    ahead(focus);
                }
            });
            tap = new GestureDetector(a, new GestureDetector.SimpleOnGestureListener() {
                @Override
                public boolean onDoubleTap(MotionEvent e) {
                    zoomAt(zoom > 1.2f ? 1f : 2f, e.getX(), e.getY());
                    fitHeight();
                    ahead(focus);
                    return true;
                }
                @Override
                public boolean onScroll(MotionEvent a, MotionEvent b, float dx, float dy) {
                    /* 손가락 두 개일 때도 이 콜백은 계속 불린다. 여기서 clampPan을
                       돌리면 확대 도중 페이지가 화면 폭을 넘는 순간 잡고 있는데도
                       가운데로 끌려간다 — 확대는 확대대로 두어야 한다. */
                    if (pinching) return false;
                    if (zoom <= 1f) return false;    // 원래 크기·축소면 목록이 세로로 스크롤한다
                    panX -= dx;
                    clampPan();
                    apply();
                    return false;                     // 세로 스크롤은 목록 몫으로 남긴다
                }
                @Override
                public boolean onDown(MotionEvent e) { return true; }
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

    /**
     * 손가락 사이를 중심으로 확대·축소한다.
     *
     * 기준점을 뷰의 pivot으로 옮기는 방법은 쓰지 않았다. pivot은 뷰 자신의 좌표계
     * 값인데 손짓 좌표는 부모 좌표계로 들어와서, 이미 변형된 뷰에서는 둘이 어긋난다.
     * 대신 pivot을 (0,0)에 못박고 배율과 이동을 직접 계산한다 —
     * 화면 = 내용*배율 + 이동 이라는 한 줄짜리 모형이라 역산이 어긋날 데가 없다.
     *
     * 세로는 이동값을 두지 않고 목록을 그만큼 스크롤한다. 세로 이동을 따로 들면
     * 목록 스크롤과 둘이 같은 일을 하게 되어 서로 어긋난다.
     */
    private void zoomAt(float z, float fx, float fy) {
        float was = zoom;
        zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z));
        if (zoom == was) return;

        // 손가락 아래 있던 지점이 그 자리에 남도록
        panX = fx - (fx - panX) * zoom / was;
        list.scrollBy(0, Math.round(fy * (1f / was - 1f / zoom)));

        if (pinching) loosePan(); else clampPan();
        apply();
    }

    /* 손짓 중에는 손가락을 따라가는 것이 우선이다. 여기서 중앙으로 끌어당기면
       매 프레임 손가락과 반대로 당기는 셈이라 화면이 손에서 미끄러진다.
       화면 밖으로 완전히 놓치지 않을 만큼만 붙잡아 둔다. */
    private void loosePan() {
        float shown = list.getWidth() * zoom;
        float room = stage.getWidth();
        panX = Math.max(room * 0.25f - shown, Math.min(room * 0.75f, panX));
    }

    private void clampPan() {
        float shown = list.getWidth() * zoom;
        float room = stage.getWidth();
        /* 화면보다 좁아지면 가운데에 세운다 — 양옆에 여백이 생기는 게 이 상태다.
           넓으면 화면 밖으로 흰 여백이 새지 않는 범위 안에서만 움직인다. */
        panX = shown <= room
                ? (room - shown) / 2f
                : Math.max(room - shown, Math.min(0f, panX));
    }

    /* 손을 뗀 뒤에 제자리를 찾아간다. 그냥 튀게 두면 마지막 순간에 화면이 한 번
       덜컥하므로 짧게 미끄러뜨린다. */
    private void settlePan() {
        float from = panX;
        clampPan();
        float to = panX;
        if (Math.abs(to - from) < 0.5f) { apply(); return; }

        panX = from;
        stopSettle();
        settle = ValueAnimator.ofFloat(from, to);
        settle.setDuration(160);
        settle.setInterpolator(new DecelerateInterpolator());
        settle.addUpdateListener(v -> { panX = (float) v.getAnimatedValue(); apply(); });
        settle.start();
    }

    private void stopSettle() {
        if (settle != null) { settle.cancel(); settle = null; }
    }

    /* 배율만큼 목록을 키우거나 줄여, 그려지는 높이가 늘 화면과 같게 맞춘다.
       축소하면 아래가 비고 확대하면 안 보이는 곳까지 배치하게 되는데 둘 다 이걸로
       없어진다. 손짓 도중에 하면 매 프레임 재배치가 되므로 손을 뗀 뒤에만 맞춘다. */
    private void fitHeight() {
        if (stage.getHeight() <= 0) return;
        setListHeight(Math.round(stage.getHeight() / zoom));
    }

    private void setListHeight(int want) {
        ViewGroup.LayoutParams lp = list.getLayoutParams();
        if (Math.abs(lp.height - want) > 1) { lp.height = want; list.setLayoutParams(lp); }
    }

    private void apply() {
        list.setPivotX(0f);
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
                list.post(() -> { measureRender(); showPage(); });   // 배치가 끝난 뒤에 폭을 잰다
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
        zoom = 1f; panX = 0f;      // 화면이 바뀌었으니 배율은 원래대로 되돌린다
        clampPan();
        apply();
        fitHeight();
        cache.evictAll();        // 화면 너비가 달라졌으니 그려둔 쪽은 크기가 맞지 않는다
        renderW = 0;
        list.post(this::measureRender);
        if (list.getAdapter() != null) list.getAdapter().notifyDataSetChanged();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
        stopSettle();
        cache.evictAll();
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
        private int shown = -1;

        Page(ImageView iv) { super(iv); this.iv = iv; }

        void show(int i) {
            clear();
            shown = i;
            if (image != null) { iv.setImageBitmap(image); return; }

            focus = i;
            measureRender();
            Bitmap have = cache.get(i);
            if (have != null) { iv.setImageBitmap(have); ahead(i); return; }

            io.execute(() -> {
                Bitmap b = renderInto(i);
                if (b == null) return;
                iv.post(() -> {
                    if (shown == i) iv.setImageBitmap(b);      // 그리는 사이 다른 쪽으로 넘어갔을 수 있다
                    ahead(i);
                });
            });
        }

        void clear() { iv.setImageDrawable(null); }
    }

    /* 뒷장을 미리 그려 둔다. 넘길 때마다 흰 종이를 보고 기다리는 게 이 뷰어의
       유일한 거슬리는 점이었다. 렌더링은 단일 스레드라 보이는 쪽이 먼저 나가고
       미리 그리기는 그 뒤에 줄을 서므로, 지금 보는 화면을 늦추지 않는다.
       뒤로도 한 장 잡아두는 건 되돌아갈 때가 앞으로 갈 때만큼 잦기 때문이다. */
    private void ahead(int i) {
        /* 줄일수록 한 화면에 여러 쪽이 들어오므로 그만큼 더 멀리까지 미리 그린다.
           1배에서 두 쪽, 0.5배에서 네 쪽. 되돌아가는 일도 잦아 뒤로도 한 쪽. */
        int span = Math.max(2, Math.round(2f / Math.max(zoom, MIN_ZOOM)));
        for (int n = 1; n <= span; n++) preload(i + n);
        preload(i - 1);
    }

    /** 큐에 이미 올라간 쪽. 확대 중에는 ahead()가 연달아 불려 같은 쪽이 쌓이기 쉽다. */
    private final java.util.Set<Integer> queued = java.util.concurrent.ConcurrentHashMap.newKeySet();

    private void preload(int i) {
        if (pdf == null || i < 0 || i >= pdf.getPageCount() || cache.get(i) != null) return;
        if (!queued.add(i)) return;
        io.execute(() -> {
            try {
                /* 빨리 넘기면 미리 그리기 요청이 줄줄이 쌓인다. 그 사이 손가락은 이미
                   멀리 갔는데 지나간 쪽을 그리고 앉아 있으면, 정작 보고 있는 쪽이
                   그만큼 늦는다. 큐에서 꺼낸 시점에 다시 판단해 버린다. */
                if (Math.abs(i - focus) > 6) return;
                renderInto(i);
            } finally {
                queued.remove(i);
            }
        });
    }

    /** 캐시에 있으면 그대로, 없으면 그려서 넣는다. 렌더링 스레드에서만 부른다. */
    private Bitmap renderInto(int i) {
        Bitmap b = cache.get(i);
        if (b != null) return b;
        int w = renderW;
        if (w <= 0) return null;          // 아직 배치 전 — 크기를 모른 채 그리면 흐릿하게 굳는다
        b = render(i, w);
        if (b != null) cache.put(i, b);
        return b;
    }

    /* 렌더링 스레드에서 list.getWidth()를 읽지 않으려고 들고 있는 값. 배치가 끝난
       뒤 UI 스레드에서만 채운다. */
    private volatile int renderW;
    private volatile int focus;

    private void measureRender() {
        int w = list.getWidth();
        if (w > 0) renderW = Math.round(w * RENDER_SCALE);
    }

    /* PdfRenderer는 페이지를 한 번에 하나만 열 수 있다. 렌더링을 단일 스레드에
       몰아둔 이유가 이것이다 — 여기서만 부른다. */
    private Bitmap render(int index, int width) {
        Bitmap b = draw(index, width);
        if (b != null) return b;
        if (!lowMemory) return null;

        /* 미리 그려둔 쪽을 놓아주고 한 번만 다시 시도한다 — 지금 보는 쪽이
           미리보기보다 급하다. 사전 로딩이 생기면서 여기 닿을 일이 늘었고,
           대개 이 한 번으로 넘어간다. */
        lowMemory = false;
        cache.evictAll();
        b = draw(index, width);
        if (b == null && lowMemory)
            fail("이 자료는 너무 커서 열지 못했습니다 — '다른 앱'으로 열어 보세요");
        return b;
    }

    private volatile boolean lowMemory;

    private Bitmap draw(int index, int width) {
        try {
            if (pdf == null || index >= pdf.getPageCount()) return null;
            try (PdfRenderer.Page p = pdf.openPage(index)) {
                int h = Math.max(1, Math.round(width * (float) p.getHeight() / p.getWidth()));
                Bitmap b = Bitmap.createBitmap(width, h, Bitmap.Config.ARGB_8888);
                b.eraseColor(Color.WHITE);            // 투명 배경으로 두면 글자만 떠 보인다
                p.render(b, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                /* 비트맵은 처음 그려질 때 GPU로 올라간다. 그 일이 UI 스레드에서
                   일어나면 쪽을 넘기는 순간 그대로 걸림이 된다. 여기서 미리 올린다. */
                if (Build.VERSION.SDK_INT >= 26) b.prepareToDraw();
                return b;
            }
        } catch (OutOfMemoryError e) {
            // OOM은 Exception이 아니라 Error다 — 아래 catch로는 잡히지 않아 앱이 죽는다
            Log.w(TAG, "메모리가 모자라 페이지를 그리지 못했습니다: " + index, e);
            lowMemory = true;
            return null;
        } catch (Exception e) {
            Log.w(TAG, "페이지를 그리지 못했습니다: " + index, e);
            return null;
        }
    }
}
