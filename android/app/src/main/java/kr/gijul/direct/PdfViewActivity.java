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
 * 흔한 PDF 뷰어들이 쓰는 두 겹 구조를 따랐다.
 *
 *   밑그림  전 쪽을 열 때 한 번, 고정된 작은 폭으로. 어디로 넘겨도 빈 종이가 없다.
 *   본그림  보고 있는 쪽과 바로 앞뒤만, **화면에 놓일 크기와 1:1로**.
 *
 * 두 번째 줄이 중요하다. 표시될 폭보다 작게 그리면 늘려 붙이게 되고 그건 그냥 흐린
 * 화면이다. 그래서 메모리가 모자랄 때 낮추는 것은 해상도가 아니라 들고 있는 장수다.
 * 확대는 손짓 도중에는 뷰 변형으로 따라가고, 손을 뗀 뒤 그 배율로 다시 그린다.
 *
 * 축소는 1배 아래로도 내려가 양옆에 여백이 생기며, 그만큼 여러 쪽이 한눈에 들어온다.
 *
 * 정답은 PDF가 아니라 PNG라서, 같은 화면에서 한 장짜리로 보여준다.
 */
public class PdfViewActivity extends Activity {

    static final String EXTRA_URL = "url";      // 받아서 열 주소
    static final String EXTRA_FILE = "file";    // 이미 받아둔 파일의 절대 경로
    static final String EXTRA_NAME = "name";    // 표시할 이름

    private static final String TAG = "기출직행";
    private static final float MAX_ZOOM = 2.5f;
    /* 실제로 그리는 배율의 상한. 이 위로는 이미 그려둔 것을 늘려 쓴다 — 2.5배까지
       진짜 해상도로 그리면 한 장이 수십 MB가 된다. */
    private static final float MAX_RENDER_ZOOM = 2f;
    /** 한 장의 절대 상한. 아주 큰 화면에서 비트맵 하나가 힙을 삼키는 것만 막는다. */
    private static final int HARD_MAX_PX = 3000;
    /** 전 쪽 밑그림의 폭. 자리를 채우는 용도라 작고 싸야 한다. */
    private static final int THUMB_PX = 280;
    /** 한 쪽에 이만큼 머물면 흘러가는 중이라도 제 해상도로 그린다 */
    private static final long DWELL_MS = 200;
    /* 1보다 작게도 줄인다 — 양옆에 여백이 생기면서 여러 쪽이 한눈에 들어온다.
       더 줄여봐야 글자를 못 읽으니 여기서 멈춘다. */
    private static final float MIN_ZOOM = 0.5f;

    private final ExecutorService io = Executors.newSingleThreadExecutor();

    private Stage stage;
    private LinearLayout bar;
    private TextView zoomPill;
    private TextView topBtn;
    private View scrollbar;
    private boolean dragging;      // 스크롤 막대를 잡고 있는 중
    private int scrollState = RecyclerView.SCROLL_STATE_IDLE;
    private boolean chrome = true;      // 위 막대·떠 있는 단추를 보여줄지
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

        bar = new LinearLayout(this);
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

        Button full = new Button(this);
        full.setText("가리기");
        full.setTextSize(13);
        full.setAllCaps(false);
        full.setOnClickListener(v -> setChrome(false));
        bar.addView(full);

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
            @Override public void onScrolled(@NonNull RecyclerView v, int dx, int dy) { updateVisible(); }

            @Override public void onScrollStateChanged(@NonNull RecyclerView v, int state) {
                scrollState = state;
                /* 막대를 끄는 동안에는 매 프레임 IDLE로 떨어진다(scrollBy는 곧바로
                   멎으므로). 그때마다 다시 그리면 헛일이라, 놓을 때 한 번만 한다. */
                if (state == RecyclerView.SCROLL_STATE_IDLE && !dragging) resharp();
                /* 흘러가던 중에 손을 대는 것은 멈추려는 것이다. 멎기를 기다리지 않고
                   그 자리를 바로 그리기 시작한다. */
                else if (state == RecyclerView.SCROLL_STATE_DRAGGING) resharp();
            }
        });
        stage.addView(list, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        status = new TextView(this);
        status.setTextColor(ink);
        status.setGravity(Gravity.CENTER);
        status.setText("여는 중입니다…");
        stage.addView(status, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        /* 지금 배율. 눌러서 폭 맞춤과 쪽 맞춤을 오간다 — 문항을 읽을 때와 한 쪽을
           통째로 훑을 때가 서로 다른 배율이라, 그 둘 사이를 한 번에 오가는 게
           손으로 매번 집어 맞추는 것보다 빠르다. */
        zoomPill = pill("100%");
        zoomPill.setOnClickListener(v -> toggleFit());
        FrameLayout.LayoutParams zp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        zp.gravity = Gravity.TOP | Gravity.END;
        zp.setMargins(0, dp(12), dp(12), 0);
        stage.addView(zoomPill, zp);

        /* 스크롤 막대. 목록에 붙은 기본 막대는 확대 변형을 같이 받아 늘어나므로,
           변형 밖인 무대 위에 따로 둔다. 자리만 알려주면 되니 얇게. */
        scrollbar = new View(this);
        android.graphics.drawable.GradientDrawable sg = new android.graphics.drawable.GradientDrawable();
        sg.setColor(night ? 0x66EDE8DF : 0x55221F1A);
        sg.setCornerRadius(dp(3));
        /* 보이는 굵기는 5dp지만 잡히는 폭은 24dp다. 손가락으로 5dp를 겨누게 하면
           대개 빗나간다 — 안쪽을 비워 두고 그 위도 이 뷰가 받는다. */
        scrollbar.setBackground(new android.graphics.drawable.InsetDrawable(sg, dp(16), 0, dp(3), 0));
        scrollbar.setVisibility(View.GONE);
        scrollbar.setOnTouchListener(new View.OnTouchListener() {
            private float grabY;
            private int grabOffset;

            @Override
            public boolean onTouch(View v, MotionEvent e) {
                int range = list.computeVerticalScrollRange();
                int extent = list.computeVerticalScrollExtent();
                int room = range - extent;
                int track = stage.getHeight() - v.getHeight();
                if (room <= 0 || track <= 0) return false;

                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        grabY = e.getRawY();
                        grabOffset = list.computeVerticalScrollOffset();
                        dragging = true;
                        return true;
                    case MotionEvent.ACTION_MOVE: {
                        /* 막대가 지나간 거리 : 트랙 = 스크롤한 양 : 전체 */
                        int want = Math.round(grabOffset + (e.getRawY() - grabY) / track * room);
                        int now = list.computeVerticalScrollOffset();
                        list.scrollBy(0, Math.max(-now, Math.min(room - now, want - now)));
                        return true;
                    }
                    case MotionEvent.ACTION_UP:
                    case MotionEvent.ACTION_CANCEL:
                        dragging = false;
                        resharp();       // 놓은 자리를 제대로 그린다
                        return true;
                }
                return false;
            }
        });
        FrameLayout.LayoutParams sbp = new FrameLayout.LayoutParams(dp(24), 0);
        sbp.gravity = Gravity.TOP | Gravity.END;
        stage.addView(scrollbar, sbp);

        /* 뒤쪽까지 내려갔다가 처음으로 돌아오는 일이 잦다 */
        topBtn = pill("맨 위로");
        topBtn.setVisibility(View.GONE);
        topBtn.setOnClickListener(v -> {
            list.scrollToPosition(0);
            list.post(this::resharp);       // 배치가 끝나야 어디에 있는지 제대로 읽힌다
        });
        FrameLayout.LayoutParams tp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        tp.setMargins(0, 0, 0, dp(18));
        stage.addView(topBtn, tp);

        root.addView(stage, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        return root;
    }

    private TextView pill(String text) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(0xFFFFFFFF);
        t.setTextSize(12);
        t.setPadding(dp(14), dp(8), dp(14), dp(8));
        android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
        g.setColor(0xCC1A1814);
        g.setCornerRadius(dp(999));
        t.setBackground(g);
        t.setClickable(true);
        return t;
    }

    /* 화면을 가리는 것들을 치운다. 문제지는 화면이 넓을수록 읽기 쉽고, 다시 부르는
       방법이 화면을 한 번 두드리는 것이면 굳이 남겨둘 이유가 없다. */
    private void setChrome(boolean on) {
        chrome = on;
        bar.setVisibility(on ? View.VISIBLE : View.GONE);
        zoomPill.setVisibility(on ? View.VISIBLE : View.GONE);
        topBtn.setVisibility(on && visFirst > 0 ? View.VISIBLE : View.GONE);
        systemBars(on);
        stage.post(this::fitHeight);        // 무대가 커졌으니 목록 높이도 다시 잡는다
    }

    @SuppressWarnings("deprecation")
    private void systemBars(boolean on) {
        View d = getWindow().getDecorView();
        if (Build.VERSION.SDK_INT >= 30) {
            android.view.WindowInsetsController c = d.getWindowInsetsController();
            if (c == null) return;
            if (on) c.show(android.view.WindowInsets.Type.systemBars());
            else {
                c.hide(android.view.WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(android.view.WindowInsetsController
                        .BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            d.setSystemUiVisibility(on ? 0
                    : View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
    }

    /** 폭 맞춤(화면 너비에 한 쪽 폭) ↔ 쪽 맞춤(한 쪽이 통째로 들어오게) */
    private void toggleFit() {
        float target = Math.abs(zoom - 1f) < 0.02f ? pageFit() : 1f;
        zoomAt(target, stage.getWidth() / 2f, 0f);
        fitHeight();
        settlePan();
        resharp();
    }

    /** 한 쪽이 화면에 통째로 들어오는 배율. 잴 수 없으면 원래 크기로 둔다. */
    private float pageFit() {
        View v = list.getChildAt(0);
        if (v == null || v.getHeight() <= 0 || stage.getHeight() <= 0) return 1f;
        return stage.getHeight() / (float) v.getHeight();
    }

    private void syncPill() {
        if (zoomPill != null) zoomPill.setText(Math.round(zoom * 100) + "%");
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
        private boolean toButton;       // 이번 터치가 떠 있는 단추 몫인지

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
                    resharp();
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
                    resharp();      // 확대한 만큼 선명도를 올린다
                }
            });
            tap = new GestureDetector(a, new GestureDetector.SimpleOnGestureListener() {
                @Override
                public boolean onSingleTapConfirmed(MotionEvent e) {
                    setChrome(!chrome);      // 가려둔 것을 다시 부르는 유일한 길
                    return true;
                }
                @Override
                public boolean onDoubleTap(MotionEvent e) {
                    zoomAt(zoom > 1.2f ? 1f : 2f, e.getX(), e.getY());
                    fitHeight();
                    resharp();
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
            /* 떠 있는 단추 위에서 시작한 터치는 손짓 감지기에 넣지 않는다. 넣으면 한 번
               두드림으로도 세어져, 단추를 누르는 순간 그 단추가 사라진다.
               판단은 손가락이 닿는 순간에 한 번만 한다 — 매번 다시 보면 손짓 도중에
               단추 위를 지나가는 것만으로 주인이 바뀐다. */
            if (e.getActionMasked() == MotionEvent.ACTION_DOWN) toButton = onButton(e);
            if (toButton) {
                if (e.getActionMasked() == MotionEvent.ACTION_UP
                        || e.getActionMasked() == MotionEvent.ACTION_CANCEL) toButton = false;
                return super.dispatchTouchEvent(e);
            }

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

        private boolean onButton(MotionEvent e) {
            return hits(zoomPill, e) || hits(topBtn, e) || hits(scrollbar, e);
        }

        private boolean hits(View v, MotionEvent e) {
            if (v == null || v.getVisibility() != View.VISIBLE) return false;
            return e.getX() >= v.getLeft() && e.getX() <= v.getRight()
                    && e.getY() >= v.getTop() && e.getY() <= v.getBottom();
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
        syncPill();
        list.setPivotX(0f);
        list.setPivotY(0f);
        list.setScaleX(zoom);
        list.setScaleY(zoom);
        list.setTranslationX(panX);
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    /**
     * 지금 화면에 무엇이 있는지 다시 잡는다.
     *
     * 예전에는 이 값을 항목이 붙을 때 정했는데, 붙는 순서는 화면 순서가 아니라서
     * 결국 '마지막으로 붙은 쪽'이 기준이 됐다. 그 기준으로 요청을 걸러내니, 정작
     * 보고 있는 쪽의 요청이 버려지는 일이 생겼다 — 될 때도 있고 안 될 때도 있던
     * 이유가 이것이다. 기준은 스크롤 위치에서 온다.
     */
    private void updateVisible() {
        RecyclerView.Adapter<?> a = list.getAdapter();
        LinearLayoutManager lm = (LinearLayoutManager) list.getLayoutManager();
        if (a == null || lm == null) return;
        int f = lm.findFirstVisibleItemPosition();
        int l = lm.findLastVisibleItemPosition();
        if (f == RecyclerView.NO_POSITION) return;
        visFirst = f;
        visLast = l == RecyclerView.NO_POSITION ? f : l;

        syncScrollbar();
        dwell();

        if (a.getItemCount() <= 1) return;
        int i = lm.findFirstCompletelyVisibleItemPosition();
        if (i == RecyclerView.NO_POSITION) i = f;
        pageLabel.setText((i + 1) + " / " + a.getItemCount());
        pageLabel.setVisibility(View.VISIBLE);
        topBtn.setVisibility(chrome && i > 0 ? View.VISIBLE : View.GONE);
    }

    // ── 읽어들이기 ──────────────────────────────────────────────────────

    private void fetch(String url) {
        try {
            /* 이미 '받아둔 자료'에 있으면 그걸 쓴다 — 같은 파일을 두 번 받을 이유가 없다 */
            File saved = findSaved(nameOf(url));
            if (saved != null) { load(saved); return; }

            File dir = new File(getCacheDir(), "view");
            if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("임시 폴더를 만들지 못했습니다");
            File to = new File(dir, MainActivity.safe(nameOf(url)));
            if (!to.isFile() || to.length() == 0) {
                HttpURLConnection c = (HttpURLConnection) new URL(MainActivity.fromEbsi(url)).openConnection();
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
                measurePages();      // 높이를 먼저 확정해야 배치가 흔들리지 않는다
            }
            runOnUiThread(() -> {
                status.setVisibility(View.GONE);
                list.setAdapter(new Pages());
                list.post(() -> {
                    measureRender();
                    updateVisible();
                    /* 첫 쪽은 폭을 재기 전에 붙었을 수 있다. 그때 건 요청은 폭을
                       몰라 그냥 돌아섰으므로, 여기서 한 번 더 건다. */
                    resharp();
                    drawThumbs();     // 배치가 끝나야 폭을 알고, 폭을 알아야 밑그림을 깐다
                });
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
        // 화면 너비가 달라졌으니 그려둔 쪽은 전부 크기가 맞지 않는다
        sharp.evictAll();
        base.clear();
        renderW = 0;
        list.post(() -> { measureRender(); drawThumbs(); });
        if (list.getAdapter() != null) list.getAdapter().notifyDataSetChanged();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
        stopSettle();
        sharp.evictAll();
        base.clear();
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
            /* adjustViewBounds를 쓰면 높이가 비트맵에서 나온다. 밑그림을 본그림으로
               갈아 끼울 때마다 높이가 1px씩 달라지고, 그때마다 배치가 돌면서 넘기던
               손이 멈춘다. 높이는 쪽의 가로세로비로 미리 정해두고 여기서는 안 건드린다. */
            iv.setAdjustViewBounds(false);
            /* FIT_XY는 칸에 맞춰 잡아늘인다 — 높이 계산이 한 번이라도 어긋나면
               그림이 찌그러진다. FIT_CENTER는 비율을 지키고 남는 데를 비운다. */
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
        private int shownW;        // 지금 붙어 있는 비트맵의 폭. 더 좁은 것으로 바꾸지 않으려고.

        Page(ImageView iv) { super(iv); this.iv = iv; }

        void show(int i) {
            clear();
            shown = i;
            measureRender();
            if (image != null) {
                /* 정답은 한 장짜리 이미지다. 여기서도 높이를 정해줘야 한다 —
                   빠뜨렸더니 폭만 가득 늘어나고 높이는 원본 픽셀에 머물러
                   세로로 눌린 그림이 나왔다. */
                fixHeight(image.getHeight() / (float) image.getWidth());
                set(image);
                return;
            }
            fixHeight(ratio(i));
            /* 붙는다는 건 화면에 들어온다는 뜻이다. 배치가 끝나야 갱신되는 값을
               기다리면, 방금 넘어온 쪽의 요청이 옛 범위에 걸려 버려질 수 있다. */
            if (i < visFirst) visFirst = i;
            if (i > visLast) visLast = i;

            /* 선명한 것이 있으면 그걸로. 없으면 밑그림을 먼저 깔아 빈 종이를 없애고,
               선명한 쪽은 뒤이어 덮어쓴다. */
            Bitmap s = sharp.get(i);
            if (s != null && s.getWidth() >= wantW() * 0.95f) {
                set(s);
            } else {
                Bitmap l = base.get(i);
                if (l != null) set(l);
                /* 흘러가는 중에는 걸지 않는다. 지나갈 쪽을 제 해상도로 그리느라
                   렌더링 스레드가 붙잡히면 그 무게가 넘기는 손에 그대로 온다.
                   멎거나, 잡거나, 한자리에 머물면 그때 건다. */
                if (scrollState == RecyclerView.SCROLL_STATE_IDLE) askSharp(i);
            }
        }

        /**
         * 다 그려진 비트맵을 꽂는다.
         *
         * 지금 붙어 있는 것보다 좁으면 물린다. 이게 없으면 전 쪽 밑그림이 나중에
         * 완성되면서 이미 제대로 그려진 쪽을 280px짜리로 덮어쓴다 — 열자마자 첫 쪽이
         * 뭉개져 보이던 것이 바로 이것이었다.
         */
        void put(int i, Bitmap b) {
            if (shown == i && b.getWidth() >= shownW) set(b);
        }

        private void set(Bitmap b) { shownW = b.getWidth(); iv.setImageBitmap(b); }

        /** 가로세로비로 높이를 못박는다. 그림이 바뀌어도 배치는 그대로다. */
        private void fixHeight(float r) {
            int w = renderW > 0 ? renderW : 720;
            int h = Math.round(w * r);
            ViewGroup.LayoutParams lp = iv.getLayoutParams();
            if (lp.height != h) { lp.height = h; iv.setLayoutParams(lp); }
        }

        void clear() { iv.setImageDrawable(null); shownW = 0; }
    }

    /* ── 두 겹으로 그린다 ────────────────────────────────────────────────
     *
     * 문제지는 길어야 스무 쪽 남짓이라 전부 미리 그려도 된다. 열 때 모든 쪽을 낮은
     * 해상도로 한 번 훑어 두면 어디로 넘겨도 빈 종이가 없다. 그 위에 지금 보는 쪽만
     * 제 해상도로 덮어쓰고, 확대하면 그 배율에 맞춰 다시 그린다.
     *
     * 밑그림은 문서를 닫을 때까지 들고 있는다 — 다 합쳐도 선명한 쪽 두 장 값이다.
     */
    private final java.util.Map<Integer, Bitmap> base = new java.util.concurrent.ConcurrentHashMap<>();

    /* 제 해상도로 그려둔 쪽. 한 장이 십수 MB라 개수가 아니라 바이트로 한도를 잡는다.
       비트맵을 직접 recycle하지 않는 이유는, 아직 화면에 걸린 것을 지우면 그 자리에서
       죽기 때문이다. 한도를 지키는 쪽이 훨씬 안전하다. */
    private final android.util.LruCache<Integer, Bitmap> sharp =
            new android.util.LruCache<Integer, Bitmap>(
                    (int) Math.min(Runtime.getRuntime().maxMemory() / 3, Integer.MAX_VALUE)) {
                @Override protected int sizeOf(Integer k, Bitmap b) { return b.getByteCount(); }
            };

    /**
     * 지금 그려야 할 폭. 화면에 실제로 놓일 크기와 1:1이다.
     *
     * 이 값을 캐시 크기로 깎았던 것이 뭉개짐의 원인이었다. 표시될 폭보다 작게 그리면
     * 늘려서 붙이게 되고, 그건 그냥 흐린 화면이다. 메모리가 모자라면 해상도를 낮출
     * 게 아니라 **들고 있는 장수**를 줄여야 한다 — 지금 보는 쪽은 언제나 제 크기로.
     *
     * 축소했을 때는 1배로 그린다. 줄여 그려봐야 다시 키울 때 흐릴 뿐이다.
     */
    private int wantW() {
        if (renderW <= 0) return 0;
        /* 표시될 크기 그대로. 줄였으면 줄여 그리는 것이 1:1이고, 그래야 여러 쪽이
           보이는 축소 상태에서도 전부 제대로 그릴 여유가 생긴다. */
        float z = Math.max(MIN_ZOOM, Math.min(zoom, MAX_RENDER_ZOOM));
        int want = Math.min(Math.round(renderW * z), HARD_MAX_PX);

        /* 확대해서 얻는 선명도는 힙이 감당하는 만큼만 가져간다 — 두 장은 들 수 있어야
           앞뒤로 넘길 때 매번 다시 그리지 않는다. 다만 바닥은 renderW다. 1배 화면에서
           표시 폭보다 작게 그리는 일만은 없어야 한다. 그게 뭉개짐이다. */
        int afford = (int) Math.sqrt((sharp.maxSize() / 2.0) / (1.45 * 4));
        return Math.max(Math.round(renderW * MIN_ZOOM), Math.min(want, afford));
    }

    /**
     * 이 쪽을 제 해상도로 맞춘다.
     *
     * 같은 쪽의 요청이 이미 큐에 있어도 버리지 않는다. 예전에는 버렸는데, 그러면
     * 나중에 온 요청이 담고 있던 '지금 화면에 붙여라'라는 뜻까지 같이 사라졌다.
     * 겹쳐도 손해가 없다 — 먼저 온 쪽이 캐시를 채우고, 나머지는 아래의 적중 경로로
     * 빠지면서 화면에만 붙인다.
     */
    private void askSharp(int i) {
        if (pdf == null || i < 0 || i >= pdf.getPageCount()) return;
        io.execute(() -> {
            if (i < visFirst - 1 || i > visLast + 1) return;   // 그 사이 화면이 옮겨갔다
            int w = wantW();
            if (w <= 0) return;
            Bitmap b = sharp.get(i);
            if (b != null && b.getWidth() >= w * 0.95f) {
                /* 캐시에 있다고 그냥 돌아서면 안 된다. 그려둔 것과 화면에 붙어 있는
                   것은 다른 이야기다 — 캐시에는 선명한 게 있는데 화면은 밑그림인 채로
                   굳는 자리가 여기서 생겼다. */
                post(i, b);
                return;
            }
            b = render(i, w);
            if (b != null) { sharp.put(i, b); post(i, b); }
        });
    }

    /**
     * 다 그렸으니 그 쪽이 아직 화면에 있으면 갈아 끼운다.
     *
     * 여기서 show()를 다시 부르면 안 된다. show()는 캐시를 다시 보고 없으면 또
     * 요청을 거는데, 그 사이 방금 넣은 것이 밀려났으면 같은 요청이 무한히 되풀이된다.
     * 손에 든 비트맵을 그냥 꽂는다.
     */
    private void post(int i, Bitmap b) {
        list.post(() -> {
            RecyclerView.ViewHolder h = list.findViewHolderForAdapterPosition(i);
            if (h instanceof Page) ((Page) h).put(i, b);
        });
    }

    /**
     * 화면에 있는 쪽 전부와 바로 앞뒤를 제 해상도로 맞춘다.
     *
     * 줄이면 한 화면에 여러 쪽이 들어오는데, 그때 보이는 쪽 중 하나만 제대로 그리면
     * 나머지는 밑그림인 채로 남는다. 대신 줄인 만큼 한 장이 작아지므로(표시 크기와
     * 1:1) 여러 장을 그려도 비용은 오히려 준다.
     */
    private void resharp() {
        /* 배치가 끝난 뒤에 읽어야 한다. 목록 높이를 바꾸면 재배치는 다음 차례로
           미뤄지는데, 그 전에 범위를 읽으면 축소해서 새로 드러난 쪽들이 범위 밖으로
           판정돼 요청이 통째로 버려진다. */
        list.post(() -> {
            updateVisible();
            for (int i = visFirst - 1; i <= visLast + 1; i++) askSharp(i);
        });
    }

    /* 렌더링 스레드에서 list.getWidth()를 읽지 않으려고 들고 있는 값. 배치가 끝난
       뒤 UI 스레드에서만 채운다. */
    private volatile int renderW;
    private volatile int visFirst, visLast;

    /**
     * 화면에 오래 머문 쪽을 그린다.
     *
     * 기준은 '맨 위 쪽이 안 바뀐 시간'이 아니라 **쪽마다 화면에 머문 시간의 합**이다.
     * 14·15가 함께 보이다가 15·16이 함께 보이는 식으로 넘어가면 맨 위 쪽은 계속
     * 바뀌지만 15는 그 내내 화면에 있었다 — 그런 쪽이 실은 제일 오래 보고 있는
     * 쪽인데, 맨 위 쪽만 보는 기준으로는 한 번도 걸리지 않았다.
     *
     * 화면을 벗어나면 0으로 돌아간다. 스쳐 지나간 시간이 쌓여 나중에 엉뚱한 쪽이
     * 걸리는 일이 없도록.
     */
    private void dwell() {
        if (pdf == null) return;
        int n = pdf.getPageCount();
        if (seen == null || seen.length != n) seen = new long[n];

        long now = android.os.SystemClock.uptimeMillis();
        /* 손을 놓고 한참 뒤에 다시 움직인 공백까지 머문 시간으로 세면 안 된다 —
           한 프레임 몫으로 자른다. */
        long dt = tick == 0 ? 0 : Math.min(now - tick, 250);
        tick = now;

        for (int i = 0; i < n; i++) {
            if (i < visFirst || i > visLast) { seen[i] = 0; continue; }
            if (seen[i] < 0) continue;                 // 이미 걸어둔 쪽
            seen[i] += dt;
            if (seen[i] >= DWELL_MS) { seen[i] = -1; askSharp(i); }
        }
    }

    private long[] seen;       // 쪽마다 화면에 머문 시간(ms). -1이면 이미 요청했다.
    private long tick;

    /**
     * 스크롤 막대를 지금 위치에 맞춘다.
     *
     * 길이와 위치는 목록이 알려주는 비율로만 정한다 — 목록 좌표가 배율에 따라
     * 달라져도 '전체 중 어디쯤'은 그대로라서, 확대 상태와 무관하게 맞는다.
     */
    private void syncScrollbar() {
        if (scrollbar == null || stage.getHeight() <= 0) return;
        int range = list.computeVerticalScrollRange();
        int extent = list.computeVerticalScrollExtent();
        if (range <= extent || extent <= 0) { scrollbar.setVisibility(View.GONE); return; }

        int track = stage.getHeight();
        int h = Math.max(dp(28), Math.round(track * (float) extent / range));
        int max = range - extent;
        int y = max <= 0 ? 0
                : Math.round((track - h) * Math.min(1f, list.computeVerticalScrollOffset() / (float) max));

        ViewGroup.LayoutParams lp = scrollbar.getLayoutParams();
        if (lp.height != h) { lp.height = h; scrollbar.setLayoutParams(lp); }
        scrollbar.setTranslationY(y);
        scrollbar.setVisibility(View.VISIBLE);
    }

    /* 쪽마다의 가로세로비. 그리지 않고 크기만 읽으므로 문서를 열 때 한 번에 끝난다.
       탐구는 A3, 국어는 A4지만 비율은 둘 다 1.41이라 실제로는 거의 같은 값이다. */
    private volatile float[] ratio;

    private float ratio(int i) {
        float[] r = ratio;
        if (r == null || i < 0 || i >= r.length || r[i] <= 0) return 1.414f;
        return r[i];
    }

    private void measurePages() {
        if (pdf == null) return;
        float[] r = new float[pdf.getPageCount()];
        for (int i = 0; i < r.length; i++) {
            try (PdfRenderer.Page p = pdf.openPage(i)) {
                r[i] = p.getWidth() > 0 ? p.getHeight() / (float) p.getWidth() : 1.414f;
            } catch (Exception e) { r[i] = 1.414f; }
        }
        ratio = r;
    }

    /** 표시 폭. 그리는 크기의 기준이므로 곱하지 않고 그대로 쓴다. */
    private void measureRender() {
        int w = list.getWidth();
        if (w > 0) renderW = w;
    }

    /**
     * 전 쪽의 밑그림. 문서를 열 때 한 번만 돈다.
     *
     * 폭이 고정이라 쪽수와 무관하게 한 장에 0.5MB가 채 안 된다. 예전에는 예산을
     * 쪽수로 나눠 정했는데, 그러면 쪽이 적은 자료일수록 한 장이 커지는 거꾸로 된
     * 일이 벌어졌다 — 이건 자리를 채우는 용도지 읽으라고 있는 게 아니다.
     */
    private void drawThumbs() {
        if (pdf == null) return;
        int n = pdf.getPageCount();
        if (n <= 0 || renderW <= 0) return;

        for (int i = 0; i < n; i++) {
            final int at = i;
            io.execute(() -> {
                if (base.containsKey(at)) return;
                Bitmap b = draw(at, THUMB_PX);
                if (b != null) { base.put(at, b); post(at, b); }
            });
        }
    }

    /* PdfRenderer는 페이지를 한 번에 하나만 열 수 있다. 렌더링을 단일 스레드에
       몰아둔 이유가 이것이다 — 여기서만 부른다. */
    private Bitmap render(int index, int width) {
        Bitmap b = draw(index, width);
        if (b != null) return b;
        if (!lowMemory) return null;

        /* 선명한 쪽들을 놓아주고 한 번만 다시 시도한다 — 지금 보는 쪽이 미리
           그려둔 것보다 급하다. 밑그림은 남긴다. 그게 빈 종이를 막는 마지막 보루고,
           다 합쳐도 선명한 쪽 두 장 값이라 여기서 얻을 것도 별로 없다. */
        lowMemory = false;
        sharp.evictAll();
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
