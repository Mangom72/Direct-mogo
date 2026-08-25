package kr.gijul.direct;

/**
 * 과목마다 정해진 시험 시간.
 *
 * <h3>지금 기준만 담는다</h3>
 * 시험 시간은 교육과정이 바뀔 때 함께 바뀌었다 — 2013년 이전 언어영역은
 * 50문항 90분이었다. 자료는 2006년 시행분부터 있으므로, 표 하나로 못박으면
 * <b>옛 회차에서 조용히 틀린다.</b> 화면에는 멀쩡한 숫자가 흐르고 어긋난 것은
 * 아무 데서도 안 보인다.
 *
 * 그래서 지금 기준만 담고, 나머지는 '직접 정하기'로 연다. 아는 것만 적고 모르는
 * 것은 사람에게 맡기는 편이, 그럴듯한 값을 지어내는 것보다 낫다.
 *
 * <h3>영어의 두 갈래</h3>
 * 영어는 70분인데 앞의 17문항이 듣기다. 듣기 방송 파일은 EBSi에 따로 있고 이
 * 화면은 담지 않으므로, 듣기 없이 푸는 사람이 많다. 그때 70분은 너무 길다.
 */
final class Exam {

    private Exam() { }

    /** 한 갈래 — 화면에 알약으로 뜬다 */
    static final class Choice {
        final int minutes;
        final String label;
        Choice(int minutes, String label) { this.minutes = minutes; this.label = label; }
    }

    /**
     * 과목 이름으로 시간을 고른다. 과목군이 아니라 <b>과목 이름</b>을 받는 것은
     * 앱이 들고 있는 것이 그것이어서다(GijulNative.openPaperAt 이 건네준다).
     *
     * @return 고를 수 있는 것들. 비면 아는 시간이 없다는 뜻이라 '직접 정하기'만 낸다.
     */
    static Choice[] choices(String subject) {
        String s = subject == null ? "" : subject;

        if (s.equals("영어")) {
            return new Choice[]{
                    new Choice(70, "70분 — 듣기 포함"),
                    new Choice(50, "50분 — 듣기 빼고"),
            };
        }
        int m = minutes(s);
        return m > 0 ? new Choice[]{ new Choice(m, m + "분") } : new Choice[0];
    }

    /** 아는 시간(분). 모르면 0. */
    static int minutes(String subject) {
        String s = subject == null ? "" : subject;
        if (s.equals("화법과 작문") || s.equals("언어와 매체") || s.equals("국어")) return 80;
        if (s.equals("확률과 통계") || s.equals("미적분") || s.equals("기하") || s.equals("수학")) return 100;
        if (s.equals("영어")) return 70;
        if (s.equals("한국사")) return 30;
        if (s.startsWith("제2외국어") || SECOND.contains("|" + s + "|")) return 40;
        /* 사회·과학·직업탐구는 과목마다 30분이다. 위에서 안 걸린 것은 전부 탐구로
           본다 — 탐구 과목이 마흔 남짓이라 하나씩 적는 것보다 이쪽이 덜 어긋난다. */
        return 30;
    }

    /* 제2외국어·한문은 40분이다. 이름이 저마다라 한 줄에 모아 둔다. */
    private static final String SECOND =
            "|독일어Ⅰ|프랑스어Ⅰ|스페인어Ⅰ|중국어Ⅰ|일본어Ⅰ|러시아어Ⅰ|아랍어Ⅰ|베트남어Ⅰ|한문Ⅰ|";

    /** '수학은 100분입니다' 처럼 한 줄로 */
    static String says(String subject) {
        int m = minutes(subject);
        if ("영어".equals(subject)) return "영어는 70분입니다. 듣기 없이 푸시려면 50분을 고르십시오.";
        return (subject == null ? "이 과목" : subject) + "은(는) " + m + "분입니다.";
    }
}
