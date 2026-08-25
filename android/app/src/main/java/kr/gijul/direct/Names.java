package kr.gijul.direct;

/**
 * 이름을 다루는 순수한 셈. <b>안드로이드가 없어도 돈다.</b>
 *
 * <h3>왜 따로 두는가</h3>
 * 여기 있는 것들은 값을 넣으면 답이 정해지는 함수다. 그런데 예전에는 {@code safe}
 * 가 {@code MainActivity} 안에 있었다 — {@code Activity} 를 상속한 클래스라
 * 불러오는 것만으로 안드로이드 틀이 딸려 와서, 기기 없이는 확인할 길이 없었다.
 *
 * 경로를 거르는 자리는 틀리면 <b>조용히</b> 틀린다. 화면에서는 아무 일도 안
 * 일어나고 파일만 엉뚱한 데 쓰인다. 그런 것일수록 기기를 켜지 않고도 값을 넣어
 * 볼 수 있어야 한다({@code app/src/test} 참고).
 */
final class Names {

    private Names() { }

    /**
     * 파일·폴더 이름으로 받아도 되는가.
     *
     * 페이지가 건네는 값이라 경계를 건너온다. 여기서 막는 것은 <b>자리를 벗어나는
     * 것</b>이다 — 구분자가 섞이면 우리 폴더 밖에 쓰게 되고, 점 하나와 점 둘은
     * 그 자체로 자리를 가리킨다.
     */
    static String safe(String s) throws Exception {
        if (s == null || s.isEmpty() || s.equals(".") || s.equals("..")
                || s.indexOf('/') >= 0 || s.indexOf('\\') >= 0 || s.indexOf('\0') >= 0)
            throw new Exception("허용되지 않는 이름입니다");
        return s;
    }

    /** "20260824" → "8.24". 못 읽으면 빈 글자. */
    static String mmdd(String ymd) {
        try {
            return Integer.parseInt(ymd.substring(4, 6)) + "."
                    + Integer.parseInt(ymd.substring(6, 8));
        } catch (Exception e) {
            return "";
        }
    }
}
