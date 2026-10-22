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
        // O formulário real grava a identidade no SQLite, e o cabeçalho a recupera após recarregar.
        String previous=(String)new org.json.JSONTokener(evaluate(activity,"JSON.stringify(state.settings)")).nextValue();
        String saved=evaluate(activity,"action('nav','settings');document.querySelector('#f_name').value='Doces e Afeto';document.querySelector('form[data-form=settings]').requestSubmit();JSON.stringify({header:document.querySelector('#shop-name').textContent,stored:JSON.parse(Android.loadState('real')).settings.name})");
        try {
            assertTrue(saved,saved.contains("Doces e Afeto"));
            assertTrue(saved,saved.contains("stored"));
            evaluate(activity,"location.reload();true");
            String reopened="";
            for(int attempt=0;attempt<30;attempt++){
                reopened=evaluate(activity,"document.querySelector('#shop-name')?.textContent");
                if(reopened.contains("Doces e Afeto"))break;
                Thread.sleep(300);
            }
            assertTrue(reopened,reopened.contains("Doces e Afeto"));
            assertEquals("Doces e Afeto · Gestão",new org.json.JSONTokener(evaluate(activity,"document.title")).nextValue());
        } finally {
            evaluate(activity,"commit(s=>s.settings="+previous+");render();true");
        }
    }

    private String evaluate(MainActivity activity,String script) throws Exception {
        CountDownLatch latch=new CountDownLatch(1);AtomicReference<String> result=new AtomicReference<>("");
        activity.runOnUiThread(()->{WebView view=(WebView)((android.view.ViewGroup)((android.view.ViewGroup)activity.findViewById(android.R.id.content)).getChildAt(0)).getChildAt(0);view.evaluateJavascript(script,value->{result.set(value);latch.countDown();});});
        assertTrue(latch.await(5,TimeUnit.SECONDS));return result.get();
    }
}
