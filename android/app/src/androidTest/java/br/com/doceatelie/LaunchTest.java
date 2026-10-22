package br.com.doceatelie;

import android.test.ActivityInstrumentationTestCase2;
import android.webkit.WebView;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

public class LaunchTest extends ActivityInstrumentationTestCase2<MainActivity> {
    public LaunchTest(){super(MainActivity.class);}
    public void testRealApkLoadsLocalInterfaceAndNativeBridge() throws Exception {
        MainActivity activity=getActivity();AtomicReference<String> result=new AtomicReference<>("");
        for(int attempt=0;attempt<30;attempt++){
            CountDownLatch latch=new CountDownLatch(1);
            activity.runOnUiThread(()->{WebView view=(WebView)((android.view.ViewGroup)((android.view.ViewGroup)activity.findViewById(android.R.id.content)).getChildAt(0)).getChildAt(0);if(view==null){latch.countDown();return;}view.evaluateJavascript("JSON.stringify({heading:document.querySelector('h1')?.textContent,bridge:typeof Android,products:window.DOCE_SEED?.products.length})",value->{result.set(value);latch.countDown();});});
            assertTrue(latch.await(5,TimeUnit.SECONDS));if(result.get().contains("Sua confeitaria em dia")&&result.get().contains("object"))break;Thread.sleep(300);
        }
        assertTrue(result.get(),result.get().contains("Sua confeitaria em dia"));assertTrue(result.get(),result.get().contains("object"));assertTrue(result.get(),result.get().contains("12"));
    }
}
