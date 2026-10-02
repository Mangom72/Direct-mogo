package kr.gijul.direct;
import android.app.Instrumentation;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.util.Map;
public class FloatCheck extends Instrumentation {
    Context target; Object service; StringBuilder log=new StringBuilder();
    Object get(Object o,String n) { try { Field f=o.getClass().getDeclaredField(n); f.setAccessible(true); return f.get(o); } catch(Exception e) {throw new RuntimeException(e);} }
    void main(Runnable r) { Throwable[] failure=new Throwable[1]; runOnMainSync(() -> {try {r.run();}catch(Throwable t){failure[0]=t;}}); if(failure[0]!=null)throw new AssertionError(failure[0]); SystemClock.sleep(800); }
    void seed(long left,boolean pause) { main(() -> { long now=System.currentTimeMillis(); target.getSharedPreferences("timing",0).edit().putLong("limit",7200000).putLong("from",now-7200000+left).putLong("paused",pause?now:0).commit(); target.sendBroadcast(new Intent("kr.gijul.direct.TIMER_CHANGED").setPackage(target.getPackageName())); }); }
    void click(String name) { main(() -> ((View)get(service,name)).performClick()); }
    int check(String label) {
        int[] width=new int[1]; main(() -> {
            View bar=(View)get(service,"bar"); LinearLayout row=(LinearLayout)get(service,"row");
            WindowManager.LayoutParams lp=(WindowManager.LayoutParams)get(service,"barLp"); GradientDrawable bg=(GradientDrawable)get(service,"barBg");
            width[0]=lp.width;
            if(bar.getWidth()!=lp.width || bg.getBounds().width()!=lp.width) throw new AssertionError("View/window/border widths differ: "+bar.getWidth()+"/"+lp.width+"/"+bg.getBounds());
            int last=row.getPaddingLeft();
            for(int i=0;i<row.getChildCount();i++) {
                View c=row.getChildAt(i); if(c.getVisibility()!=View.VISIBLE)continue;
                if(c.getLeft()<last || c.getRight()>row.getWidth()-row.getPaddingRight()) throw new AssertionError("Control clipped: "+c+" "+c.getLeft()+".."+c.getRight()+" in "+row.getWidth());
                if(c instanceof TextView) {TextView t=(TextView)c; if(t.getLayout()!=null && t.getLayout().getLineWidth(0)>t.getWidth()-t.getPaddingLeft()-t.getPaddingRight()+1) throw new AssertionError("Text clipped: "+t.getText());}
                last=c.getRight();
            }
            if(lp.x<0 || lp.x+lp.width>target.getResources().getDisplayMetrics().widthPixels) throw new AssertionError("Outside screen");
            log.append(label+": window/border "+lp.width+" px, all text and controls contained\n");
        }); return width[0];
    }
    @Override public void onCreate(Bundle b) { super.onCreate(b); start(); }
    @Override public void onStart() {
        int code=-1; Bundle summary=new Bundle();
        try {
            target=getTargetContext(); File picture=new File(target.getCacheDir(),"popup-check.png"); Bitmap bitmap=Bitmap.createBitmap(64,64,Bitmap.Config.ARGB_8888); bitmap.eraseColor(-1);
            try(FileOutputStream out=new FileOutputStream(picture)){bitmap.compress(Bitmap.CompressFormat.PNG,100,out);}
            target.getSharedPreferences("timing",0).edit().putString("done", "[{\"k\":\"D300/158/20250101/시험\",\"spent\":600,\"limit\":1200}]").commit();
            String pending=Timing.peekRecords(target);
            if(!pending.equals(Timing.peekRecords(target)))throw new AssertionError("Peek lost record or changed ID");
            org.json.JSONArray records=new org.json.JSONArray(pending);
            String id=records.getJSONObject(0).getString("id");
            records.put(new org.json.JSONObject().put("id","later").put("k","D300/158/20250102/시험").put("spent",60));
            target.getSharedPreferences("timing",0).edit().putString("done",records.toString()).commit();
            Timing.acknowledgeRecords(target,new org.json.JSONArray().put(id).toString());
            if(new org.json.JSONArray(Timing.peekRecords(target)).length()!=1)throw new AssertionError("ACK removed newer record");
            Timing.acknowledgeRecords(target,"[\"later\"]");
            if(!"[]".equals(Timing.peekRecords(target)))throw new AssertionError("ACK did not clear");
            log.append("persistent timing peek/ACK, newer record retention: PASS\n");
            seed(3900000,false); main(() -> target.startForegroundService(new Intent(target,FloatService.class).putExtra("file",picture.getAbsolutePath()).putExtra("name","Popup check")));
            Class<?> at=Class.forName("android.app.ActivityThread"); Object thread=at.getMethod("currentActivityThread").invoke(null);
            for(Object s:((Map<?,?>)get(thread,"mServices")).values())if(s.getClass().getName().equals("kr.gijul.direct.FloatService"))service=s;
            if(service==null)throw new AssertionError("Service missing");
            click("minBtn"); int active=check("running over one hour"); click("timeChip");
            if(Timing.clock(target).paused())throw new AssertionError("Timer tap paused without menu action");
            main(() -> ((LinearLayout)((android.widget.PopupWindow)get(service,"timerMenu")).getContentView()).getChildAt(0).performClick());
            if(check("paused by menu action")<=active)throw new AssertionError("Pause did not grow window");
            click("timeChip");
            main(() -> ((LinearLayout)((android.widget.PopupWindow)get(service,"timerMenu")).getContentView()).getChildAt(0).performClick());
            check("resumed by menu action"); seed(590000,false); check("under ten minutes"); seed(-3900000,false); check("overtime over one hour"); seed(-3900000,true); check("paused overtime");
            click("minBtn"); check("expanded active timer, essential actions contained"); click("minBtn");
            Bitmap screenshot=getUiAutomation().takeScreenshot(); try(FileOutputStream out=new FileOutputStream(new File(target.getFilesDir(),"popup-check.png"))){screenshot.compress(Bitmap.CompressFormat.PNG,100,out);}
            main(() -> {target.getSharedPreferences("timing",0).edit().clear().commit(); target.sendBroadcast(new Intent("kr.gijul.direct.TIMER_CHANGED").setPackage(target.getPackageName()));});
            if(check("timer stopped")>=active)throw new AssertionError("Stop did not shrink window");
            click("minBtn"); if(((View)get(service,"menuBtn")).getVisibility()!=View.VISIBLE)throw new AssertionError("Toolbar not restored");
            log.append("expand restored toolbar\nPASS\n");
        } catch(Throwable t){code=0;log.append(android.util.Log.getStackTraceString(t));}
        finally {if(target!=null)main(() -> target.stopService(new Intent(target,FloatService.class)));}
        summary.putString("stream",log.toString()); finish(code,summary);
    }
}
