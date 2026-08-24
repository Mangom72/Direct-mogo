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
 * 이번 주와 연속 일수.
 *
 * 홈 화면에서 답해야 할 질문이 '오늘 했나'라면 이게 가장 곧바로 답한다.
 * 막대 높이를 프레임마다 정해야 하는데 {@code setViewLayoutHeight} 는
 * 안드로이드 12부터라, 막대만 한 장으로 그린다 — 글자는 진짜 글자다.
 */
public class WeekWidget extends WidgetBase {

    /* 푼 것을 보여 주던 위젯이니 눌렀을 때 갈 곳은 달력이다 */
    @Override String where() { return Widgets.CAL; }

    @Override int layout() { return R.layout.w_week; }

    @Override
    void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
              Map<String, List<Solved.Item>> log) {
        int st = streakDays(log);
        v.setTextViewText(R.id.big, st + "일째");
        v.setTextViewText(R.id.title, st > 0 ? "이어서 풀고 있습니다" : "오늘부터 다시");

        Calendar c0 = Calendar.getInstance();
        c0.add(Calendar.DAY_OF_MONTH, -(c0.get(Calendar.DAY_OF_WEEK) - 1));
        int[] n = new int[7];
        int sum = 0;
        for (int i = 0; i < 7; i++) {
            n[i] = Solved.on(log, Solved.ymd(c0));
            sum += n[i];
            c0.add(Calendar.DAY_OF_MONTH, 1);
        }
        v.setTextViewText(R.id.foot, "수능 D-" + Widgets.dday() + " · 이번 주 " + sum + "회차");

        int[] wh = size(c, m, id, 250, 110);
        v.setImageViewBitmap(R.id.art, bars(c, n,
                px(c, Math.max(140, wh[0] - 20)), px(c, Math.max(34, wh[1] - 66))));
    }

    private int streakDays(Map<String, List<Solved.Item>> log) { return Solved.streak(log); }

    /**
     * 일곱 칸. <b>막대 너비에 상한을 둔다</b> — 큰 화면에서 폭을 다 나눠 가지면
     * 막대가 아니라 널찍한 판이 일곱 개 서 있는 꼴이 되어, 무엇을 재는 그림인지가
     * 안 보인다. 남는 폭은 양쪽으로 흘린다.
     */
    private Bitmap bars(Context c, int[] n, int w, int h) {
        Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas g = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        int max = 1;
        for (int x : n) max = Math.max(max, x);

        float lab = fit(c, h, 0.22f, 10f, 17f), foot = fit(c, h, 0.20f, 9f, 15f);
        float txt = fit(c, h, 0.14f, 8f, 12f);
        float area = Math.max(1, h - lab - foot);      /* 막대가 설 높이 */
        /* 폭을 다 나눠 가지면 막대가 아니라 널찍한 판이 일곱 개 서 있는 꼴이
           된다. 서는 높이보다 넓어지지 않게 묶어 둔다. */
        float cw = Math.min((w - px(c, 5) * 6) / 7f, Math.min(px(c, 28), area * 0.55f));
        /* 남는 폭은 사이로 흘린다. 막대만 좁혀 놓고 가운데로 모으면 넓은 위젯에서
           양옆이 통째로 비어, 자리를 차지하고도 아무 말을 안 하는 꼴이 된다. */
        float gap = Math.max(px(c, 5), Math.min((w - cw * 7) / 6f, cw * 1.1f));
        float span = cw * 7 + gap * 6;
        float left = (w - span) / 2f;
        float top = lab, bot = h - foot;
        float round = Math.min(px(c, 6), cw * 0.28f);
        String[] dow = {"일", "월", "화", "수", "목", "금", "토"};
        int today = Calendar.getInstance().get(Calendar.DAY_OF_WEEK) - 1;

        p.setTextAlign(Paint.Align.CENTER);
        for (int i = 0; i < 7; i++) {
            float x0 = left + i * (cw + gap);
            p.setTypeface(font(c, true));
            p.setTextSize(txt);
            p.setColor(i == 0 ? color(c, R.color.w_mark) : color(c, R.color.w_ink2));
            g.drawText(dow[i], x0 + cw / 2, lab - txt * 0.45f, p);

            float bh = Math.max(0, bot - top);
            p.setColor(color(c, R.color.w_rule));
            g.drawRoundRect(x0, top, x0 + cw, bot, round, round, p);
            if (n[i] > 0) {
                /* 아주 낮은 막대도 둥근 끝이 뭉개지지 않을 만큼은 남긴다.
                   여기를 막대 너비로 잡아 두었더니 하루 푼 날과 이틀 푼 날이
                   같은 높이가 됐다. */
                float fill = Math.max(round * 2, bh * n[i] / max);
                p.setColor(color(c, R.color.w_mark));
                g.drawRoundRect(x0, bot - fill, x0 + cw, bot, round, round, p);
            }
            /* 오늘은 밑줄로 표시한다 — 막대 색을 바꾸면 '많이 푼 날'과 헷갈린다 */
            if (i == today) {
                p.setColor(color(c, R.color.w_ink));
                g.drawRect(x0, bot + px(c, 2), x0 + cw, bot + px(c, 3.5f), p);
            }
            if (n[i] > 0) {
                p.setTypeface(font(c, false));
                p.setTextSize(txt);
                p.setColor(color(c, R.color.w_ink2));
                g.drawText(String.valueOf(n[i]), x0 + cw / 2, h - foot * 0.15f, p);
            }
        }
        return b;
    }
}
