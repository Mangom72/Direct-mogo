package kr.gijul.direct;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.graphics.pdf.PdfRenderer;
import android.hardware.input.InputManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.util.Log;
import android.util.LruCache;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 문제지를 다른 앱 위에 반투명하게 띄워 두는 창.
 *
 * 쓰임은 하나다 — 노트앱에 풀이를 적으면서 문제지를 겹쳐 보는 것. 그래서 종이는
 * 터치를 통과시키고(아래 앱에 그대로 필기된다), 조작할 것들만 따로 받는다.
 *
 * <h3>창을 셋으로 나눈 까닭</h3>
 * 터치 통과는 창 단위 깃발(FLAG_NOT_TOUCHABLE)이라 한 창의 일부만 통과시킬 수
 * 없다. 그런데 통과하는 창에는 손을 댈 수 없으니 닫지도 옮기지도 못한다. 그래서
 * <b>바</b>(위)와 <b>손잡이</b>(좌하단)는 늘 터치를 받는 별개의 창으로 두고,
 * 가운데 <b>종이</b>만 설정에 따라 통과시킨다. 셋은 언제나 같이 움직인다.
 *
 * <h3>투명도 상한이 있는 까닭</h3>
 * 안드로이드 12부터 시스템은 <b>합산 불투명도가 0.8을 넘는 오버레이를 지나는
 * 터치를 차단한다.</b> 우리가 고를 수 있는 것이 아니라 기기 OS가 정하는 것이고,
 * targetSdk 와도 무관하다. 그래서 통과 모드에서는 슬라이더가 그 값을 넘지 못한다
 * — 넘겨 두면 창은 보이는데 아래 앱이 터치를 못 받아 "왜 필기가 안 되지"가 된다.
 * 조작 모드에서는 우리 창이 터치를 먹으므로 상한이 없다.
 *
 * <h3>확대·축소 뒤의 유예</h3>
 * ＋/－ 로 키우고 나면 대개 보고 싶은 자리로 끌어 옮기고 싶어진다. 그때마다
 * 모드를 오갔다가 되돌리는 건 번거로우니, 누른 뒤 잠깐 동안은 종이가 터치를
 * 받는다. <b>끌기가 시작된 뒤에 시간이 다 되어도 그 끌기는 끝까지 반영한다</b> —
 * 손가락이 닿아 있는 채로 창을 통과 모드로 되돌리면 하던 동작이 도중에 끊긴다.
 */
public class FloatService extends Service {

    static final String TAG = "gijul.float";
    static final String EXTRA_FILE = "file";
    static final String EXTRA_NAME = "name";
    static final String EXTRA_URL = "url";      // 목록에서 '지금 보는 중'을 가리기 위해
    static final String ACTION_STOP = "kr.gijul.direct.FLOAT_STOP";

    private static final String CHANNEL = "float";
    private static final int NOTE_ID = 71;

    private static final int MIN_OPACITY = 20;    // 더 내리면 글자가 안 보이고 창도 잃는다
    private static final int DEF_OPACITY = 65;
    private static final float DEF_CAP = 0.8f;    // API 31 미만에서 쓸 기본 상한

    private WindowManager wm;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private View bar, grip;
    private PaperView paper;
    private WindowManager.LayoutParams barLp, paperLp, gripLp;
    private TextView pctBubble;
    private Slider slider;
    private TextView menuBtn;
    private android.widget.FrameLayout content;   // 종이와 목록이 같은 자리를 나눠 쓴다
    private PickerView picker;
    private Catalog catalog;
    private boolean pickerOpen;
    private boolean passBefore;                   // 목록을 열기 전 모드
    private String showingUrl;                    // 지금 보고 있는 자료의 주소
    private int imeLift;                          // 자판을 피해 올려 둔 만큼
    private TextView minBtn;
    private GradientDrawable barBg;
    private boolean minimized;
    private final ExecutorService fetch = Executors.newSingleThreadExecutor();
    private TextView passBtn, holdBtn;

    /* 창 자리. 셋이 이 하나를 나눠 쓴다. */
    private int wx, wy, ww, wh;
    private int barH, gripPx;

    private boolean full = true;      // 아직 사용자가 크기를 건드리지 않았다
    private boolean passThrough = true;
    private int opacity = DEF_OPACITY;
    private boolean paperTouched = false;          // 종이에 손가락이 닿아 있는가

    private String name = "";

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        String path = intent == null ? null : intent.getStringExtra(EXTRA_FILE);
        String n = intent == null ? null : intent.getStringExtra(EXTRA_NAME);
        if (path == null) { stopSelf(); return START_NOT_STICKY; }
        name = n == null ? "" : n;
        String u = intent.getStringExtra(EXTRA_URL);
        if (u != null && !u.isEmpty()) showingUrl = u;

        note();
        if (bar == null) build();
        if (paper != null) paper.open(new File(path));
        return START_NOT_STICKY;
    }

    // ── 알림 ────────────────────────────────────────────────────────────
    //
    // 포그라운드 서비스라 알림을 뗄 수 없다. 그렇다면 쓸모라도 있어야 하므로
    // '닫기'를 단다 — 창을 화면 밖으로 밀어 손잡이를 잃어버려도 여기서 걷는다.

    private void note() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(CHANNEL) == null) {
            NotificationChannel c = new NotificationChannel(
                    CHANNEL, "띄워 둔 문제지", NotificationManager.IMPORTANCE_LOW);
            c.setShowBadge(false);
            nm.createNotificationChannel(c);
        }
        Intent stop = new Intent(this, FloatService.class).setAction(ACTION_STOP);
        PendingIntent pi = PendingIntent.getService(this, 0, stop,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        Notification note = b.setSmallIcon(R.drawable.ic_float)
                .setContentTitle(name.isEmpty() ? "문제지를 띄워 두었습니다" : name)
                .setContentText("탭하면 닫습니다")
                .setContentIntent(pi)
                .setOngoing(true)
                .build();

        /* specialUse 는 API 34에서 생긴 유형이다. 그 아래에 넘기면 모르는 값이라
           거부될 수 있으므로, 유형을 요구하는 판에서만 붙인다. */
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTE_ID, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTE_ID, note);
        }
    }

    // ── 창 만들기 ───────────────────────────────────────────────────────

    private int dp(float v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private boolean night() {
        int m = getResources().getConfiguration().uiMode
                & android.content.res.Configuration.UI_MODE_NIGHT_MASK;
        return m == android.content.res.Configuration.UI_MODE_NIGHT_YES;
    }

    private void build() {
        wm = getSystemService(WindowManager.class);
        barH = dp(44);
        gripPx = dp(34);

        defaultGeometry();

        catalog = new Catalog(getCacheDir());
        paper = new PaperView(this);
        content = new android.widget.FrameLayout(this);
        content.setFocusableInTouchMode(true);
        content.setOnKeyListener((v, code, ev) -> {
            if (code != KeyEvent.KEYCODE_BACK || ev.getAction() != KeyEvent.ACTION_UP) return false;
            if (!pickerOpen) return false;
            if (!picker.back()) closePicker();     // 과목 목록이면 목록 자체를 닫는다
            return true;
        });
        content.addView(paper, new android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        bar = buildBar();
        grip = buildGrip();

        paperLp = lp(ww, wh - barH);
        barLp = lp(ww, barH);
        gripLp = lp(gripPx, gripPx);

        wm.addView(content, paperLp);
        wm.addView(bar, barLp);
        wm.addView(grip, gripLp);
        watchIme();
        place();
        applyMode();
    }

    /**
     * 처음 열릴 때의 자리와 크기.
     *
     * 폰에서는 화면 너비를 그대로 쓴다 — 문제지는 세로로 길고 글자가 작아서
     * 옆을 남기면 그만큼 못 읽는다.
     *
     * 다만 넓은 화면에서 그대로 늘리면 거꾸로 읽기 나빠진다. 종이는 창 너비에
     * 맞춰 그려지므로(zoom 1 = 폭 맞춤) 태블릿에서 폭을 다 쓰면 **한 쪽이 창
     * 높이보다 훨씬 커져 윗동강만 들어온다.** 게다가 화면을 통째로 덮어서,
     * 옆에 두고 쓰는 창이 아니라 그냥 큰 창이 된다. 그래서 읽기 좋은 폭까지만
     * 쓰고 가운데에 놓는다. 더 넓게 쓰고 싶으면 손잡이로 늘리면 된다.
     */
    private void defaultGeometry() {
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        ww = Math.min(dm.widthPixels, dp(560));
        wh = Math.min(dp(560), (int) (dm.heightPixels * 0.6f));
        wx = (dm.widthPixels - ww) / 2;
        wy = dp(72);
    }

    /**
     * 창을 화면 안으로 밀어 넣는다.
     *
     * 이걸 안 하면 벽에 닿았을 때 <b>손잡이만 따로 움직인다.</b> 창 셋의 y가
     * 저마다 다른데(바는 위, 손잡이는 아래) 화면 밖으로 나가는 창은 시스템이
     * 알아서 붙잡아 두므로, 이미 붙잡힌 바·종이는 서면서 아직 여유가 있는
     * 작은 손잡이만 계속 내려간다. 우리가 먼저 묶어 두면 셋이 함께 선다.
     */
    private void clampWindow() {
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        ww = Math.min(ww, dm.widthPixels);
        wh = Math.min(wh, dm.heightPixels);
        wx = Math.max(0, Math.min(wx, dm.widthPixels - ww));
        wy = Math.max(0, Math.min(wy, Math.max(0, dm.heightPixels - wh)));
    }

    private WindowManager.LayoutParams lp(int w, int h) {
        int type = Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
        WindowManager.LayoutParams p = new WindowManager.LayoutParams(w, h, type,
                /* 초점을 받지 않는다 — 받으면 아래 앱의 입력기가 내려간다 */
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        /* 우리 창 밖의 터치는 우리 것이 아니다 */
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        p.gravity = Gravity.TOP | Gravity.START;
        /* 자판이 뜰 때 시스템이 창을 밀어 올리게 두지 않는다.
           미는 것은 **초점을 쥔 창 하나**뿐이라, 목록을 열어 글자를 치면
           종이만 위로 뛰고 바와 손잡이는 제자리에 남아 셋이 흩어졌다.
           밀 자리는 우리가 정하고(imeLift), 셋을 함께 옮긴다. */
        p.softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING;
        return p;
    }

    /** 세 창을 현재 자리에 맞춰 다시 놓는다. 옮기든 크기를 바꾸든 여기 하나로 끝난다. */
    /**
     * 끌 때 쓰는 자리 갱신.
     *
     * 터치는 화면 주사율보다 빨리 들어온다(요즘 기기는 두세 배). 그때마다
     * place() 를 부르면 창 셋에 대고 초당 수백 번 IPC 를 날리는 셈이라, 창들이
     * 서로 다른 프레임에 도착해 <b>따로 노는 것처럼 보이고</b> 끌기도 끊긴다.
     * 프레임마다 한 번으로 묶으면 셋이 같은 프레임에 함께 움직인다.
     */
    private boolean placeQueued;
    private void placeSoon() {
        if (placeQueued) return;
        placeQueued = true;
        android.view.Choreographer.getInstance().postFrameCallback(t -> {
            placeQueued = false;
            place();
        });
    }

    private void place() {
        clampWindow();
        final int y = wy - imeLift;      // 자판이 떴으면 셋이 함께 그만큼 올라간다
        barLp.x = wx;              barLp.y = y;               barLp.width = ww; barLp.height = barH;
        paperLp.x = wx;            paperLp.y = y + barH;      paperLp.width = ww;
        paperLp.height = Math.max(dp(80), wh - barH);
        gripLp.x = wx;             gripLp.y = y + wh - gripPx;
        try {
            wm.updateViewLayout(bar, barLp);
            wm.updateViewLayout(content, paperLp);
            wm.updateViewLayout(grip, gripLp);
        } catch (Exception e) { Log.w(TAG, "자리 갱신 실패", e); }
    }

    // ── 위쪽 설정 바 ────────────────────────────────────────────────────

    private View buildBar() {
        final boolean night = night();
        final int ink = night ? 0xFFECE7DA : 0xFF221F1A;
        final int bg  = night ? 0xFF161A22 : 0xFFF3F1EC;

        FrameLayout wrap = new FrameLayout(this);
        barBg = new GradientDrawable();
        barBg.setColor(bg);
        wrap.setBackground(barBg);
        roundBar();

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(8), 0, dp(8), 0);
        wrap.addView(row, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        /* 통과 | 조작 — 켬/끔 스위치로 두면 '켜짐'이 어느 쪽인지 헷갈린다.
           두 낱말을 나란히 놓고 지금 것을 칠하면 읽을 것이 없다. */
        LinearLayout seg = new LinearLayout(this);
        seg.setOrientation(LinearLayout.HORIZONTAL);
        GradientDrawable segBg = new GradientDrawable();
        segBg.setColor(night ? 0x1FECE7DA : 0x17221F1A);
        segBg.setCornerRadius(dp(8));
        seg.setBackground(segBg);
        menuBtn = chip("☰", night, v -> togglePicker());
        LinearLayout.LayoutParams mlp = new LinearLayout.LayoutParams(dp(30), dp(30));
        mlp.rightMargin = dp(7);
        row.addView(menuBtn, mlp);

        passBtn = segItem("통과");
        holdBtn = segItem("조작");
        passBtn.setOnClickListener(v -> setPass(true));
        holdBtn.setOnClickListener(v -> setPass(false));
        seg.addView(passBtn); seg.addView(holdBtn);
        row.addView(seg);

        slider = new Slider(this, night);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(0, dp(30), 1f);
        slp.leftMargin = dp(8); slp.rightMargin = dp(10);
        row.addView(slider, slp);

        View sep = new View(this);
        sep.setBackgroundColor(night ? 0x29ECE7DA : 0x24221F1A);
        LinearLayout.LayoutParams sepLp = new LinearLayout.LayoutParams(dp(1), dp(18));
        sepLp.leftMargin = dp(6); sepLp.rightMargin = dp(4);
        row.addView(sep, sepLp);

        /* 창틀 단추 둘 — 접기와 닫기. 바탕을 지워 다른 조작과 구별한다.
           이것들은 창 자체를 어찌하는 것이지 문제지를 어찌하는 것이 아니다. */
        minBtn = chip("－", night, v -> setMin(!minimized));
        minBtn.setBackground(null);
        minBtn.setTextColor(night ? 0x99ECE7DA : 0x99221F1A);
        row.addView(minBtn, chipLp());

        TextView close = chip("✕", night, v -> stopSelf());
        close.setBackground(null);
        close.setTextColor(night ? 0x99ECE7DA : 0x99221F1A);
        row.addView(close, chipLp());

        /* 상시로 두면 ☰ 자리가 없다. 손잡이 위치로도 대강 읽히므로 끄는
           동안에만 눈금을 띄운다. 바가 44dp뿐이라 위로 못 올리고 슬라이더
           오른쪽 끝에 얹는다. */
        pctBubble = new TextView(this);
        pctBubble.setTextSize(11);
        pctBubble.setTypeface(null, android.graphics.Typeface.BOLD);
        pctBubble.setTextColor(night ? 0xFF161A22 : 0xFFF3F1EC);
        pctBubble.setPadding(dp(6), dp(1), dp(6), dp(1));
        GradientDrawable bub = new GradientDrawable();
        bub.setColor(ink);
        bub.setCornerRadius(dp(6));
        pctBubble.setBackground(bub);
        pctBubble.setVisibility(View.GONE);
        wrap.addView(pctBubble, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER_VERTICAL | Gravity.START));

        wrap.setOnTouchListener(new DragMove());
        updateBar();
        return wrap;
    }

    private LinearLayout.LayoutParams chipLp() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(30), dp(30));
        p.leftMargin = dp(6);
        return p;
    }

    private TextView segItem(String label) {
        TextView t = new TextView(this);
        t.setText(label);
        t.setTextSize(12);
        t.setTypeface(null, android.graphics.Typeface.BOLD);
        t.setPadding(dp(11), dp(5), dp(11), dp(5));
        return t;
    }

    private TextView chip(String label, boolean night, View.OnClickListener on) {
        TextView t = new TextView(this);
        t.setText(label);
        t.setTextSize(14);
        t.setTypeface(null, android.graphics.Typeface.BOLD);
        t.setGravity(Gravity.CENTER);
        t.setTextColor(night ? 0xFFECE7DA : 0xFF221F1A);
        GradientDrawable g = new GradientDrawable();
        g.setColor(night ? 0x1AECE7DA : 0x12221F1A);
        g.setCornerRadius(dp(8));
        t.setBackground(g);
        t.setOnClickListener(on);
        return t;
    }

    private void updateBar() {
        boolean night = night();
        int on = night ? 0xFF161A22 : 0xFFF3F1EC;
        int onBg = night ? 0xFFECE7DA : 0xFF221F1A;
        int off = night ? 0x8CECE7DA : 0x8C221F1A;
        for (int i = 0; i < 2; i++) {
            TextView t = i == 0 ? passBtn : holdBtn;
            boolean sel = (i == 0) == passThrough;
            if (sel) {
                GradientDrawable g = new GradientDrawable();
                g.setColor(onBg);
                g.setCornerRadius(dp(8));
                t.setBackground(g);
                t.setTextColor(on);
            } else {
                t.setBackground(null);
                t.setTextColor(off);
            }
        }
        if (pctBubble != null) pctBubble.setText(opacity + "%");
        /* 값만 고치고 말면 슬라이더는 옛 자리를 그대로 그리고 있는다. 조작에서
           100을 찍고 통과로 돌아오면 상한까지 깎이는데, 손잡이는 100에 남아
           있어서 만지기 전까지 어긋난 채로 보였다. */
        if (slider != null) slider.invalidate();
    }

    // ── 좌하단 손잡이 ───────────────────────────────────────────────────

    private View buildGrip() {
        final boolean night = night();
        View v = new View(this) {
            private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
            /* 그리는 동안에는 아무것도 새로 만들지 않는다 — 이 창은 남의 앱 위에서
               계속 떠 있으므로 프레임마다 쓰레기를 남기면 그 부담이 그쪽에 간다. */
            private final android.graphics.Path path = new android.graphics.Path();
            private final RectF arc = new RectF();
            @Override protected void onDraw(Canvas c) {
                float t = dp(6);
                p.setStyle(Paint.Style.STROKE);
                p.setStrokeCap(Paint.Cap.ROUND);
                p.setStrokeJoin(Paint.Join.ROUND);
                float pad = t / 2f + dp(2);
                path.rewind();
                path.moveTo(pad, dp(4));
                path.lineTo(pad, getHeight() - pad - dp(6));
                arc.set(pad, getHeight() - pad - dp(12), pad + dp(12), getHeight() - pad);
                path.arcTo(arc, 180, -90);
                path.lineTo(getWidth() - dp(4), getHeight() - pad);
                /* 이 손잡이는 앱 화면이 아니라 **문제지 위**에 얹힌다. 시스템
                   테마를 따라가게 두었더니 어두운 화면에서 밝은 획이 되어 흰
                   종이에 묻혀 버렸다 — 그래서 안 보였다.
                   종이가 흰 것에 맞춰 어둡게 그리되, 그림·표처럼 검은 자리에
                   걸려도 살아남도록 흰 테를 먼저 깔고 그 위에 얹는다. 어느
                   바탕이든 둘 중 하나는 보인다. 바탕색을 재어 갈아 끼우는
                   방법도 있지만, 넘길 때마다 색이 바뀌어 깜빡인다. */
                p.setStrokeWidth(t + dp(3));
                p.setColor(0xE6FFFFFF);
                c.drawPath(path, p);
                p.setStrokeWidth(t);
                p.setColor(0xF2151310);
                c.drawPath(path, p);
            }
        };
        v.setOnTouchListener(new DragResize());
        return v;
    }

    // ── 모드·투명도·확대 ────────────────────────────────────────────────

    /** 이 기기가 허용하는 최대 불투명도. 통과가 되려면 이 아래여야 한다. */
    private float cap() {
        if (Build.VERSION.SDK_INT >= 31) {
            try {
                InputManager im = getSystemService(InputManager.class);
                if (im != null) return im.getMaximumObscuringOpacityForTouch();
            } catch (Exception e) { Log.w(TAG, "상한을 묻지 못했습니다", e); }
        }
        return DEF_CAP;
    }

    private int capPct() { return Math.max(MIN_OPACITY, Math.round(cap() * 100)); }

    private void setPass(boolean on) {
        passThrough = on;
        if (on && opacity > capPct()) opacity = capPct();   // 상한 밖이면 끌어내린다
        updateBar();
        applyMode();
    }

    private void setOpacity(int pct) {
        int max = passThrough ? capPct() : 100;
        int v = Math.max(MIN_OPACITY, Math.min(max, pct));
        if (v == opacity) return;          // 상한에 붙은 채로 계속 끌 때가 대부분이다
        opacity = v;
        updateBar();
        applyMode();
    }

    private final Runnable hidePct = () -> {
        if (pctBubble != null) pctBubble.setVisibility(View.GONE);
    };

    private void showPct(final View sliderView) {
        if (pctBubble == null) return;
        ui.removeCallbacks(hidePct);
        pctBubble.setText(opacity + "%");
        pctBubble.setVisibility(View.VISIBLE);
        /* 슬라이더 오른쪽 끝에 붙인다. 손잡이를 따라다니게 하면 손가락에
           가려서, 정작 읽으려는 숫자가 안 보인다. */
        pctBubble.post(() -> pctBubble.setTranslationX(
                sliderView.getX() + sliderView.getWidth() - pctBubble.getWidth()));
    }


    /**
     * 지금 종이가 터치를 받아야 하는가.
     *
     * paperTouched 를 함께 보는 것은 끌던 도중에 '통과'로 바뀌는 경우 때문이다.
     * 그 자리에서 터치를 끊으면 하던 동작이 반쯤에서 사라진다 — 손을 뗄 때까지는
     * 계속 받고, 마지막 손가락이 떨어진 뒤에 되돌린다.
     */
    private boolean live() {
        return !passThrough || paperTouched;
    }

    private void applyMode() {
        if (paperLp == null) return;
        int f = WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL;
        float a;
        if (pickerOpen) {
            /* 목록은 글자를 받아야 한다 — 초점을 잡지 않으면 자판이 붙지 않는다.
               읽으라고 띄운 것이니 그동안은 투명도도 걷는다. */
            a = 1f;
        } else {
            f |= WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
            if (!live()) f |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
            /* 통과 모드에서는 상한을 넘길 수 없다 — 넘기면 아래 앱이 터치를 못 받는다. */
            int pct = passThrough ? Math.min(opacity, capPct()) : opacity;
            a = pct / 100f;
        }
        /* 값이 그대로면 넘기지 않는다. applyMode() 는 슬라이더를 끄는 동안에도
           터치마다 불리는데, 같은 값을 다시 실어 보내는 것은 그냥 낭비다. */
        if (paperLp.flags == f && Math.abs(paperLp.alpha - a) < 0.001f) return;
        paperLp.flags = f;
        paperLp.alpha = a;
        try { wm.updateViewLayout(content, paperLp); }
        catch (Exception e) { Log.w(TAG, "종이 갱신 실패", e); }
    }

    // ── 접기 ────────────────────────────────────────────────────────────

    /**
     * 바만 남기고 접는다.
     *
     * 다른 앱을 잠깐 통째로 봐야 할 때가 있다. 그때마다 닫았다가 다시 띄우면
     * 보던 자리와 배율을 잃는다 — 종이와 손잡이의 창만 감추면 그대로 있다가
     * 그 자리로 돌아온다.
     *
     * 창을 지우지 않고 보이기만 끄는 까닭이 그것이다. WindowManager 에 붙은
     * 뷰는 VISIBLE 이 아니면 그리는 면을 내리므로, 자리도 차지하지 않고
     * 터치도 받지 않는다.
     */
    private void setMin(boolean on) {
        minimized = on;
        if (on && pickerOpen) closePicker();
        minBtn.setText(on ? "＋" : "－");
        content.setVisibility(on ? View.GONE : View.VISIBLE);
        grip.setVisibility(on ? View.GONE : View.VISIBLE);
        roundBar();
        place();
        applyMode();
    }

    /** 접었으면 바 혼자 뜨므로 네 귀가 다 둥글고, 폈으면 아래는 종이와 잇는다. */
    private void roundBar() {
        if (barBg == null) return;
        float r = dp(12), b = minimized ? r : 0;
        barBg.setCornerRadii(new float[]{r, r, r, r, b, b, b, b});
    }

    // ── 자판 ────────────────────────────────────────────────────────────

    /**
     * 자판에 가려지지 않을 만큼만 창 셋을 함께 올린다.
     *
     * 창이 남은 자리보다 크면 위로는 더 못 간다 — 그때는 화면 맨 위까지만
     * 올리고 아래가 가려지는 것을 받아들인다. 목록은 위에서부터 읽는 것이라
     * 찾는 칸과 첫 줄들이 살아남는 편이 낫다.
     *
     * 안드로이드 11부터 자판 높이를 물어볼 수 있다. 그 아래에서는 0으로 두는데,
     * 그러면 아무것도 움직이지 않는다 — 셋이 흩어지는 것보다야 낫다.
     */
    private void onIme(int imeH) {
        int want = 0;
        if (imeH > 0) {
            int free = getResources().getDisplayMetrics().heightPixels - imeH;
            want = Math.min(Math.max(0, wy + wh - free), wy);
        }
        if (want == imeLift) return;
        imeLift = want;
        place();
    }

    private void watchIme() {
        if (Build.VERSION.SDK_INT < 30 || content == null) return;
        content.setOnApplyWindowInsetsListener((v, in) -> {
            onIme(in.getInsets(android.view.WindowInsets.Type.ime()).bottom);
            return in;
        });
    }

    /**
     * 손으로 옮기거나 크기를 바꾸기 직전에, 올려 둔 만큼을 제자리로 친다.
     *
     * 그러지 않으면 창은 올라가 있는데 셈은 원래 자리로 하므로, 잡는 순간
     * 창이 손가락 아래로 뚝 떨어진다. 여기서 지금 보이는 자리를 그대로
     * 사용자의 자리로 삼으면 손을 따라온다.
     */
    private void settle() {
        if (imeLift == 0) return;
        wy -= imeLift;
        imeLift = 0;
    }

    /** 목록을 닫으면 자판도 함께 내린다. 남겨 두면 아래 앱 위에 혼자 떠 있는다. */
    private void dropIme() {
        try {
            android.view.inputmethod.InputMethodManager im =
                    getSystemService(android.view.inputmethod.InputMethodManager.class);
            if (im != null && content != null && content.getWindowToken() != null)
                im.hideSoftInputFromWindow(content.getWindowToken(), 0);
        } catch (Exception e) { Log.w(TAG, "자판을 내리지 못했습니다", e); }
        if (imeLift != 0) { imeLift = 0; place(); }
    }

    // ── 목록 ────────────────────────────────────────────────────────────

    private void togglePicker() {
        if (pickerOpen) closePicker(); else openPicker();
    }

    private void openPicker() {
        if (content == null) return;
        if (minimized) setMin(false);      // 접힌 채로 열면 목록이 감춰진 창에 뜬다
        if (picker == null) {
            picker = new PickerView(this, catalog, new PickerView.Host() {
                @Override public void pick(Catalog.Paper p, int kind) { load(p, kind); }
                @Override public String showing() { return showingUrl; }
            }, night());
            content.addView(picker, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        }
        /* 목록은 만져야 하니 조작으로 바꾸고, 고르고 나면 있던 자리로 돌린다.
           통과로 되돌리는 것을 사용자가 기억할 일이 아니다. */
        passBefore = passThrough;
        passThrough = false;
        pickerOpen = true;
        picker.setVisibility(View.VISIBLE);
        content.requestFocus();
        markMenu(true);
        updateBar();
        applyMode();
        picker.enter();
    }

    private void closePicker() {
        pickerOpen = false;
        dropIme();
        if (picker != null) picker.setVisibility(View.GONE);
        passThrough = passBefore;
        markMenu(false);
        updateBar();
        applyMode();
    }

    private void markMenu(boolean on) {
        if (menuBtn == null) return;
        boolean night = night();
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(8));
        g.setColor(on ? (night ? 0xFFECE7DA : 0xFF221F1A) : (night ? 0x1AECE7DA : 0x12221F1A));
        menuBtn.setBackground(g);
        menuBtn.setTextColor(on ? (night ? 0xFF161A22 : 0xFFF3F1EC)
                                : (night ? 0xFFECE7DA : 0xFF221F1A));
    }

    /** 고른 자료를 연다. 이미 받아 둔 것이면 받는 화면 없이 바로 뜬다. */
    private void load(final Catalog.Paper p, final int kind) {
        final String url = p.url(kind);
        if (url == null || url.isEmpty()) return;
        final String label = p.title + " " + Catalog.KIND[kind];
        closePicker();
        paper.busy(label + " 받는 중…");
        fetch.execute(() -> {
            try {
                final java.io.File f = catalog.paper(url);
                ui.post(() -> {
                    showingUrl = url;
                    name = label;
                    paper.open(f);
                    note();                    // 알림에 뜨는 이름도 따라간다
                });
            } catch (Exception e) {
                Log.w(TAG, "받지 못했습니다: " + url, e);
                ui.post(() -> paper.busy("받지 못했습니다 — 연결을 확인해 주십시오"));
            }
        });
    }

    // ── 끌기 ────────────────────────────────────────────────────────────

    /** 바를 끌면 창이 통째로 움직인다. 바가 곧 손잡이다. */
    private class DragMove implements View.OnTouchListener {
        private float ox, oy; private int sx, sy;
        @Override public boolean onTouch(View v, MotionEvent e) {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    settle();
                    ox = e.getRawX(); oy = e.getRawY(); sx = wx; sy = wy; return true;
                case MotionEvent.ACTION_MOVE:
                    wx = sx + (int) (e.getRawX() - ox);
                    wy = sy + (int) (e.getRawY() - oy);
                    placeSoon(); return true;
            }
            return false;
        }
    }

    /** 좌하단 손잡이 — 왼쪽 모서리와 아래 모서리를 끈다. */
    private class DragResize implements View.OnTouchListener {
        private float ox, oy; private int sx, sw, sh;
        @Override public boolean onTouch(View v, MotionEvent e) {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    settle();
                    ox = e.getRawX(); oy = e.getRawY(); sx = wx; sw = ww; sh = wh; return true;
                case MotionEvent.ACTION_MOVE:
                    int dx = (int) (e.getRawX() - ox), dy = (int) (e.getRawY() - oy);
                    int w = Math.max(dp(200), sw - dx);
                    int h = Math.max(dp(140), sh + dy);
                    wx = sx + (sw - w);                 // 오른쪽 모서리는 제자리에 둔다
                    ww = w; wh = h; full = false;
                    placeSoon(); return true;
            }
            return false;
        }
    }

    // ── 투명도 슬라이더 ─────────────────────────────────────────────────

    private class Slider extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final boolean night;
        Slider(Context c, boolean night) { super(c); this.night = night; }

        @Override protected void onDraw(Canvas c) {
            float cy = getHeight() / 2f, r = dp(2), knob = dp(7.5f);
            float x0 = knob, x1 = getWidth() - knob, span = x1 - x0;
            p.setStyle(Paint.Style.FILL);
            p.setColor(night ? 0x38ECE7DA : 0x2E221F1A);
            c.drawRoundRect(x0, cy - r, x1, cy + r, r, r, p);

            /* 통과 모드에서 갈 수 없는 구간을 빗금으로 보인다. "80%까지"라고
               띄우는 것보다, 못 가는 자리를 눈에 보이게 두는 편이 낫다. */
            if (passThrough && capPct() < 100) {
                float lx = x0 + span * capPct() / 100f;
                p.setColor(night ? 0x55ECE7DA : 0x40221F1A);
                for (float x = lx; x < x1; x += dp(5)) {
                    c.drawRect(x, cy - r, Math.min(x + dp(2), x1), cy + r, p);
                }
            }
            float px = x0 + span * (opacity - MIN_OPACITY) / (float) (100 - MIN_OPACITY);
            p.setColor(0xFFB4342A);
            c.drawRoundRect(x0, cy - r, Math.max(x0, px), cy + r, r, r, p);
            c.drawCircle(px, cy, knob, p);
        }

        @Override public boolean onTouchEvent(MotionEvent e) {
            float knob = dp(7.5f), x0 = knob, span = getWidth() - knob * 2;
            if (span <= 0) return true;
            float t = (e.getX() - x0) / span;
            setOpacity(Math.round(MIN_OPACITY + t * (100 - MIN_OPACITY)));
            invalidate();
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                case MotionEvent.ACTION_MOVE: showPct(this); break;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL: ui.postDelayed(hidePct, 700); break;
            }
            return true;
        }
    }

    // ── 종이 ────────────────────────────────────────────────────────────

    /**
     * 페이지를 세로로 이어 그린다. 뷰어(PdfViewActivity)와 달리 캐시도 밑그림도
     * 얇게 간다 — 이 창은 남의 앱 위에서 오래 떠 있으므로, 화면을 다 채우는
     * 뷰어와 같은 무게로 들고 있을 이유가 없다.
     */
    private class PaperView extends View {
        private ParcelFileDescriptor fd;
        private PdfRenderer pdf;
        private Bitmap still;                       // 정답은 PNG로 온다
        private float[] ratio = new float[0];       // 쪽마다 높이 ÷ 너비
        private float zoom = 1f;
        private int scrollY, scrollX;
        private final ExecutorService render = Executors.newSingleThreadExecutor();
        private final LruCache<Integer, Bitmap> cache = new LruCache<Integer, Bitmap>(4) {
            @Override protected int sizeOf(Integer k, Bitmap b) { return 1; }
        };
        /* 늘려 그리는 동안(핀칭 중)에는 원래 폭과 어긋난다. 필터를 켜 두면
           그때 모난 계단 대신 부드럽게 흐려져서, 다시 그려질 때까지의 몇
           프레임이 눈에 덜 거슬린다. */
        private final Paint dim = new Paint(Paint.FILTER_BITMAP_FLAG);
        private final android.graphics.Rect at = new android.graphics.Rect();
        /* onDraw 는 프레임마다 돈다. 아직 안 그려진 쪽을 그때마다 새로 시키면
           같은 일이 큐에 수십 개씩 쌓여, 정작 지금 보이는 쪽이 뒤로 밀린다. */
        private final java.util.Set<Integer> inFlight =
                java.util.Collections.synchronizedSet(new java.util.HashSet<Integer>());
        private int cachedTotalH, cachedForW = -1;
        /* 쪽마다 어느 폭으로 그려 두었는지. 폭이 달라졌다고 그림을 버리면
           다시 그려질 때까지 흰 바탕이 보인다 — 있는 것을 늘려 쓰다가,
           새것이 준비되면 그때 갈아 끼운다. */
        private final java.util.Map<Integer, Integer> madeAt =
                java.util.Collections.synchronizedMap(new java.util.HashMap<Integer, Integer>());
        private boolean sharpen;

        /* 받는 동안 종이 대신 뜨는 한 줄. 다 받으면 open() 이 지운다. */
        private String msg;
        private final Paint say = new Paint(Paint.ANTI_ALIAS_FLAG);

        /* 창 크기를 바꾸는 동안에는 예전 폭으로 그린 쪽이 늘어난 채로 보인다.
           끌고 있는 내내 다시 그리면 렌더 스레드가 밀리므로, 손이 멎은 뒤에
           한 번만 새로 그린다. */
        private final Runnable resharp = () -> { sharpen = true; invalidate(); };

        @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
            super.onSizeChanged(w, h, ow, oh);
            if (w != ow) {
                removeCallbacks(resharp);
                postDelayed(resharp, 180);
            }
            clamp();
        }

        PaperView(Context c) {
            super(c);
            setBackgroundColor(Color.WHITE);
            say.setColor(0xFF6B7280);
            say.setTextSize(dp(14));
            say.setTextAlign(Paint.Align.CENTER);
        }

        /** 자료를 받아오는 동안 그 자리에 한 줄만 띄운다. */
        void busy(String text) {
            close();
            synchronized (FloatService.this) {
                ratio = new float[0];
                inFlight.clear();
                madeAt.clear();
                cachedForW = -1;
                scrollY = scrollX = 0;
                zoom = 1f;
            }
            msg = text;
            postInvalidate();
        }

        void open(File f) {
            close();
            try {
              synchronized (FloatService.this) {
                String n = f.getName().toLowerCase();
                if (n.endsWith(".png") || n.endsWith(".jpg")) {
                    still = BitmapFactory.decodeFile(f.getAbsolutePath());
                    ratio = new float[]{ still == null ? 1.4f
                            : still.getHeight() / (float) still.getWidth() };
                } else {
                    fd = ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
                    pdf = new PdfRenderer(fd);
                    ratio = new float[pdf.getPageCount()];
                    for (int i = 0; i < ratio.length; i++) {
                        try (PdfRenderer.Page p = pdf.openPage(i)) {
                            ratio[i] = p.getHeight() / (float) p.getWidth();
                        }
                    }
                }
                msg = null;
                scrollY = scrollX = 0;
                cache.evictAll();
                inFlight.clear();
                madeAt.clear();
                cachedForW = -1;
              }
                postInvalidate();
            } catch (Exception e) {
                Log.w(TAG, "띄울 자료를 열지 못했습니다: " + f, e);
                stopSelf();
            }
        }

        /* 렌더 스레드가 같은 pdf 를 붙들고 있다. 닫는 쪽도 같은 자물쇠를 잡지
           않으면 그리는 도중에 닫혀 죽는다. */
        void close() {
            synchronized (FloatService.this) {
                cache.evictAll();
                try { if (pdf != null) pdf.close(); } catch (Exception ignore) {}
                try { if (fd != null) fd.close(); } catch (Exception ignore) {}
                pdf = null; fd = null; still = null;
            }
        }

        /**
         * (fx, fy) 아래에 있던 자리를 그대로 두고 배율만 바꾼다.
         *
         * 그냥 배율만 올리면 왼쪽 위로 밀린다 — ＋를 누르면 화면 가운데가,
         * 손가락 둘로 벌리면 그 사이가 제자리에 있어야 보던 곳을 잃지 않는다.
         */
        void zoomAt(float want, float fx, float fy) {
            float z = Math.max(1f, Math.min(4f, want));
            if (Math.abs(z - zoom) < 0.001f) return;
            float k = z / zoom;
            scrollX = Math.round((scrollX + fx) * k - fx);
            scrollY = Math.round((scrollY + fy) * k - fy);
            zoom = z;
            cachedForW = -1;
            clamp();
            invalidate();
            /* 핀칭 중에 매번 다시 그리라고 하면 렌더가 밀린다. 손이 멎은 뒤에
               한 번만 또렷하게 한다. 그동안은 있는 그림을 늘려 쓴다. */
            removeCallbacks(resharp);
            postDelayed(resharp, 180);
        }

        private int contentW() { return Math.max(1, (int) (getWidth() * zoom)); }

        /* 끌 때마다 clamp() 가 부르는 자리다. 폭이 그대로면 답도 그대로다. */
        private int totalH() {
            int w = contentW();
            if (w == cachedForW) return cachedTotalH;
            int h = 0;
            for (float r : ratio) h += (int) (w * r) + dp(6);
            cachedForW = w;
            cachedTotalH = Math.max(1, h);
            return cachedTotalH;
        }

        private void clamp() {
            scrollX = Math.max(0, Math.min(scrollX, contentW() - getWidth()));
            scrollY = Math.max(0, Math.min(scrollY, Math.max(0, totalH() - getHeight())));
        }

        @Override protected void onDraw(Canvas c) {
            if (msg != null) {
                c.drawText(msg, getWidth() / 2f,
                        getHeight() / 2f - (say.ascent() + say.descent()) / 2f, say);
                return;
            }
            int w = contentW();
            if (ratio.length == 0) return;
            int y = -scrollY;
            for (int i = 0; i < ratio.length; i++) {
                int ph = (int) (w * ratio[i]);
                if (y + ph > 0 && y < getHeight()) {
                    Bitmap b = still != null ? still : cache.get(i);
                    if (b != null) {
                        /* 폭이 달라졌으면 늘려서 그린다. 잠깐 흐릴지언정
                           비어 보이지는 않는다. */
                        at.set(-scrollX, y, -scrollX + w, y + ph);
                        c.drawBitmap(b, null, at, dim);
                    }
                    if (b == null || sharpen) want(i, w);
                }
                y += ph + dp(6);
                if (y > getHeight()) {
                    sharpen = false;
                    /* 다음 쪽을 미리 그려 둔다. 스크롤이 그 자리에 닿았을 때
                       흰 종이만 보이다 뒤늦게 채워지는 것이 끊겨 보이는 원인이다. */
                    want(i + 1, w);
                    break;
                }
            }
            sharpen = false;
        }

        private void want(final int i, final int w) {
            if (pdf == null || i < 0 || i >= ratio.length) return;
            final int target = Math.min(w, 1600);
            /* 이미 그 폭으로 들고 있으면 할 일이 없다. 그림이 밀려나 사라졌다면
               madeAt 에 자국이 남아 있어도 다시 그린다. */
            if (cache.get(i) != null && Integer.valueOf(target).equals(madeAt.get(i))) return;
            if (!inFlight.add(i)) return;
            render.execute(() -> {
                if (cache.get(i) != null) { inFlight.remove(i); return; }
                try {
                    Bitmap b;
                    synchronized (FloatService.this) {
                        if (pdf == null) return;
                        try (PdfRenderer.Page p = pdf.openPage(i)) {
                            int bw = target;
                            int bh = Math.max(1, (int) (bw * ratio[i]));
                            b = Bitmap.createBitmap(bw, bh, Bitmap.Config.ARGB_8888);
                            b.eraseColor(Color.WHITE);
                            p.render(b, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                        }
                    }
                    cache.put(i, b);
                    madeAt.put(i, target);
                    postInvalidate();
                } catch (Exception e) {
                    Log.w(TAG, "쪽을 그리지 못했습니다: " + i, e);
                } finally {
                    inFlight.remove(i);
                }
            });
        }

        private float lx, ly;
        private final ScaleGestureDetector pinch = new ScaleGestureDetector(
                FloatService.this, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector d) {
                zoomAt(zoom * d.getScaleFactor(), d.getFocusX(), d.getFocusY());
                return true;
            }
        });

        @Override public boolean onTouchEvent(MotionEvent e) {
            pinch.onTouchEvent(e);
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    paperTouched = true;
                    lx = e.getX(); ly = e.getY();
                    return true;
                /* 손가락이 늘거나 줄면 기준점을 다시 잡는다. 그러지 않으면 그
                   순간 좌표가 튀어 화면이 한 번 껑충 뛴다. */
                case MotionEvent.ACTION_POINTER_DOWN:
                case MotionEvent.ACTION_POINTER_UP:
                    lx = e.getX(); ly = e.getY();
                    return true;
                case MotionEvent.ACTION_MOVE:
                    if (!pinch.isInProgress() && e.getPointerCount() == 1) {
                        scrollY -= (int) (e.getY() - ly);
                        scrollX -= (int) (e.getX() - lx);
                        clamp(); invalidate();
                    }
                    lx = e.getX(); ly = e.getY();
                    return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    paperTouched = false;
                    /* 끌기가 끝났다. 그 사이 통과로 바뀌었다면 여기서 비로소
                       되돌아간다 — 손가락이 닿아 있는 동안은 미뤄 두었다. */
                    applyMode();
                    return true;
            }
            return false;
        }
    }

    // ── 끝 ──────────────────────────────────────────────────────────────

    /**
     * 화면이 돌거나 크기가 바뀌면 창을 다시 맞춘다.
     *
     * 처음에 화면 너비로 열어 두므로 이걸 안 하면 가로로 돌렸을 때 옆이 뭉텅
     * 남는다. 사용자가 손잡이로 줄인 뒤라면 그 크기를 존중하되, 화면 밖으로
     * 나가지만 않게 안으로 밀어 넣는다 — 밖으로 나가면 잡을 수가 없다.
     */
    @Override
    public void onConfigurationChanged(android.content.res.Configuration c) {
        super.onConfigurationChanged(c);
        if (wm == null || bar == null) return;
        if (full) defaultGeometry();     // 아직 손대지 않았으면 새 화면에 맞춰 다시
        place();                         // 손댄 뒤라면 크기는 지키고 안으로만 민다
    }

    @Override
    public void onDestroy() {
        ui.removeCallbacks(hidePct);
        try { if (picker != null) picker.shutdown(); } catch (Exception ignore) {}
        fetch.shutdownNow();
        try { if (paper != null) paper.close(); } catch (Exception ignore) {}
        try { if (content != null) wm.removeView(content); } catch (Exception ignore) {}
        try { if (bar != null) wm.removeView(bar); } catch (Exception ignore) {}
        try { if (grip != null) wm.removeView(grip); } catch (Exception ignore) {}
        bar = grip = null; paper = null; content = null;
        super.onDestroy();
    }
}
