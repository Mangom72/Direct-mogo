package kr.gijul.direct;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.util.Log;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;
import java.util.Map;

/**
 * 다음에 풀 것 — 내 과목에서 아직 <b>안 푼</b> 최신 회차.
 *
 * 달력이 아니다. 지나간 것을 돌아보는 대신 다음 한 걸음을 내놓는다.
 *
 * <h3>고르는 일은 페이지가 한다</h3>
 * 무엇이 안 풀렸는지 알려면 회차 목록 전부와 내 과목과 표시가 다 있어야 하는데,
 * 앱이 그것을 얻으려면 자료를 받아 와야 한다. <b>홈 화면에 뜨는 것이 망을 타는
 * 것은 옳지 않다.</b> 페이지는 그 셋을 이미 들고 있으므로, 골라 놓은 결과만
 * 표시와 함께 건네받는다.
 */
public class NextWidget extends WidgetBase {

    private static final int[] ROW = {R.id.r0, R.id.r1, R.id.r2};
    private static final int[] BAR = {R.id.b0, R.id.b1, R.id.b2};
    private static final int[] TXT = {R.id.t0, R.id.t1, R.id.t2};

    @Override int layout() { return R.layout.w_next; }

    @Override
    void draw(Context c, AppWidgetManager m, int id, RemoteViews v,
              Map<String, List<Solved.Item>> log) {
        v.setTextViewText(R.id.title, "다음에 풀 것");
        v.setTextViewText(R.id.count, "안 푼 것");
        v.setTextViewText(R.id.foot, "누르면 그 과목으로");

        JSONArray next = null;
        try {
            String json = Solved.prefs(c).getString("json", null);
            if (json != null) next = new JSONObject(json).optJSONArray("next");
        } catch (Exception e) {
            Log.w("gijul.widget", "다음 회차를 읽지 못했습니다", e);
        }

        int n = next == null ? 0 : next.length();
        int[] wh = size(c, m, id, 250, 122);
        float k = grow(wh, 250, 122);
        sp(v, R.id.title, 13.5f * k);
        sp(v, R.id.count, 10.5f * k);
        sp(v, R.id.foot, 10.5f * k);
        sp(v, R.id.empty, 11.5f * k);
        int pad = spread(c, wh, Math.max(1, Math.min(n, ROW.length)), 46 * k, 21 * k);
        v.setViewVisibility(R.id.empty, n == 0 ? View.VISIBLE : View.GONE);
        if (n == 0) {
            v.setTextViewText(R.id.empty,
                    "내 과목을 저장하고 앱을 한 번 열면 여기에 뜹니다");
        }
        for (int i = 0; i < ROW.length; i++) {
            JSONObject x = (next != null && i < n) ? next.optJSONObject(i) : null;
            if (x == null) { v.setViewVisibility(ROW[i], View.GONE); continue; }
            v.setViewVisibility(ROW[i], View.VISIBLE);
            v.setViewPadding(ROW[i], 0, pad, 0, pad);
            v.setTextViewText(TXT[i], x.optString("t", ""));
            sp(v, TXT[i], 12f * k);
            if (android.os.Build.VERSION.SDK_INT >= 31) {
                v.setViewLayoutWidth(BAR[i], 3 * k, android.util.TypedValue.COMPLEX_UNIT_DIP);
                v.setViewLayoutHeight(BAR[i], 15 * k, android.util.TypedValue.COMPLEX_UNIT_DIP);
            }
            v.setInt(BAR[i], "setBackgroundResource",
                    "gov".equals(x.optString("k")) ? R.drawable.w_bar_gov : R.drawable.w_bar_edu);
            /* 줄마다 가는 곳이 다르다. 바탕에 걸어 둔 것(첫 화면)을 줄에서 덮어쓴다 —
               '다음에 풀 것'을 눌렀는데 첫 화면이 열리면 한 번 더 골라야 한다. */
            String g = x.optString("g", ""), sub = x.optString("s", "");
            if (!g.isEmpty() && !sub.isEmpty()) {
                v.setOnClickPendingIntent(ROW[i],
                        Widgets.open(c, Widgets.subject(g, sub), slot() + 1 + i));
            }
        }
    }
}
