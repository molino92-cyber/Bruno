package br.com.doceatelie;

import android.graphics.Insets;
import android.os.Build;
import android.test.ActivityInstrumentationTestCase2;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.webkit.WebView;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

public class SafeAreaTest extends ActivityInstrumentationTestCase2<MainActivity> {
    public SafeAreaTest(){super(MainActivity.class);}
    private ViewGroup safeArea(){return (ViewGroup)((ViewGroup)getActivity().findViewById(android.R.id.content)).getChildAt(0);}
    private WebView web(){return (WebView)safeArea().getChildAt(0);}
    private void assertMeasuredSafeArea(){
        ViewGroup root=safeArea();WebView view=web();
        assertEquals("O WebView deve começar abaixo da barra de status.",root.getPaddingTop(),view.getTop());
        assertEquals("O menu deve terminar antes da navegação Android.",root.getHeight()-root.getPaddingBottom(),view.getBottom());
        assertEquals(root.getPaddingLeft(),view.getLeft());
        assertEquals(root.getWidth()-root.getPaddingRight(),view.getRight());
        assertEquals("A área segura deve redimensionar o viewport, sem padding interno no WebView.",0,view.getPaddingTop());
        assertEquals(0,view.getPaddingBottom());
    }
    private void assertHtmlNavigation() throws Exception {
        AtomicReference<String> result=new AtomicReference<>("");
        for(int attempt=0;attempt<30;attempt++){
            CountDownLatch latch=new CountDownLatch(1);
            getActivity().runOnUiThread(()->web().evaluateJavascript("JSON.stringify({ready:!!document.querySelector('h1'),bottom:Math.round(document.querySelector('nav').getBoundingClientRect().bottom),height:window.innerHeight,buttons:document.querySelectorAll('nav button').length,icons:document.querySelectorAll('nav svg').length})",value->{result.set(value);latch.countDown();}));
            assertTrue(latch.await(5,TimeUnit.SECONDS));
            try{
                String raw=new org.json.JSONArray("["+result.get()+"]").getString(0);
                if(new org.json.JSONObject(raw).optBoolean("ready"))break;
            }catch(Exception ignored){}
            Thread.sleep(200);
        }
        String decoded=new org.json.JSONArray("["+result.get()+"]").getString(0);
        org.json.JSONObject value=new org.json.JSONObject(decoded);
        assertTrue(value.toString(),value.getBoolean("ready"));
        assertTrue("O menu inferior precisa caber no viewport.",Math.abs(value.getInt("bottom")-value.getInt("height"))<=1);
        assertEquals(5,value.getInt("buttons"));assertEquals(5,value.getInt("icons"));
    }
    public void testRealSystemBarsDoNotCoverHeaderOrBottomMenu() throws Exception {
        getActivity();assertHtmlNavigation();getInstrumentation().waitForIdleSync();
        getInstrumentation().runOnMainSync(()->{
            assertMeasuredSafeArea();
            if(Build.VERSION.SDK_INT>=30){
                WindowInsets original=safeArea().getRootWindowInsets();
                Insets bars=original.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
                assertTrue(safeArea().getPaddingTop()>=bars.top);
                assertTrue(safeArea().getPaddingBottom()>=bars.bottom);
                int appearance=getActivity().getWindow().getInsetsController().getSystemBarsAppearance();
                assertEquals(WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,appearance&WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
                assertEquals(0,appearance&WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS);
            }
        });
        assertHtmlNavigation();
    }
    private void applyInsets(int bottom,int keyboard) throws Exception {
        if(Build.VERSION.SDK_INT<30)return;
        getActivity();assertHtmlNavigation();getInstrumentation().waitForIdleSync();
        getInstrumentation().runOnMainSync(()->{
            ViewGroup root=safeArea();
            WindowInsets synthetic=new WindowInsets.Builder().setInsets(WindowInsets.Type.statusBars(),Insets.of(0,48,0,0))
                .setInsets(WindowInsets.Type.navigationBars(),Insets.of(0,0,0,bottom))
                .setInsets(WindowInsets.Type.displayCutout(),Insets.of(8,40,16,0))
                .setInsets(WindowInsets.Type.ime(),Insets.of(0,0,0,keyboard))
                .setVisible(WindowInsets.Type.statusBars()|WindowInsets.Type.navigationBars()|WindowInsets.Type.displayCutout(),true)
                .setVisible(WindowInsets.Type.ime(),keyboard>0).build();
            root.dispatchApplyWindowInsets(synthetic);
            root.measure(View.MeasureSpec.makeMeasureSpec(root.getWidth(),View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(root.getHeight(),View.MeasureSpec.EXACTLY));
            root.layout(root.getLeft(),root.getTop(),root.getRight(),root.getBottom());
            assertEquals(48,root.getPaddingTop());assertEquals(Math.max(bottom,keyboard),root.getPaddingBottom());
            assertEquals(8,root.getPaddingLeft());assertEquals(16,root.getPaddingRight());assertMeasuredSafeArea();
            root.requestApplyInsets();
        });
    }
    public void testThreeButtonNavigationAndDisplayCutoutResizeTheViewport() throws Exception {applyInsets(72,0);}
    public void testGestureNavigationKeepsItsOwnSafeArea() throws Exception {applyInsets(24,0);}
    public void testKeyboardUsesTheLargestInsetWithoutAddingItTwice() throws Exception {applyInsets(72,320);}
}
