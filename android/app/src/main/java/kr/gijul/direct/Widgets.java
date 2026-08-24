package kr.gijul.direct;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * 홈 화면 위젯들이 함께 쓰는 것.
 *
 * 위젯은 여섯 벌이고 저마다 답하는 질문이 다르다 — 달력, 이번 주, 잔디밭,
 * 최근 푼 것, D-day, 다음에 풀 것. 하나로 합치지 않은 것은 홈 화면의 자리가
 * 사람마다 달라서다. 넷을 나란히 놓는 사람도, 2×2 하나만 두는 사람도 있다.
 */
final class Widgets {

    private static final String TAG = "gijul.widget";

    private Widgets() { }

    /** 여섯 벌 전부에게 '다시 그려라'라고 이른다 */
    static void refresh(Context c) {
        Class<?>[] all = {
            CalWidget.class, WeekWidget.class, TurfWidget.class,
            RecentWidget.class, DdayWidget.class, NextWidget.class,
        };
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        for (Class<?> k : all) {
            try {
                int[] ids = m.getAppWidgetIds(new ComponentName(c, k));
                if (ids.length == 0) continue;
                Intent i = new Intent(c, k);
                i.setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE);
                i.putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids);
                c.sendBroadcast(i);
            } catch (Exception e) {
                Log.w(TAG, "위젯을 깨우지 못했습니다: " + k.getSimpleName(), e);
            }
        }
    }

    /** 위젯을 누르면 앱이 열린다. 위젯이 스스로 할 수 있는 일은 없다. */
    static PendingIntent open(Context c) {
        Intent i = new Intent(c, MainActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(c, 0, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /**
     * 수능까지 며칠. 11월 13~19일 사이의 목요일이라 해만 알면 날이 정해진다 —
     * 7일 창에 목요일은 하나뿐이다. 화면 쪽과 같은 셈이다.
     */
    static int dday() {
        java.util.Calendar now = java.util.Calendar.getInstance();
        now.set(java.util.Calendar.HOUR_OF_DAY, 0);
        now.set(java.util.Calendar.MINUTE, 0);
        now.set(java.util.Calendar.SECOND, 0);
        now.set(java.util.Calendar.MILLISECOND, 0);
        java.util.Calendar t = suneung(now.get(java.util.Calendar.YEAR));
        if (t.before(now)) t = suneung(now.get(java.util.Calendar.YEAR) + 1);
        return (int) Math.round((t.getTimeInMillis() - now.getTimeInMillis()) / 86400000.0);
    }

    private static java.util.Calendar suneung(int year) {
        java.util.Calendar c = java.util.Calendar.getInstance();
        c.clear();
        for (int d = 13; d <= 19; d++) {
            c.set(year, java.util.Calendar.NOVEMBER, d);
            if (c.get(java.util.Calendar.DAY_OF_WEEK) == java.util.Calendar.THURSDAY) return c;
        }
        c.set(year, java.util.Calendar.NOVEMBER, 19);
        return c;
    }
}
