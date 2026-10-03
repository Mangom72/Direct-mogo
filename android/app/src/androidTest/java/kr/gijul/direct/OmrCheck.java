package kr.gijul.direct;

import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.os.SystemClock;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.File;
import java.io.FileInputStream;
import java.lang.reflect.Field;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Emulator smoke test. Push the repository fixture into files/omr-fixture first.
 * Does not claim physical camera recognition accuracy or contact a sync account. */
public class OmrCheck extends Instrumentation {
    WebView web;
    String js(String script) throws Exception {
        CountDownLatch done=new CountDownLatch(1);String[] value=new String[1];
        runOnMainSync(()->web.evaluateJavascript(script, v->{value[0]=v;done.countDown();}));
        if(!done.await(10,TimeUnit.SECONDS))throw new AssertionError("JS timeout");
        return value[0];
    }
    void waitFor(String script) throws Exception {
        for(int i=0;i<120;i++){if("true".equals(js(script)))return;SystemClock.sleep(250);}
        throw new AssertionError("Wait failed: "+script);
    }
    void check(String script) throws Exception {if(!"true".equals(js(script)))throw new AssertionError(script);}
    @Override public void onCreate(Bundle b){super.onCreate(b);start();}
    @Override public void onStart(){
        Bundle result=new Bundle();int code=-1;
        try{
            MainActivity activity=(MainActivity)startActivitySync(new Intent(getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            Field f=MainActivity.class.getDeclaredField("web");f.setAccessible(true);web=(WebView)f.get(activity);
            File root=new File(getTargetContext().getFilesDir(),"omr-fixture");
            if(!new File(root,"index.html").isFile())throw new AssertionError("Missing fixture");
            runOnMainSync(()->{
                web.setWebViewClient(new WebViewClient(){
                    @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest req){
                        try{
                            String path=req.getUrl().getPath();String prefix="/Direct-mogo/";
                            if(!path.startsWith(prefix))return new WebResourceResponse("text/plain","UTF-8",new java.io.ByteArrayInputStream(new byte[0]));
                            String relative=path.substring(prefix.length());if(relative.equals("omr-check.html"))relative="index.html";
                            File file=new File(root,relative);if(!file.getCanonicalPath().startsWith(root.getCanonicalPath()+"/"))return null;
                            String mime=relative.endsWith(".js")?"application/javascript":relative.endsWith(".css")?"text/css":relative.endsWith(".webp")?"image/webp":relative.endsWith(".woff2")?"font/woff2":"text/html";
                            return new WebResourceResponse(mime,"UTF-8",new FileInputStream(file));
                        }catch(Exception e){return new WebResourceResponse("text/plain","UTF-8",new java.io.ByteArrayInputStream(new byte[0]));}
                    }
                });
                web.loadUrl("https://mangom72.github.io/Direct-mogo/omr-check.html");
            });
            waitFor("!!document.querySelector('.item .record')");
            check("typeof GijulNative.scanOmr==='function'&&typeof GijulNative.pickOmrPhoto==='function'");
            js("localStorage.removeItem('gijul.omr.drafts.v1');sel.grp=GROUPS.D300.findIndex(g=>g[0]==='과학탐구');sel.sub='158';render();document.querySelector('.record').click();document.querySelector('#recordOmr').click();document.querySelector('#omrManual').click()");
            waitFor("!!document.querySelector('.omr-bubble')");
            check("document.querySelector('.omr-progress').textContent.includes('0/20')");
            js("document.querySelector('.omr-bubble[data-question=\"1\"][data-value=\"3\"]').click()");
            check("document.querySelector('.omr-progress').textContent.includes('1/20')");
            check("gijulBack()&&!document.querySelector('.omr-dialog')");
            // Cancellation is safe even when no scanner activity is open.
            js("GijulNative.cancelOmrScan('omr_cancel_check');gijulOmrScanResult('old_id',true,'invalid')");
            check("!document.querySelector('.omr-dialog')");
            runOnMainSync(activity::finish);
            result.putString("stream","PASS: Android WebView actual specimen input, scanner bridge, back, late result\nPhysical scanning not tested.\n");
        }catch(Throwable e){code=0;result.putString("stream",android.util.Log.getStackTraceString(e));}
        finish(code,result);
    }
}
