package kr.gijul.direct;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.widget.RemoteViews;

import java.util.Calendar;
import java.util.List;
import java.util.Map;

/**
 * 한 달 달력.
 *
 * <h3>왜 한 장으로 그리는가</h3>
 * 격자는 칸이 마흔둘이고 칸마다 이름표가 또 여럿이다. {@code RemoteViews} 로
 * 내면 뷰가 수백 개가 되어 런처에 건네는 꾸러미가 한도를 넘는다 — 넘으면 위젯이
 * 통째로 안 뜬다. 그림 한 장은 뷰 하나다.
 *
 * 값이 없지는 않다. 이 위젯만은 <b>글자 크기가 기기 설정을 따르지 않는다.</b>
 * 나머지 다섯은 진짜 글자라 따라간다.
 */
public class CalWidget extends WidgetBase {

    /* 푼 것을 보여 주던 위젯이니 눌렀을 때 갈 곳은 달력이다 */
    @Override String where() { return Widgets.CAL; }

    @Override int layout() { return R.layout.w_cal; }

    @Override
    void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
              Map<String, List<Solved.Item>> log) {
        Calendar now = Calendar.getInstance();
        int y = now.get(Calendar.YEAR), mo = now.get(Calendar.MONTH);

        int n = 0;
        String pre = String.format("%04d%02d", y, mo + 1);
        for (String d : log.keySet()) if (d.startsWith(pre)) n += log.get(d).size();

        v.setTextViewText(R.id.title, (mo + 1) + "월");
        v.setTextViewText(R.id.count, n > 0 ? n + "회차" : "");
        v.setTextViewText(R.id.foot, footer(c, log));

        int[] wh = size(m, id, 250, 250);
        v.setImageViewBitmap(R.id.art, month(c, log, y, mo,
                px(c, Math.max(140, wh[0] - 20)), px(c, Math.max(120, wh[1] - 62))));
    }

    /** 격자 한 장. 칸에 들어가는 만큼 이름표를 넣고 나머지는 +n 으로 접는다. */
    private Bitmap month(Context c, Map<String, List<Solved.Item>> log,
                         int year, int mon, int w, int h) {
        Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas g = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        RectF r = new RectF();

        final int ink = color(c, R.color.w_ink), ink2 = color(c, R.color.w_ink2);
        final int rule = color(c, R.color.w_rule), card = color(c, R.color.w_card);
        final int gov = color(c, R.color.w_gov), edu = color(c, R.color.w_edu);

        Calendar cal = Calendar.getInstance();
        cal.clear();
        cal.set(year, mon, 1);
        int first = cal.get(Calendar.DAY_OF_WEEK) - 1;
        int last = cal.getActualMaximum(Calendar.DAY_OF_MONTH);
        int weeks = (int) Math.ceil((first + last) / 7.0);

        float head = px(c, 13);
        float cw = w / 7f, ch = (h - head) / Math.max(1, weeks);

        /* 요일 */
        p.setTextSize(px(c, 8.5f));
        p.setTextAlign(Paint.Align.CENTER);
        String[] dow = {"일", "월", "화", "수", "목", "금", "토"};
        for (int i = 0; i < 7; i++) {
            p.setColor(i == 0 ? color(c, R.color.w_mark) : ink2);
            g.drawText(dow[i], cw * (i + .5f), head - px(c, 3), p);
        }

        String today = Solved.ymd(Calendar.getInstance());
        p.setTextAlign(Paint.Align.LEFT);
        float pad = px(c, 2), chipH = px(c, 9.5f), gapY = px(c, 1.5f);

        for (int d = 1; d <= last; d++) {
            int idx = first + d - 1, col = idx % 7, row = idx / 7;
            float x0 = cw * col, y0 = head + ch * row;

            /* 칸 테두리 — 실선 격자를 그리면 작은 화면에서 자국만 남는다.
               바탕을 아주 옅게 깔고 날짜만 또렷하게 둔다. */
            r.set(x0 + .5f, y0 + .5f, x0 + cw - .5f, y0 + ch - .5f);
            p.setColor(card);
            g.drawRect(r, p);
            p.setColor(rule);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(1f);
            g.drawRect(r, p);
            p.setStyle(Paint.Style.FILL);

            String key = String.format("%04d%02d%02d", year, mon + 1, d);
            List<Solved.Item> it = log.get(key);

            p.setTextSize(px(c, 8.5f));
            float ty = y0 + px(c, 8);
            if (key.equals(today)) {
                float rr = px(c, 6.5f);
                p.setColor(ink);
                g.drawCircle(x0 + pad + rr - px(c, 1), ty - px(c, 2.6f), rr, p);
                p.setColor(card);
            } else {
                p.setColor(col == 0 ? color(c, R.color.w_mark) : ink2);
            }
            g.drawText(String.valueOf(d), x0 + pad + (key.equals(today) ? px(c, 2.4f) : 0), ty, p);

            if (it == null || it.isEmpty()) continue;

            /* 이름표 — 들어가는 만큼만. 몇 개가 들어갈지는 칸 높이가 정한다. */
            float top = ty + px(c, 2), room = y0 + ch - top - px(c, 1);
            int fits = (int) Math.floor(room / (chipH + gapY));
            int show = Math.min(fits, it.size());
            /* '+n' 도 한 줄을 먹지만 이름표보다 낮다. 이름표 하나를 물리기 전에
               남은 틈으로 되는지 먼저 본다 — 한 칸밖에 못 넣는 크기에서 무턱대고
               물리면 이름은 하나도 없이 '+2'만 남는다. */
            if (show < it.size() && show > 0 && room - show * (chipH + gapY) < px(c, 7.5f)) show--;

            p.setTextSize(px(c, 7.5f));
            for (int i = 0; i < show; i++) {
                Solved.Item x = it.get(i);
                float cy = top + i * (chipH + gapY);
                r.set(x0 + pad, cy, x0 + cw - pad, cy + chipH);
                p.setColor((x.gov() ? gov : edu) & 0x30FFFFFF);
                g.drawRect(r, p);
                p.setColor(x.gov() ? gov : edu);
                g.drawRect(x0 + pad, cy, x0 + pad + px(c, 1.6f), cy + chipH, p);
                p.setColor(ink);
                g.save();
                g.clipRect(x0 + pad + px(c, 2.4f), cy, x0 + cw - pad, cy + chipH);
                g.drawText(Solved.shortSub(x.name), x0 + pad + px(c, 2.6f),
                        cy + chipH - px(c, 2.2f), p);
                g.restore();
            }
            if (show < it.size()) {
                p.setColor(ink2);
                p.setTextSize(px(c, 7f));
                g.drawText("+" + (it.size() - show), x0 + pad + px(c, 1),
                        top + show * (chipH + gapY) + px(c, 7), p);
            }
        }
        return b;
    }
}
