package kr.gijul.direct;

import static org.junit.Assert.*;
import org.junit.Test;

public class PaperSourcesTest {
    private static final String KICE="https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=aec9a03dc37cda0f107fd6c1d175e6b8";
    private static final String MOE="https://www.moe.go.kr/boardCnts/fileDown.do?fileSeq=76dc225437d298122bc7000aab130487";
    private static final String EBS="https://www.ebsi.co.kr/ebs/ent/com/downLoadFileDefaultNew.ebs?fileGbn=1&bbsCd=B123&datNo=620487";
    @Test public void verifiedServletPDFsAreRecognized() {
        assertTrue(PaperSources.known(KICE));assertTrue(PaperSources.known(MOE));assertTrue(PaperSources.known(EBS));
        assertEquals("2028학년도 수능 예시문항.pdf",PaperSources.filename(MOE));
        assertEquals("2017학년도 수능 예시문항.pdf",PaperSources.filename("https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=6357e2f4036197724bb13027737a6edd"));
    }
    @Test public void arbitraryOfficialHostDownloadsAreBlocked() {
        for(String u:new String[]{null,"",MOE+"&fileSeq=other",MOE+"&redirect=https://evil.example/a.pdf",MOE+"#fragment",
                MOE.replace("https:","http:"),MOE.replace("www.moe.go.kr","www.moe.go.kr.evil.example"),
                MOE.replace("www.moe.go.kr","user@www.moe.go.kr"),MOE.replace("www.moe.go.kr","www.moe.go.kr:8443"),
                MOE.replace("76dc225437d298122bc7000aab130487","00000000000000000000000000000000"),
                "https://www.moe.go.kr/arbitrary.pdf",EBS+"&extra=1",EBS.replace("fileGbn=1","fileGbn=5")})
            assertFalse(u,PaperSources.known(u));
    }
    @Test public void sampleRedirectsCannotEscapeEvenToAnotherAllowedHost() {
        assertTrue(PaperSources.redirectAllowed(MOE,MOE));
        for(String target:new String[]{null,KICE,EBS,"https://wdown.ebsi.co.kr/arbitrary.pdf","https://evil.example/a.pdf"})
            assertFalse(PaperSources.redirectAllowed(MOE,target));
        assertFalse(PaperSources.redirectAllowed("https://evil.example/a.pdf","https://evil.example/a.pdf"));
    }
}
