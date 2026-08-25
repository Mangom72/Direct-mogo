package kr.gijul.direct;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.view.View;
import android.widget.RemoteViews;

import java.util.Calendar;
import java.util.List;
import java.util.Map;

/**
 * 최근 푼 것 다섯.
 *
 * 달력을 안 쓰는 사람을 위한 것이다. '요즘 하고 있나'가 아니라 '방금 뭘
 * 풀었더라'에 답한다. 그림을 그리지 않는다 — 글자와 색칠한 네모뿐이라
 * 글자 크기가 기기 설정을 그대로 따른다.
 */
public class RecentWidget extends WidgetBase {

    private static final int[] ROW = {R.id.r0, R.id.r1, R.id.r2, R.id.r3, R.id.r4};
    private static final int[] DAY = {R.id.d0, R.id.d1, R.id.d2, R.id.d3, R.id.d4};
    private static final int[] BAR = {R.id.b0, R.id.b1, R.id.b2, R.id.b3, R.id.b4};
    private static final int[] TXT = {R.id.t0, R.id.t1, R.id.t2, R.id.t3, R.id.t4};

    /* 푼 것을 보여 주던 위젯이니 눌렀을 때 갈 곳은 달력이다 */
    @Override String where() { return Widgets.CAL; }

    @Override int layout() { return R.layout.w_recent; }

    @Override
    void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
              Map<String, List<Solved.Item>> log) {
        v.setTextViewText(R.id.title, "최근 푼 것");
        int st = Solved.streak(log);
        v.setTextViewText(R.id.count, st > 0 ? st + "일째" : "");
        v.setTextViewText(R.id.foot, footer(c, log));

        List<Solved.Item> it = Solved.recent(log, ROW.length);
        v.setViewVisibility(R.id.empty, it.isEmpty() ? View.VISIBLE : View.GONE);
        if (it.isEmpty()) v.setTextViewText(R.id.empty, "아직 찍어 둔 회차가 없습니다");

        /* 카드가 크면 글자도 커지고 줄도 벌어진다 */
        int[] wh = size(c, m, id, 250, 160);
        float k = grow(wh, 250, 160);
        sp(v, R.id.title, 13.5f * k);
        sp(v, R.id.count, 10.5f * k);
        sp(v, R.id.foot, 10.5f * k);
        sp(v, R.id.empty, 11.5f * k);
        int pad = spread(c, wh, Math.max(1, it.size()), 46 * k, 20 * k);

        for (int i = 0; i < ROW.length; i++) {
            if (i >= it.size()) { v.setViewVisibility(ROW[i], View.GONE); continue; }
            Solved.Item x = it.get(i);
            v.setViewVisibility(ROW[i], View.VISIBLE);
            v.setViewPadding(ROW[i], 0, pad, 0, pad);
            v.setTextViewText(DAY[i], mmdd(x.day));
            v.setTextViewText(TXT[i], Solved.label(x));
            sp(v, DAY[i], 10.5f * k);
            sp(v, TXT[i], 11.5f * k);
            v.setInt(BAR[i], "setBackgroundResource",
                    x.gov() ? R.drawable.w_bar_gov : R.drawable.w_bar_edu);
            bar(c, v, BAR[i], k);
        }
    }

    /* 세로 막대는 글자와 함께 자라야 한다 — 안 그러면 큰 카드에서 실오라기가 된다 */
    private void bar(Context c, RemoteViews v, int id, float k) {
        if (android.os.Build.VERSION.SDK_INT < 31) return;
        v.setViewLayoutWidth(id, 3 * k, android.util.TypedValue.COMPLEX_UNIT_DIP);
        v.setViewLayoutHeight(id, 15 * k, android.util.TypedValue.COMPLEX_UNIT_DIP);
    }

    static String mmdd(String ymd) { return Names.mmdd(ymd); }
}
