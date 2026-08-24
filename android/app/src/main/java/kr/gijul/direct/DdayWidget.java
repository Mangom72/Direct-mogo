package kr.gijul.direct;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.widget.RemoteViews;

import java.util.Calendar;
import java.util.List;
import java.util.Map;

/**
 * 가장 작은 것 — 수능까지 남은 날과 이번 달 진도.
 *
 * 2×2 라 자리를 거의 안 먹는다. 그림을 그리지 않는다 — 비율은
 * {@code ProgressBar} 가 낸다. RemoteViews 가 다룰 수 있는 몇 안 되는 뷰다.
 */
public class DdayWidget extends WidgetBase {

    @Override int layout() { return R.layout.w_dday; }

    @Override
    void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
              Map<String, List<Solved.Item>> log) {
        v.setTextViewText(R.id.big, "D-" + Widgets.dday());
        v.setTextViewText(R.id.title, "수능까지");

        Calendar now = Calendar.getInstance();
        int y = now.get(Calendar.YEAR), mo = now.get(Calendar.MONTH);
        int days = now.getActualMaximum(Calendar.DAY_OF_MONTH);
        int hit = 0, n = 0;
        Calendar d = Calendar.getInstance();
        d.set(y, mo, 1);
        for (int i = 1; i <= days; i++) {
            int k = Solved.on(log, Solved.ymd(d));
            if (k > 0) hit++;
            n += k;
            d.add(Calendar.DAY_OF_MONTH, 1);
        }
        /* 며칠 했는지로 채운다. 회차 수로 채우면 하루에 여럿 푼 날이
           달을 통째로 채워 버려 '얼마나 꾸준한가'가 안 보인다. */
        v.setProgressBar(R.id.prog, days, hit, false);
        v.setTextViewText(R.id.foot, (mo + 1) + "월 " + hit + "일 · " + n + "회차");
    }
}
