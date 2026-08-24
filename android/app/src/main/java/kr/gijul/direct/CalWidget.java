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
 * <h3>칸에 맞춰 자란다</h3>
 * 글자와 이름표 크기를 dp 로 못박아 두었더니, 태블릿처럼 칸이 70dp가 넘는
 * 자리에서 8.5dp 글자가 구석에 붙어 칸이 통째로 비어 보였다. 이제 칸 크기에
 * 비례해 자라고 위아래로만 막아 둔다.
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

        int[] wh = size(c, m, id, 250, 250);
        float k = grow(wh, 250, 250);
        sp(v, R.id.title, 13.5f * k);
        sp(v, R.id.count, 10.5f * k);
        sp(v, R.id.foot, 10.5f * k);
        v.setImageViewBitmap(R.id.art, month(c, log, y, mo,
                px(c, Math.max(140, wh[0] - 20)),
                px(c, Math.max(120, wh[1] - Math.round(62 * k)))));
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
        final int mark = color(c, R.color.w_mark);

        Calendar cal = Calendar.getInstance();
        cal.clear();
        cal.set(year, mon, 1);
        int first = cal.get(Calendar.DAY_OF_WEEK) - 1;
        int last = cal.getActualMaximum(Calendar.DAY_OF_MONTH);
        int weeks = (int) Math.ceil((first + last) / 7.0);

        float cw = w / 7f;
        /* 요일 줄은 칸 높이를 따라간다. 못박아 두면 큰 칸에서 격자와 동떨어져
           허공에 뜬 것처럼 보인다. */
        float ch0 = h / (weeks + 0.55f);
        float head = ch0 * 0.55f, ch = ch0;

        float dowSize = fit(c, head, 0.62f, 8f, 22f);
        p.setTextSize(dowSize);
        p.setTextAlign(Paint.Align.CENTER);
        p.setTypeface(font(c, true));
        String[] dow = {"일", "월", "화", "수", "목", "금", "토"};
        for (int i = 0; i < 7; i++) {
            p.setColor(i == 0 ? mark : ink2);
            g.drawText(dow[i], cw * (i + .5f), head - dowSize * 0.35f, p);
        }

        String today = Solved.ymd(Calendar.getInstance());
        p.setTextAlign(Paint.Align.LEFT);
        float pad = Math.max(px(c, 2), cw * 0.045f);
        float daySize = fit(c, ch, 0.26f, 8.5f, 26f);
        float chipText = fit(c, ch, 0.21f, 7.5f, 21f);
        float chipH = chipText * 1.55f, gapY = chipH * 0.16f;

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
            boolean isToday = key.equals(today);

            p.setTextSize(daySize);
            p.setTypeface(font(c, isToday));
            float ty = y0 + pad + daySize;              /* 글자 밑선 */
            if (isToday) {
                /* 동그라미가 칸을 넘지 않게 안쪽에 그린다. 예전에는 왼쪽으로
                   반쯤 삐져나가 격자 선을 물고 있었다. */
                float rr = daySize * 0.78f;
                float cx = x0 + pad + rr, cy = ty - daySize * 0.36f;
                p.setColor(ink);
                g.drawCircle(cx, cy, rr, p);
                p.setColor(card);
                p.setTextAlign(Paint.Align.CENTER);
                g.drawText(String.valueOf(d), cx, cy + daySize * 0.36f, p);
                p.setTextAlign(Paint.Align.LEFT);
            } else {
                p.setColor(col == 0 ? mark : ink2);
                g.drawText(String.valueOf(d), x0 + pad, ty, p);
            }

            if (it == null || it.isEmpty()) continue;

            /* 이름표 — 들어가는 만큼만. 몇 개가 들어갈지는 칸 높이가 정한다. */
            float top = ty + daySize * 0.45f, room = y0 + ch - top - pad;
            int fits = (int) Math.floor(room / (chipH + gapY));
            int show = Math.min(fits, it.size());
            /* '+n' 도 한 줄을 먹지만 이름표보다 낮다. 이름표 하나를 물리기 전에
               남은 틈으로 되는지 먼저 본다 — 한 칸밖에 못 넣는 크기에서 무턱대고
               물리면 이름은 하나도 없이 '+2'만 남는다. */
            if (show < it.size() && show > 0 && room - show * (chipH + gapY) < chipText) show--;

            p.setTextSize(chipText);
            p.setTypeface(font(c, false));
            for (int i = 0; i < show; i++) {
                Solved.Item x = it.get(i);
                float cy = top + i * (chipH + gapY);
                r.set(x0 + pad, cy, x0 + cw - pad, cy + chipH);
                p.setColor((x.gov() ? gov : edu) & 0x30FFFFFF);
                g.drawRect(r, p);
                float barW = Math.max(px(c, 1.6f), cw * 0.018f);
                p.setColor(x.gov() ? gov : edu);
                g.drawRect(x0 + pad, cy, x0 + pad + barW, cy + chipH, p);
                p.setColor(ink);
                g.save();
                g.clipRect(x0 + pad + barW * 1.5f, cy, x0 + cw - pad, cy + chipH);
                g.drawText(Solved.shortSub(x.name), x0 + pad + barW * 1.7f,
                        cy + chipH - (chipH - chipText) * 0.62f, p);
                g.restore();
            }
            if (show < it.size()) {
                p.setColor(ink2);
                p.setTextSize(chipText * 0.94f);
                g.drawText("+" + (it.size() - show), x0 + pad,
                        top + show * (chipH + gapY) + chipText, p);
            }
        }
        return b;
    }
}
