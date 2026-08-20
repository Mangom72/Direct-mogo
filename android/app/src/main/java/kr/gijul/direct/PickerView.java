package kr.gijul.direct;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 띄운 창 안에서 문서를 고르는 목록.
 *
 * 화면은 둘뿐이다 — <b>과목 고르기</b>와 <b>회차 고르기</b>. 문제·정답·해설을
 * 셋째 화면으로 빼지 않고 회차 줄에 바로 붙였다. 좁은 창에서 한 걸음은 크다.
 *
 * 종이 자리에 얹혔다가 고르고 나면 물러난다. 창을 새로 띄우지 않는 것은 이
 * 기능의 요점이 '앱으로 돌아가지 않는 것'이기 때문이다.
 */
class PickerView extends LinearLayout {

    private static final String TAG = "gijul.picker";

    interface Host {
        /** 고른 자료를 열어라 */
        void pick(Catalog.Paper p, int kind);
        /** 지금 보고 있는 자료의 주소 (없으면 null) */
        String showing();
    }

    private final Catalog cat;
    private final Host host;
    private final boolean night;
    private final int ink, dim, card;

    private final EditText box;
    private final View searchRow;
    private final LinearLayout crumb;
    private final TextView crumbText, notice;
    private final RecyclerView list;

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private List<Catalog.Subject> allSubjects = new ArrayList<>();
    private List<Catalog.Subject> shown = new ArrayList<>();
    private List<Catalog.Paper> papers = new ArrayList<>();
    private Catalog.Subject open;          // null 이면 과목 고르기

    PickerView(Context c, Catalog cat, Host host, boolean night) {
        super(c);
        this.cat = cat;
        this.host = host;
        this.night = night;
        ink  = night ? 0xFFECE7DA : 0xFF221F1A;
        dim  = night ? 0x8CECE7DA : 0xFF8B8271;
        card = night ? 0xFF1B2029 : 0xFFFCFAF5;

        setOrientation(VERTICAL);
        setBackgroundColor(card);

        searchRow = buildSearch();
        addView(searchRow, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        box = (EditText) ((ViewGroup) searchRow).getChildAt(0);

        crumb = new LinearLayout(c);
        crumb.setOrientation(HORIZONTAL);
        crumb.setGravity(Gravity.CENTER_VERTICAL);
        crumb.setPadding(dp(10), dp(7), dp(10), dp(7));
        crumb.setBackgroundColor(night ? 0xFF161A22 : 0xFFFFFFFF);
        TextView back = new TextView(c);
        back.setText("‹");
        back.setTextSize(17);
        back.setTypeface(null, Typeface.BOLD);
        back.setTextColor(ink);
        back.setPadding(dp(4), 0, dp(10), 0);
        back.setOnClickListener(v -> showSubjects());
        crumbText = new TextView(c);
        crumbText.setTextSize(12.5f);
        crumbText.setTypeface(null, Typeface.BOLD);
        crumbText.setTextColor(ink);
        crumb.addView(back);
        crumb.addView(crumbText);
        crumb.setVisibility(GONE);
        addView(crumb, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));

        notice = new TextView(c);
        notice.setTextSize(12.5f);
        notice.setTextColor(dim);
        notice.setPadding(dp(12), dp(14), dp(12), dp(14));
        notice.setVisibility(GONE);
        addView(notice, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));

        list = new RecyclerView(c);
        list.setLayoutManager(new LinearLayoutManager(c));
        list.setAdapter(new Rows());
        addView(list, new LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f));
    }

    private int dp(float v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private View buildSearch() {
        LinearLayout row = new LinearLayout(getContext());
        row.setOrientation(HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(10), dp(8), dp(10), dp(8));
        row.setBackgroundColor(night ? 0xFF161A22 : 0xFFFFFFFF);

        EditText e = new EditText(getContext());
        e.setHint("과목 찾기 — 언매, 생윤, 고3 생명…");
        e.setTextSize(12.5f);
        e.setTextColor(night ? 0xFFECE7DA : 0xFF221F1A);
        e.setHintTextColor(night ? 0x8CECE7DA : 0xFF8B8271);
        e.setSingleLine(true);
        e.setPadding(dp(9), dp(5), dp(9), dp(5));
        GradientDrawable g = new GradientDrawable();
        g.setColor(night ? 0x14ECE7DA : 0xFFFFFFFF);
        g.setCornerRadius(dp(8));
        g.setStroke(dp(1.2f), night ? 0x33ECE7DA : 0xFFD9D2C4);
        e.setBackground(g);
        e.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void afterTextChanged(Editable s) { filter(s.toString()); }
        });
        row.addView(e, new LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));

        TextView clear = new TextView(getContext());
        clear.setText("✕");
        clear.setTextSize(13);
        clear.setTextColor(night ? 0x8CECE7DA : 0xFF8B8271);
        clear.setPadding(dp(10), dp(4), dp(4), dp(4));
        clear.setOnClickListener(v -> e.setText(""));
        row.addView(clear);
        return row;
    }

    // ── 화면 둘 ─────────────────────────────────────────────────────────

    /** 열릴 때 부른다. 지난번에 보던 과목이 있으면 거기로 바로 간다. */
    void enter() {
        if (!allSubjects.isEmpty()) {
            if (open != null) showPapers(open); else showSubjects();
            return;
        }
        say("목록을 받는 중…");
        io.execute(() -> {
            try {
                final List<Catalog.Subject> s = cat.subjects();
                post(() -> {
                    allSubjects = s;
                    if (open != null) showPapers(open); else showSubjects();
                });
            } catch (Exception e) {
                Log.w(TAG, "목록을 받지 못했습니다", e);
                post(() -> say("목록을 받지 못했습니다 — 연결을 확인해 주십시오"));
            }
        });
    }

    private void say(String msg) {
        notice.setText(msg == null ? "" : msg);
        notice.setVisibility(msg == null ? GONE : VISIBLE);
        list.setVisibility(msg == null ? VISIBLE : GONE);
    }

    private void showSubjects() {
        open = null;
        searchRow.setVisibility(VISIBLE);
        crumb.setVisibility(GONE);
        filter(box.getText().toString());
    }

    private void filter(String q) {
        if (open != null) return;
        shown = Catalog.search(allSubjects, q);
        say(shown.isEmpty() && !allSubjects.isEmpty() ? "찾는 과목이 없습니다" : null);
        list.getAdapter().notifyDataSetChanged();
    }

    private void showPapers(final Catalog.Subject s) {
        open = s;
        searchRow.setVisibility(GONE);
        crumb.setVisibility(VISIBLE);
        crumbText.setText(s.gradeLabel + " · " + s.name);
        papers = new ArrayList<>();
        list.getAdapter().notifyDataSetChanged();
        say("회차를 받는 중…");
        io.execute(() -> {
            try {
                final List<Catalog.Paper> p = cat.papers(s);
                post(() -> {
                    if (open != s) return;          // 그 사이 다른 과목으로 갔다
                    papers = p;
                    say(null);
                    list.getAdapter().notifyDataSetChanged();
                });
            } catch (Exception e) {
                Log.w(TAG, "회차를 받지 못했습니다: " + s, e);
                post(() -> { if (open == s) say("회차를 받지 못했습니다 — 연결을 확인해 주십시오"); });
            }
        });
    }

    /** 뒤로. 과목 목록이면 더 갈 데가 없다고 알린다. */
    boolean back() {
        if (open != null) { showSubjects(); return true; }
        return false;
    }

    // ── 줄 그리기 ───────────────────────────────────────────────────────

    /**
     * 줄마다 <b>폭을 못박아 준다.</b>
     *
     * RecyclerView 는 LayoutParams 없이 온 줄에 WRAP_CONTENT 를 물려 준다.
     * 그러면 줄이 제 내용만큼만 넓어져서, 오른쪽으로 밀어붙이라고 준
     * 가중치(weight 1)가 밀어낼 여백을 못 찾는다 — 문제·정답·해설이 회차
     * 이름 바로 뒤에 붙어 회차마다 들쭉날쭉해 보였다.
     */
    private class Rows extends RecyclerView.Adapter<RecyclerView.ViewHolder> {
        @NonNull @Override
        public RecyclerView.ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int type) {
            return type == 0 ? new SubjectRow(getContext()) : new PaperRow(getContext());
        }
        @Override public void onBindViewHolder(@NonNull RecyclerView.ViewHolder h, int i) {
            if (h instanceof SubjectRow) ((SubjectRow) h).bind(shown.get(i));
            else ((PaperRow) h).bind(papers.get(i));
        }
        @Override public int getItemCount() { return open == null ? shown.size() : papers.size(); }
        @Override public int getItemViewType(int position) { return open == null ? 0 : 1; }
    }

    private class SubjectRow extends RecyclerView.ViewHolder {
        private final TextView name, count;
        SubjectRow(Context c) {
            super(new LinearLayout(c));
            LinearLayout r = (LinearLayout) itemView;
            r.setOrientation(HORIZONTAL);
            r.setGravity(Gravity.CENTER_VERTICAL);
            r.setPadding(dp(11), dp(9), dp(11), dp(9));
            r.setLayoutParams(new RecyclerView.LayoutParams(
                    LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
            name = new TextView(c);
            name.setTextSize(13);
            name.setTypeface(null, Typeface.BOLD);
            name.setTextColor(ink);
            count = new TextView(c);
            count.setTextSize(11);
            count.setTextColor(dim);
            r.addView(name, new LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
            r.addView(count);
        }
        void bind(final Catalog.Subject s) {
            name.setText(s.gradeLabel + " · " + s.name);
            count.setText(s.count + "회차");
            itemView.setOnClickListener(v -> showPapers(s));
        }
    }

    private class PaperRow extends RecyclerView.ViewHolder {
        private final TextView title, when;
        private final TextView[] chips = new TextView[3];
        PaperRow(Context c) {
            super(new LinearLayout(c));
            LinearLayout r = (LinearLayout) itemView;
            r.setOrientation(HORIZONTAL);
            r.setGravity(Gravity.CENTER_VERTICAL);
            r.setPadding(dp(11), dp(8), dp(8), dp(8));
            r.setLayoutParams(new RecyclerView.LayoutParams(
                    LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
            LinearLayout left = new LinearLayout(c);
            left.setOrientation(VERTICAL);
            title = new TextView(c);
            title.setTextSize(13);
            title.setTypeface(null, Typeface.BOLD);
            title.setTextColor(ink);
            when = new TextView(c);
            when.setTextSize(11);
            when.setTextColor(dim);
            left.addView(title);
            left.addView(when);
            r.addView(left, new LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));
            for (int k = 0; k < 3; k++) {
                TextView t = new TextView(c);
                t.setText(Catalog.KIND[k]);
                t.setTextSize(11);
                t.setTypeface(null, Typeface.BOLD);
                t.setGravity(Gravity.CENTER);
                t.setPadding(dp(8), dp(4), dp(8), dp(4));
                LayoutParams lp = new LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT);
                lp.leftMargin = dp(4);
                r.addView(t, lp);
                chips[k] = t;
            }
        }
        void bind(final Catalog.Paper p) {
            String now = host.showing();
            boolean here = now != null && (now.equals(p.problem) || now.equals(p.answer) || now.equals(p.solution));
            title.setText(p.title + "  " + p.source);
            when.setText(p.date.replace('-', '.') + (here ? " · 지금 보는 중" : ""));
            itemView.setBackgroundColor(here ? (night ? 0xFF232A36 : 0xFFF2ECE0) : Color.TRANSPARENT);
            for (int k = 0; k < 3; k++) {
                final int kind = k;
                String u = p.url(k);
                final boolean on = u != null && !u.isEmpty();
                TextView t = chips[k];
                GradientDrawable g = new GradientDrawable();
                g.setCornerRadius(dp(2));
                if (!on) {
                    g.setColor(Color.TRANSPARENT);
                    g.setStroke(dp(1.2f), night ? 0x33ECE7DA : 0xFFD9D2C4);
                    t.setTextColor(night ? 0x55ECE7DA : 0xFFBDB5A4);
                } else if (kind == 1) {
                    g.setColor(0xFFB4342A);
                    t.setTextColor(0xFFFFFFFF);
                } else if (kind == 0) {
                    g.setColor(ink);
                    t.setTextColor(card);
                } else {
                    g.setColor(Color.TRANSPARENT);
                    g.setStroke(dp(1.2f), ink);
                    t.setTextColor(ink);
                }
                t.setBackground(g);
                t.setClickable(on);
                t.setOnClickListener(on ? v -> host.pick(p, kind) : null);
            }
        }
    }

    void shutdown() { io.shutdownNow(); }
}
