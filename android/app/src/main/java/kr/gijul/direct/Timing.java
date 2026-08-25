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
        String label = name(c);

        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CHANNEL) : new Notification.Builder(c);
        b.setSmallIcon(R.drawable.ic_timer)
                .setContentTitle(label.isEmpty() ? "시험 시간" : label)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setShowWhen(false)
                .setContentIntent(Widgets.open(c, null, 0x71));

        if (k.paused()) {
            b.setContentText("멈춤 · " + Clock.face(left) + " 남음");
            b.addAction(act(c, "resume", "이어서"));
        } else {
            /* 끝나는 시각을 건네고 세는 일은 시스템에 맡긴다. 우리가 잠들어도
               숫자가 흐르고, 잠금화면처럼 우리가 손댈 수 없는 자리에서도 흐른다. */
            b.setUsesChronometer(true).setWhen(now + left).setShowWhen(true);
            if (Build.VERSION.SDK_INT >= 24) b.setChronometerCountDown(left > 0);
            b.setContentText(left >= 0
                    ? (k.limit / 60000) + "분 중 남은 시간"
                    : (k.limit / 60000) + "분을 넘겼습니다");
            b.addAction(act(c, "pause", "일시정지"));
        }
        b.addAction(act(c, "plus", "10분 추가"));
        b.addAction(act(c, "stop", "끝내기"));
        b.setProgress(1000, Math.round(k.ratio(now) * 1000), false);

        try {
            nm.notify(NOTE_ID, b.build());
        } catch (Exception e) {
            /* 안드로이드 13+ 에서 알림 권한이 없으면 여기서 걸린다. 알림만 없을
               뿐 재는 것은 그대로다 — 뷰어의 칩과 띄운 창의 바가 남아 있다. */
            Log.w(TAG, "알림을 띄우지 못했습니다", e);
        }
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
