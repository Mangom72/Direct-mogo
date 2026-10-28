package kr.gijul.direct;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/** tools/build_sample_sources.py generates this exact list from the verified sample catalog.
 * Host-wide MOE/KICE downloads and redirected targets are not permitted. */
final class PaperSources {
    private PaperSources() { }
    private static final Map<String, Integer> PDFS = sources();
    private static Map<String, Integer> sources() {
        Map<String, Integer> out = new HashMap<>();
        out.put("https://www.ebsi.co.kr/ebs/ent/com/downLoadFileDefaultNew.ebs?fileGbn=1&bbsCd=B123&datNo=620487", 2028);
        out.put("https://www.ebsi.co.kr/ebs/ent/com/downLoadFileDefaultNew.ebs?fileGbn=2&bbsCd=B123&datNo=620487", 2028);
        out.put("https://www.ebsi.co.kr/ebs/ent/com/downLoadFileDefaultNew.ebs?fileGbn=3&bbsCd=B123&datNo=620487", 2028);
        out.put("https://www.ebsi.co.kr/ebs/ent/com/downLoadFileDefaultNew.ebs?fileGbn=4&bbsCd=B123&datNo=620487", 2028);
        out.put("https://www.moe.go.kr/boardCnts/fileDown.do?fileSeq=76dc225437d298122bc7000aab130487", 2028);
        out.put("https://www.moe.go.kr/boardCnts/fileDown.do?fileSeq=ee517bedf5aa88ac3c1e3669051a8a3e", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=0675e3a5019f6c4b98147a499311297c", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=06eff0322c90fe3f587d2581c9b91367", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=0f946c8e039659ca355e82e21e850bb1", 2018);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=1f42deaec52059f97e169964668b4b5c", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=2d61407c6b2d3083455e0a4b8dd105bb", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=4b0c957f57a31b0fea30b89930f4a2ad", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=4c56e911ea50fb545ae4bfdacb8757a6", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=58ff395b233bcf231e7a85022452c296", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=6357e2f4036197724bb13027737a6edd", 2017);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=77becfb1bab058dde44856ebb6bbaa6b", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=82ec89b4b761175225370a71be3b9b2d", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=a0aa9b435bbb3c95ff484e5ba97fc27d", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=ae2aa58e13f8e1f2fda19de1b9143a37", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=aec9a03dc37cda0f107fd6c1d175e6b8", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=c29a5e922183e4f919b1cc829583875b", 2022);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=cfec8872947730855f1217c429063a8b", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=fbed99539b82f77cb4bb612dcb2c8e5a", 2028);
        out.put("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=fc6ee108c3bfcf8ca0373f854c1c595b", 2028);
        return Collections.unmodifiableMap(out);
    }
    static boolean known(String url) { return url != null && PDFS.containsKey(url); }
    static String filename(String url) {
        Integer year = PDFS.get(url);
        return year == null ? null : year + "학년도 수능 예시문항.pdf";
    }
    static boolean redirectAllowed(String initial, String target) {
        return known(initial) && initial.equals(target);
    }
}
