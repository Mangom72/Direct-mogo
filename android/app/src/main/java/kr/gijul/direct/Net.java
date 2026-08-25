package kr.gijul.direct;

import android.net.Uri;

import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 밖에서 받아 오는 길은 전부 여기를 지난다.
 *
 * <h3>왜 한 곳으로 모았는가</h3>
 * 받는 자리가 세 군데였고(문제지·자료·APK) 셋이 똑같은 구멍을 나눠 갖고 있었다.
 * <b>주소를 한 번만 보고 나서 리디렉션은 따라가게</b> 두었던 것이다.
 *
 * {@code setInstanceFollowRedirects(true)} 는 302 를 만나면 묻지 않고 다음 주소로
 * 간다. 허용 목록은 첫 주소에만 걸려 있었으므로, 허용된 서버에 리디렉션 하나만
 * 열려 있으면 그 목록은 통째로 무의미해진다. HTTPS 라 도청은 막히지만, 어디서
 * 받아 왔는지를 우리가 모르게 된다는 것이 요점이다.
 *
 * 그래서 한 발씩 딛고 <b>디딜 때마다 다시 본다.</b>
 */
final class Net {

    /**
     * 어느 자리에서 받아도 되는가.
     *
     * {@code Uri} 가 아니라 <b>호스트 글자</b>를 받는다. 셈 자체는 안드로이드와
     * 아무 상관이 없는데 {@code android.net.Uri} 를 받으면 기기 없이는 값을 넣어
     * 볼 수가 없다. 여기는 틀려도 조용히 틀리는 자리라 —
     * {@code endsWith("ebsi.co.kr")} 는 {@code notebsi.co.kr} 도 받아 준다 —
     * 값을 넣어 보는 일이 특히 값지다({@code app/src/test} 참고).
     */
    interface Allow { boolean ok(String host); }

    /** 문제지는 EBSi 에서만 */
    static final Allow EBSI = h ->
            h != null && (h.equals("ebsi.co.kr") || h.endsWith(".ebsi.co.kr"));

    /** 회차 목록·과목 자료는 우리 사이트에서만 */
    static final Allow SITE = h -> "mangom72.github.io".equals(h);

    /**
     * 새 판 APK. 명세는 우리 사이트에 있고 자산은 릴리스에 있는데, github.com 이
     * 실제 파일이 있는 곳으로 한 번 넘긴다. 그 자리 이름은 깃허브가 조용히 바꾼다 —
     * 예전에는 objects.githubusercontent.com 이었고 지금은
     * release-assets.githubusercontent.com 이다. 그래서 하나를 못박지 않고
     * 그 도메인 아래를 받는다. 못박아 두었으면 이름이 바뀐 날 <b>모두의 자동
     * 갱신이 조용히 멈췄을 것</b>이다.
     */
    static final Allow RELEASE = h ->
            h != null && (h.equals("mangom72.github.io") || h.equals("github.com")
                    || h.equals("githubusercontent.com") || h.endsWith(".githubusercontent.com"));

    private static final int MAX_HOPS = 5;

    private Net() { }

    /** 주소를 확인하고 200 인 연결을 돌려준다. 리디렉션은 한 발씩 따라가며 매번 다시 본다. */
    static HttpURLConnection open(String url, Allow allow) throws Exception {
        String at = url;
        for (int hop = 0; ; hop++) {
            Uri u = Uri.parse(at == null ? "" : at);
            if (!"https".equals(u.getScheme()) || !allow.ok(u.getHost()))
                throw new Exception("허용되지 않는 주소입니다");

            HttpURLConnection c = (HttpURLConnection) new URL(at).openConnection();
            c.setConnectTimeout(20000);
            c.setReadTimeout(60000);
            c.setInstanceFollowRedirects(false);
            int code;
            try {
                code = c.getResponseCode();
            } catch (Exception e) {
                c.disconnect();
                throw e;
            }
            if (code == 200) return c;

            String next = (code >= 300 && code < 400) ? c.getHeaderField("Location") : null;
            c.disconnect();
            if (next == null || hop >= MAX_HOPS) throw new Exception("HTTP " + code);
            /* 상대 주소로 오는 곳이 있다. 지금 주소를 기준으로 푼다. */
            at = new URL(new URL(at), next).toString();
        }
    }
}
