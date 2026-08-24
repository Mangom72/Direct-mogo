package kr.gijul.direct;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.RemoteViews;

import java.util.Calendar;
import java.util.List;
import java.util.Map;

/**
 * 위젯 여섯 벌이 함께 지고 있는 것.
 *
 * <h3>스스로 깨어나지 않는다</h3>
 * {@code updatePeriodMillis} 는 0이다. 표시가 바뀌는 것은 <b>페이지를 열었을
 * 때뿐</b>이고 그때 앱이 직접 깨우므로, 30분마다 일어나 같은 그림을 다시 그릴
 * 까닭이 없다. 배터리는 그런 데서 샌다.
 *
 * 다만 <b>날은 저절로 바뀐다.</b> '오늘'과 D-day 와 이번 주가 자정에 어긋나므로,
 * 자정에 한 번만 깨우는 알람을 스스로 걸어 둔다.
 */
abstract class WidgetBase extends AppWidgetProvider {

    private static final String TAG = "gijul.widget";
    static final String ACTION_MIDNIGHT = "kr.gijul.direct.MIDNIGHT";

    /** 한 벌을 그린다. 자료는 이미 읽어 두었다. */
    abstract void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
                       Map<String, List<Solved.Item>> log);

    abstract int layout();

    /** 이 위젯을 누르면 갈 자리. null 이면 첫 화면. */
    String where() { return null; }

    /** PendingIntent 를 서로 구별하는 번호. 위젯마다 달라야 한다. */
    int slot() { return getClass().getName().hashCode() & 0xFFFF; }

    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        Map<String, List<Solved.Item>> log = Solved.byDay(c);
        for (int id : ids) {
            try {
                RemoteViews v = new RemoteViews(c.getPackageName(), layout());
                /* 위젯마다 가는 곳이 다르다. 누르는 자리가 여럿인 위젯은
                   draw() 안에서 줄마다 다시 건다. */
                v.setOnClickPendingIntent(R.id.root, Widgets.open(c, where(), slot()));
                draw(c, m, id, v, log);
                m.updateAppWidget(id, v);
            } catch (Exception e) {
                Log.w(TAG, "위젯을 그리지 못했습니다", e);
            }
        }
        midnight(c, true);
    }

    /* 크기가 바뀌면 그림도 다시 그려야 한다 — 한 장으로 그린 것들이 늘어난다 */
    @Override
    public void onAppWidgetOptionsChanged(Context c, AppWidgetManager m, int id, Bundle o) {
        onUpdate(c, m, new int[]{id});
    }

    @Override
    public void onReceive(Context c, Intent i) {
        super.onReceive(c, i);
        if (!ACTION_MIDNIGHT.equals(i.getAction())) return;
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        onUpdate(c, m, m.getAppWidgetIds(new ComponentName(c, getClass())));
    }

    @Override
    public void onDisabled(Context c) {
        midnight(c, false);                     // 마지막 하나를 떼면 알람도 거둔다
    }

    private void midnight(Context c, boolean on) {
        try {
            AlarmManager am = c.getSystemService(AlarmManager.class);
            Intent i = new Intent(c, getClass()).setAction(ACTION_MIDNIGHT);
            PendingIntent p = PendingIntent.getBroadcast(c, 0, i,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
                            | (on ? 0 : PendingIntent.FLAG_NO_CREATE));
            if (!on) {
                if (p != null && am != null) { am.cancel(p); p.cancel(); }
                return;
            }
            if (am == null) return;
            Calendar t = Calendar.getInstance();
            t.add(Calendar.DAY_OF_MONTH, 1);
            t.set(Calendar.HOUR_OF_DAY, 0);
            t.set(Calendar.MINUTE, 1);
            t.set(Calendar.SECOND, 0);
            /* 정확할 필요가 없다. 몇 분 늦어도 '오늘'이 하루 어긋나지는 않는다 —
               정확한 알람을 쓰면 안드로이드 12부터 따로 권한을 물어야 한다. */
            am.set(AlarmManager.RTC, t.getTimeInMillis(), p);
        } catch (Exception e) {
            Log.w(TAG, "자정 알람을 걸지 못했습니다", e);
        }
    }

    // ── 그리는 데 쓰는 것 ───────────────────────────────────────────────

    static int px(Context c, float dp) {
        return Math.round(dp * c.getResources().getDisplayMetrics().density);
    }

    /**
     * 위젯이 <b>지금</b> 차지한 크기(dp). 런처가 안 알려주면 최소 크기로 친다.
     *
     * <h3>네 값 중 둘을 골라야 한다</h3>
     * 런처가 주는 것은 한 크기가 아니라 넷이다 — MIN_WIDTH·MAX_HEIGHT 가
     * <b>세로일 때</b>의 크기이고, MAX_WIDTH·MIN_HEIGHT 가 <b>가로일 때</b>다.
     * 짝을 섞으면 세로의 너비에 세로의 높이를 재는 대신 세로 너비에 가로 높이를
     * 재게 되어, 비율이 어긋난 그림을 늘여 붙이게 된다. 태블릿을 가로로 두면
     * 글자가 옆으로 늘어나 보이던 것이 이것이었다.
     *
     * 안드로이드 12부터는 아예 목록으로 준다(OPTION_APPWIDGET_SIZES). 그쪽이
     * 있으면 그것을 쓴다 — 런처가 실제로 재 놓은 값이라 가장 정확하다.
     */
    static int[] size(Context c, AppWidgetManager m, int id, int wDefault, int hDefault) {
        try {
            Bundle o = m.getAppWidgetOptions(id);
            boolean land = c.getResources().getConfiguration().orientation
                    == android.content.res.Configuration.ORIENTATION_LANDSCAPE;
            if (android.os.Build.VERSION.SDK_INT >= 31) {
                java.util.List<android.util.SizeF> all =
                        o.getParcelableArrayList(AppWidgetManager.OPTION_APPWIDGET_SIZES);
                if (all != null && !all.isEmpty()) {
                    /* 목록은 보통 [세로, 가로] 두 벌이다. 가로면 넓은 쪽을 고른다. */
                    android.util.SizeF pick = all.get(0);
                    for (android.util.SizeF x : all) {
                        boolean wider = x.getWidth() > pick.getWidth();
                        if (land == wider) pick = x;
                    }
                    return new int[]{Math.round(pick.getWidth()), Math.round(pick.getHeight())};
                }
            }
            int w = o.getInt(land ? AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH
                                  : AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0);
            int h = o.getInt(land ? AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT
                                  : AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0);
            if (w == 0) w = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0);
            if (h == 0) h = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0);
            return new int[]{ w > 0 ? w : wDefault, h > 0 ? h : hDefault };
        } catch (Exception e) {
            return new int[]{wDefault, hDefault};
        }
    }

    /**
     * 그림에 쓸 글꼴. 진짜 글자로 내는 위젯은 layout 의 fontFamily 가 맡고,
     * 한 장으로 그리는 위젯은 이것으로 맞춘다 — 한 위젯 안에서 두 글꼴이
     * 섞이면 그림 부분만 남의 앱처럼 보인다.
     */
    static android.graphics.Typeface font(Context c, boolean bold) {
        try {
            return androidx.core.content.res.ResourcesCompat.getFont(
                    c, bold ? R.font.gijul_700 : R.font.gijul_500);
        } catch (Exception e) {
            return android.graphics.Typeface.defaultFromStyle(
                    bold ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
        }
    }

    /** 칸 크기에 맞춰 자란다. 고정 dp 로 두면 큰 화면에서 글자만 남아 작아 보인다. */
    static float fit(Context c, float span, float ratio, float min, float max) {
        return Math.max(px(c, min), Math.min(px(c, max), span * ratio));
    }

    static int color(Context c, int id) {
        return c.getResources().getColor(id, c.getTheme());
    }

    static String footer(Context c, Map<String, List<Solved.Item>> log) {
        return "수능 D-" + Widgets.dday() + " · 오늘 "
                + Solved.on(log, Solved.ymd(Calendar.getInstance())) + "회차";
    }
}
