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

    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        Map<String, List<Solved.Item>> log = Solved.byDay(c);
        for (int id : ids) {
            try {
                RemoteViews v = new RemoteViews(c.getPackageName(), layout());
                v.setOnClickPendingIntent(R.id.root, Widgets.open(c));
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

    /** 위젯이 지금 차지한 크기(dp). 런처가 안 알려주면 최소 크기로 친다. */
    static int[] size(AppWidgetManager m, int id, int wDefault, int hDefault) {
        try {
            Bundle o = m.getAppWidgetOptions(id);
            int w = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0);
            int h = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0);
            if (h == 0) h = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0);
            return new int[]{ w > 0 ? w : wDefault, h > 0 ? h : hDefault };
        } catch (Exception e) {
            return new int[]{wDefault, hDefault};
        }
    }

    static int color(Context c, int id) {
        return c.getResources().getColor(id, c.getTheme());
    }

    static String footer(Context c, Map<String, List<Solved.Item>> log) {
        return "수능 D-" + Widgets.dday() + " · 오늘 "
                + Solved.on(log, Solved.ymd(Calendar.getInstance())) + "회차";
    }
}
