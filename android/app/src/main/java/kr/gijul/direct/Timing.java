package kr.gijul.direct;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 재고 있는 시험 하나. 얼굴은 셋이지만 시간은 여기 한 곳에서만 흐른다.
 *
 * <h3>왜 알림이 스스로 세게 두는가</h3>
 * 남은 시간을 1초마다 우리가 다시 그리면, 화면이 꺼진 동안이나 앱이 잠든 동안
 * 알림이 멈춘 것처럼 굳는다. {@code setUsesChronometer} 로 <b>끝나는 시각</b>을
 * 건네면 시스템이 대신 세어 준다 — 우리가 잠들어도 숫자는 흐르고, 잠금화면과
 * 나우바처럼 우리가 손댈 수 없는 자리에서도 같이 흐른다.
 *
 * 진행 실선만은 우리가 갱신해야 해서 1분에 한 번 고쳐 그린다. 초 단위로 정확할
 * 까닭이 없는 것이고, 숫자 쪽은 이미 시스템이 세고 있다.
 *
 * <h3>못 하는 것</h3>
 * 0이 되는 순간의 소리·진동은 <b>우리 프로세스가 살아 있을 때만</b> 울린다.
 * 정확한 알람을 쓰면 안드로이드 12부터 따로 권한을 물어야 하는데, 시험 한 번
 * 재자고 그것을 묻는 것은 값이 맞지 않는다(위젯의 자정 알람도 같은 까닭으로
 * 정확하지 않게 두었다). 숫자는 어느 경우에도 계속 흐르므로 넘긴 것은 보인다.
 */
final class Timing {

    private static final String TAG = "gijul.timing";
    private static final String PREF = "timing";
    private static final String CHANNEL = "timer";
    private static final int NOTE_ID = 0xC10C;

    private static final String LIMIT = "limit", FROM = "from", PAUSED = "paused";
    private static final String KEY = "key", NAME = "name", SUB = "sub";
    private static final String DONE = "done";      // 페이지가 아직 안 가져간 기록

    static final String ACTION = "kr.gijul.direct.TIMER";
    static final String WHAT = "what";              // pause | resume | plus | stop

    private Timing() { }

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
    }

    // ── 지금 상태 ───────────────────────────────────────────────────────

    static Clock clock(Context c) {
        SharedPreferences p = prefs(c);
        return new Clock(p.getLong(LIMIT, 0), p.getLong(FROM, 0), p.getLong(PAUSED, 0));
    }

    static String name(Context c) { return prefs(c).getString(NAME, ""); }
    /* 과목 이름. 알림 제목이 이것이다 — 회차 이름은 길어서 과목이 잘려 나간다. */
    static String sub(Context c) { return prefs(c).getString(SUB, ""); }
    static String key(Context c) { return prefs(c).getString(KEY, ""); }

    /** 이 회차를 지금 재고 있는가. 다른 회차를 재는 중이면 거짓. */
    static boolean mine(Context c, String paperKey) {
        return clock(c).on() && paperKey != null && paperKey.equals(key(c));
    }

    private static void put(Context c, Clock k) {
        prefs(c).edit().putLong(LIMIT, k.limit).putLong(FROM, k.from)
                .putLong(PAUSED, k.pausedAt).apply();
    }

    // ── 시작하고 멈추고 ─────────────────────────────────────────────────

    static void start(Context c, String paperKey, String label, String subject, int minutes) {
        prefs(c).edit()
                .putString(KEY, paperKey == null ? "" : paperKey)
                .putString(NAME, label == null ? "" : label)
                .putString(SUB, subject == null ? "" : subject)
                .apply();
        put(c, Clock.start(minutes * 60_000L, System.currentTimeMillis()));
        show(c);
    }

    static void pause(Context c) { put(c, clock(c).pause(System.currentTimeMillis())); show(c); }
    static void resume(Context c) { put(c, clock(c).resume(System.currentTimeMillis())); show(c); }
    static void plus(Context c, int minutes) { put(c, clock(c).plus(minutes * 60_000L)); show(c); }

    /**
     * 끝낸다. 잰 시간을 남길지는 부르는 쪽이 정한다 — '끝내기'로 끝낸 것은
     * 남기고, 다른 회차를 열어서 밀려난 것은 남기지 않는다.
     */
    static void stop(Context c, boolean record) {
        Clock k = clock(c);
        if (k.on() && record) keep(c, key(c), k.limit, k.spent(System.currentTimeMillis()));
        prefs(c).edit().remove(LIMIT).remove(FROM).remove(PAUSED)
                .remove(KEY).remove(NAME).remove(SUB).apply();
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm != null) nm.cancel(NOTE_ID);
    }

    // ── 페이지에 넘길 기록 ──────────────────────────────────────────────

    /* 타이머가 끝나는 때에 페이지가 떠 있으리라는 보장이 없다. 회차 표시의
       주인은 페이지이므로(과목 번호와 열쇠를 아는 쪽이 거기다) 여기서는 적어
       두었다가, 페이지가 뜰 때 통째로 넘긴다. */
    private static void keep(Context c, String paperKey, long limit, long spent) {
        if (paperKey == null || paperKey.isEmpty()) return;
        try {
            JSONArray a = new JSONArray(prefs(c).getString(DONE, "[]"));
            a.put(new JSONObject().put("k", paperKey)
                    .put("limit", limit / 1000).put("spent", spent / 1000));
            /* 넘겨받기 전에 쌓이기만 하는 일이 없도록 마지막 것들만 남긴다 */
            while (a.length() > 40) a.remove(0);
            prefs(c).edit().putString(DONE, a.toString()).apply();
        } catch (Exception e) {
            Log.w(TAG, "잰 시간을 적어 두지 못했습니다", e);
        }
    }

    /** 페이지가 가져간다. 한 번 넘긴 것은 지운다. */
    static String takeRecords(Context c) {
        String s = prefs(c).getString(DONE, "[]");
        prefs(c).edit().remove(DONE).apply();
        return s;
    }

    // ── 알림 ────────────────────────────────────────────────────────────

    /**
     * 알림 한 벌. 안드로이드 16 이상에서는 <b>실시간 정보</b>로 올려 달라 청하고,
     * 그러면 잠금화면의 나우바와 상태 표시줄에도 같은 시계가 흐른다.
     *
     * <h3>왜 끝나는 시각을 함께 적는가</h3>
     * 남은 시간만 있으면 화면을 볼 때마다 <b>사람이 더해야</b> 한다. 시험장에서
     * 칠판에 적어 두는 것이 종료 시각인 데에는 까닭이 있다 — 그 숫자는 한 번 보면
     * 되고, 흘끗 볼 때마다 셈이 필요 없다. 잠금화면처럼 <b>스치듯 보는 자리</b>일수록
     * 그쪽이 낫다.
     *
     * <h3>제목은 과목이다</h3>
     * 예전에는 회차 이름을 통째로 넣었다. 알림 제목은 한 줄에서 잘리는데, 하필
     * <b>맨 뒤에 과목이 온다</b> — '2026 6월 모평(평가원) 확률과 통계 문제…' 로
     * 잘려 정작 무슨 과목인지가 사라졌다. 알림에서 알고 싶은 것은 '무슨 과목을
     * 몇 시까지'이지 회차 전체가 아니다.
     */
    static void show(Context c) {
        Clock k = clock(c);
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null) return;
        if (!k.on()) { nm.cancel(NOTE_ID); return; }

        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(CHANNEL) == null) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL, "시험 시간", NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }

        long now = System.currentTimeMillis();
        long left = k.left(now);
        boolean over = left < 0;
        String subject = sub(c), paper = name(c);
        String title = !subject.isEmpty() ? subject
                     : !paper.isEmpty() ? paper : "시험 시간";
        long mins = k.limit / 60000;

        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CHANNEL) : new Notification.Builder(c);
        b.setSmallIcon(R.drawable.ic_timer)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setShowWhen(false)
                .setContentIntent(Widgets.open(c, null, 0x71));
        /* 회차 이름은 펼쳤을 때만. 접힌 줄에서는 과목과 끝나는 시각이 이긴다. */
        if (!paper.isEmpty() && !paper.equals(title)) b.setSubText(paper);

        if (k.paused()) {
            b.setContentTitle("멈춤 · " + title);
            b.setContentText(Clock.face(left) + " 남음 · 이어서 누르면 계속됩니다");
            b.addAction(act(c, "resume", "이어서"));
        } else {
            /* 끝나는 시각을 건네고 세는 일은 시스템에 맡긴다. 우리가 잠들어도
               숫자가 흐르고, 잠금화면처럼 우리가 손댈 수 없는 자리에서도 흐른다. */
            b.setUsesChronometer(true).setWhen(now + left).setShowWhen(true);
            if (Build.VERSION.SDK_INT >= 24) b.setChronometerCountDown(!over);
            b.setContentTitle(over ? "시간이 다 됐습니다 · " + title : title);
            b.setContentText(over
                    ? mins + "분 · " + Clock.face(left).substring(1) + " 넘겼습니다"
                    : mins + "분 · " + at(c, now + left) + "에 끝납니다");
            /* 끝난 시험을 멈출 일은 없다 — 그때는 '이어서/일시정지'가 사라진다. */
            if (!over) b.addAction(act(c, "pause", "일시정지"));
        }
        b.addAction(act(c, "plus", "10분 더"));
        b.addAction(act(c, "stop", "끝내기"));

        int done = Math.round(k.ratio(now) * 1000);
        if (Build.VERSION.SDK_INT >= 36) {
            /* 실시간 정보로 올라가려면 정해진 몇 갈래 가운데 하나여야 한다.
               ProgressStyle 이 그 가운데 우리 것에 맞는다 — 흘러가는 일 하나. */
            b.setStyle(new Notification.ProgressStyle()
                    .setProgressIndeterminate(false)
                    .addProgressSegment(new Notification.ProgressStyle.Segment(1000))
                    .setProgress(done));
            /* 상태 표시줄의 시계 옆에 붙는 손톱만 한 글 */
            b.setShortCriticalText(Clock.brief(left));
            /* 승격은 '청하는' 것이다. 안 받아 주면 보통 알림으로 그대로 뜨므로
               갈래를 둘로 만들지 않는다. 값을 넣는 창구(setRequestPromotedOngoing)는
               API 36.1 이라 여기서는 열쇠로 넣는다 — 36 에서도 그렇게 하라고
               문서가 이른다. */
            Bundle x = new Bundle();
            x.putBoolean("android.requestPromotedOngoing", true);
            b.addExtras(x);
        } else {
            b.setProgress(1000, done, false);
        }

        try {
            nm.notify(NOTE_ID, b.build());
        } catch (Exception e) {
            /* 안드로이드 13+ 에서 알림 권한이 없으면 여기서 걸린다. 알림만 없을
               뿐 재는 것은 그대로다 — 뷰어의 칩과 띄운 창의 바가 남아 있다. */
            Log.w(TAG, "알림을 띄우지 못했습니다", e);
        }
    }

    /** 끝나는 시각. 12시간제냐 24시간제냐는 기기 설정을 따른다. */
    private static String at(Context c, long when) {
        return android.text.format.DateFormat.getTimeFormat(c)
                .format(new java.util.Date(when));
    }

    private static Notification.Action act(Context c, String what, String label) {
        Intent i = new Intent(c, Buttons.class).setAction(ACTION).putExtra(WHAT, what);
        i.setData(android.net.Uri.parse("gijul://timer/" + what));
        PendingIntent p = PendingIntent.getBroadcast(c, what.hashCode(), i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Action.Builder(null, label, p).build();
    }

    /** 알림의 단추가 여기로 온다 */
    public static class Buttons extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent i) {
            if (!ACTION.equals(i.getAction())) return;
            String what = i.getStringExtra(WHAT);
            if ("pause".equals(what)) pause(c);
            else if ("resume".equals(what)) resume(c);
            else if ("plus".equals(what)) plus(c, 10);
            else if ("stop".equals(what)) stop(c, true);
            /* 화면에 떠 있는 얼굴들에게도 알린다 */
            c.sendBroadcast(new Intent(CHANGED).setPackage(c.getPackageName()));
        }
    }

    /** 상태가 바뀌었다 — 뷰어의 칩과 띄운 창의 바가 이것을 듣는다 */
    static final String CHANGED = "kr.gijul.direct.TIMER_CHANGED";

    static void changed(Context c) {
        show(c);
        c.sendBroadcast(new Intent(CHANGED).setPackage(c.getPackageName()));
    }
}
