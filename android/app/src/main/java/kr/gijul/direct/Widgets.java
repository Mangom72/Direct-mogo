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

    /**
     * 위젯을 누르면 앱이 <b>그 위젯이 말하던 자리</b>로 열린다.
     *
     * 푼 것을 보여 주던 위젯은 달력으로, 회차를 짚어 주던 위젯은 그 과목으로.
     * 갈 데가 마땅치 않으면 첫 화면이다. 홈 화면에서 눌렀는데 아무 데나 열리면
     * 위젯을 놓아 둔 값이 절반은 사라진다.
     *
     * 자리는 주소의 조각(#…)으로 건넨다 — 페이지가 이미 그것으로 화면을 되살린다.
     *
     * @param where 조각. null 이면 첫 화면.
     * @param slot  같은 위젯 안에서 누른 자리마다 다른 PendingIntent 를 만들려면
     *              요청 코드가 달라야 한다. 같으면 마지막 것이 앞의 것을 덮는다.
     */
    static PendingIntent open(Context c, String where, int slot) {
        Intent i = new Intent(c, MainActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (where != null) i.putExtra("gijul_frag", where);
        /* 조각을 데이터에도 실어 둔다. 이것이 없으면 안드로이드가 '같은 인텐트'로
           보아 FLAG_UPDATE_CURRENT 로도 앞의 것을 안 갈아 끼운다 — 달력 위젯과
           D-day 위젯이 같은 곳으로 열리는 그 버그다. */
        i.setData(android.net.Uri.parse("gijul://widget/" + slot + (where == null ? "" : where)));
        return PendingIntent.getActivity(c, slot, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static PendingIntent open(Context c) { return open(c, null, 0); }

    /** 달력을 펴고 연다 */
    static final String CAL = "#cal";

    /** 그 과목의 목록으로 */
    static String subject(String grade, String sub) {
        return "#/" + grade + "/" + sub + "/all/all";
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
