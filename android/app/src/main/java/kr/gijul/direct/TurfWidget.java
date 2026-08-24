package kr.gijul.direct;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.widget.RemoteViews;

import java.util.Calendar;
import java.util.List;
import java.util.Map;

/**
 * 잔디밭 — 열다섯 주.
 *
 * 홈 화면을 넘길 때마다 <b>끊긴 자리가 눈에 들어오는</b> 것이 이 꼴의 값이다.
 * 칸이 7dp 남짓이라 뷰로는 낼 수 없고 한 장으로 그린다.
 */
public class TurfWidget extends WidgetBase {

    private static final int WEEKS = 15;

    /* 푼 것을 보여 주던 위젯이니 눌렀을 때 갈 곳은 달력이다 */
    @Override String where() { return Widgets.CAL; }

    @Override int layout() { return R.layout.w_turf; }

    @Override
    void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
              Map<String, List<Solved.Item>> log) {
        v.setTextViewText(R.id.title, "푼 날");
        v.setTextViewText(R.id.count, Solved.streak(log) + "일째");

        int[] wh = size(c, m, id, 250, 110);
        float k = grow(wh, 250, 110);
        sp(v, R.id.title, 13.5f * k);
        sp(v, R.id.count, 10.5f * k);
        sp(v, R.id.foot, 10.5f * k);

        /* 칸 크기는 일곱 줄이 정하므로 높이가 결정한다. 그러고 나면 넓은 카드에는
           너비가 남는데, 칸을 늘여 채우는 대신 <b>주를 더 보여</b> 채운다 —
           잔디밭이 답하는 질문이 '어디서 끊겼나'라 길수록 낫다. */
        int artW = Math.max(140, wh[0] - 20), artH = Math.max(40, wh[1] - Math.round(62 * k));
        float cellDp = (artH - 2 * 6) / 7f, gapDp = Math.max(2, cellDp * 0.16f);
        cellDp = (artH - gapDp * 6) / 7f;
        int weeks = (int) Math.floor((artW + gapDp) / (cellDp + gapDp));
        weeks = Math.max(WEEKS, Math.min(53, weeks));
        int sum = 0;
        Calendar end = Calendar.getInstance();
        end.add(Calendar.DAY_OF_MONTH, 7 - end.get(Calendar.DAY_OF_WEEK));
        Calendar walk = (Calendar) end.clone();
        walk.add(Calendar.DAY_OF_MONTH, -(weeks * 7 - 1));
        for (int i = 0; i < weeks * 7; i++) {
            sum += Solved.on(log, Solved.ymd(walk));
            walk.add(Calendar.DAY_OF_MONTH, 1);
        }
        v.setTextViewText(R.id.foot, "수능 D-" + Widgets.dday() + " · " + weeks + "주 " + sum + "회차");
        v.setImageViewBitmap(R.id.art, turf(c, log, end, px(c, artW), px(c, artH), weeks));
    }

    private Bitmap turf(Context c, Map<String, List<Solved.Item>> log, Calendar end, int w, int h,
                        int weeks) {
        float cell = (h - px(c, 2) * 6) / 7f;
        float gap = Math.max(px(c, 2), cell * 0.16f);
        cell = (h - gap * 6) / 7f;
        int bw = Math.round(cell * weeks + gap * (weeks - 1));
        int bh = Math.round(cell * 7 + gap * 6);
        Bitmap b = Bitmap.createBitmap(Math.max(1, bw), Math.max(1, bh), Bitmap.Config.ARGB_8888);
        Canvas g = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);

        int rule = color(c, R.color.w_rule), mark = color(c, R.color.w_mark);
        Calendar d = (Calendar) end.clone();
        d.add(Calendar.DAY_OF_MONTH, -(weeks * 7 - 1));
        for (int col = 0; col < weeks; col++) {
            for (int row = 0; row < 7; row++) {
                int n = Solved.on(log, Solved.ymd(d));
                /* 하루에 몇 회차인지를 짙기로 낸다. 셋을 넘으면 더 짙어지지 않는다 —
                   여덟을 푼 날과 넉을 푼 날을 색으로 가릴 일이 아니다. */
                p.setColor(n == 0 ? rule : blend(rule, mark, n == 1 ? .38f : n == 2 ? .68f : 1f));
                float x = col * (cell + gap), y = row * (cell + gap);
                float rr = Math.max(px(c, 1.5f), cell * 0.18f);
                g.drawRoundRect(x, y, x + cell, y + cell, rr, rr, p);
                d.add(Calendar.DAY_OF_MONTH, 1);
            }
        }
        return b;
    }

    private static int blend(int from, int to, float t) {
        int r = 0;
        for (int sh = 0; sh <= 24; sh += 8) {
            int a = (from >>> sh) & 0xFF, z = (to >>> sh) & 0xFF;
            r |= (a + Math.round((z - a) * t)) << sh;
        }
        return r;
    }
}
