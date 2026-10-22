package br.com.doceatelie;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.util.Base64;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private WebView web;
    private LocalStore store;
    private ValueCallback<Uri[]> chooser;
    private byte[] pendingExport;
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private static final int PHOTO=21, EXPORT=22, IMPORT=23;
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        store=new LocalStore(this);
        getWindow().setStatusBarColor(Color.rgb(24,42,53));
        getWindow().setNavigationBarColor(Color.rgb(255,255,255));
        web=new WebView(this);
        setContentView(web);
        if (Build.VERSION.SDK_INT>=35) web.setOnApplyWindowInsetsListener((view,insets)->{
            android.graphics.Insets padding=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());
            view.setPadding(padding.left,padding.top,padding.right,padding.bottom);
            return insets;
        });
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        web.addJavascriptInterface(new Bridge(),"Android");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request) {
                Uri uri=request.getUrl();
                if ("file".equals(uri.getScheme()) && uri.toString().startsWith("file:///android_asset/")) return false;
                if (request.isForMainFrame() && "https".equals(uri.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW,uri)); } catch(Exception ignored){}
                }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> result,FileChooserParams params) {
                if(chooser!=null) chooser.onReceiveValue(null);
                chooser=result;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.setType("image/*");intent.addCategory(Intent.CATEGORY_OPENABLE);
                try {startActivityForResult(intent,PHOTO);} catch(Exception exc){chooser.onReceiveValue(null);chooser=null;message("Nenhum seletor de imagens foi encontrado.");}
                return true;
            }
            @Override public boolean onJsAlert(WebView view,String url,String text,android.webkit.JsResult result){
                new AlertDialog.Builder(MainActivity.this).setMessage(text).setPositiveButton("Entendi",(d,w)->result.confirm()).setOnCancelListener(d->result.cancel()).show();return true;
            }
        });
        web.loadUrl("file:///android_asset/index.html");
        if(Build.VERSION.SDK_INT>=33)getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,this::handleBack);
    }
    private void message(String text){runOnUiThread(()->new AlertDialog.Builder(this).setMessage(text).setPositiveButton("Entendi",null).show());}
    private void callback(String function,String value){runOnUiThread(()->web.evaluateJavascript("window."+function+"("+value+")",null));}
    private void export(byte[] bytes,String mime,String name){
        runOnUiThread(()->{
            if(pendingExport!=null){message("Conclua o salvamento anterior antes de exportar outro arquivo.");return;}
            pendingExport=bytes;
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,name);
            try{startActivityForResult(intent,EXPORT);}catch(Exception exc){pendingExport=null;message("Não foi possível abrir o local para salvar o arquivo.");}
        });
    }
    public final class Bridge {
        @JavascriptInterface public String loadState(String mode){try{return store.load(mode);}catch(Exception exc){return "{\"storageError\":true}";}}
        @JavascriptInterface public String saveState(String mode,String raw){
            try{store.save(mode,raw);return "";}catch(Exception exc){return "Não foi possível salvar. Confira o espaço livre do aparelho e tente novamente.";}
        }
        @JavascriptInterface public void exportBackup(String raw){export(raw.getBytes(StandardCharsets.UTF_8),"application/json","DoceAtelie-backup.json");}
        @JavascriptInterface public void importBackup(){runOnUiThread(()->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
            try{startActivityForResult(intent,IMPORT);}catch(Exception exc){message("Não foi possível selecionar o backup.");}
        });}
        @JavascriptInterface public void saveRestorePoint(String raw){
            try{File file=new File(getFilesDir(),"antes-da-restauracao.json");try(FileOutputStream out=new FileOutputStream(file)){out.write(raw.getBytes(StandardCharsets.UTF_8));}}catch(Exception exc){throw new IllegalStateException("Não foi possível criar a cópia anterior à restauração.");}
        }
        @JavascriptInterface public String restorePoint(){try(InputStream in=new java.io.FileInputStream(new File(getFilesDir(),"antes-da-restauracao.json"))){return new String(read(in,45*1024*1024),StandardCharsets.UTF_8);}catch(Exception exc){return "null";}}
        @JavascriptInterface public void savePdf(String uri,String name){try{export(pdfBytes(uri),"application/pdf",safeName(name));}catch(Exception exc){message("Não foi possível preparar o PDF.");}}
        @JavascriptInterface public void sharePdf(String uri,String name){
            try{
                byte[] bytes=pdfBytes(uri);
                File dir=new File(getCacheDir(),"pdfs");dir.mkdirs();
                File[] previous=dir.listFiles();if(previous!=null) for(File file:previous) if(file.lastModified()<System.currentTimeMillis()-7*86400000L) file.delete();
                File target=new File(dir,UUID.randomUUID().toString()+".pdf");
                try(FileOutputStream out=new FileOutputStream(target)){out.write(bytes);}
                Uri content=Uri.parse("content://"+getPackageName()+".pdf/"+target.getName()+"/"+safeName(name));
                runOnUiThread(()->{
                    Intent intent=new Intent(Intent.ACTION_SEND).setType("application/pdf").putExtra(Intent.EXTRA_STREAM,content).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    intent.setClipData(ClipData.newRawUri("PDF da confeitaria",content));
                    try{startActivity(Intent.createChooser(intent,"Compartilhar PDF"));}catch(Exception exc){message("Nenhum aplicativo foi encontrado para compartilhar o PDF.");}
                });
            }catch(Exception exc){message("Não foi possível compartilhar o PDF.");}
        }
        @JavascriptInterface public void lookupCep(String code,String requestId){
            if(!code.matches("[0-9]{8}")){postalResult(requestId,null,"Informe um CEP com oito dígitos.");return;}
            network.execute(()->{
                HttpURLConnection connection=null;
                try{
                    connection=(HttpURLConnection)new URL("https://viacep.com.br/ws/"+code+"/json/").openConnection();
                    connection.setConnectTimeout(6000);connection.setReadTimeout(6000);connection.setRequestProperty("Accept","application/json");
                    try(InputStream in=connection.getInputStream()){
                        JSONObject result=new JSONObject(new String(read(in,32000),StandardCharsets.UTF_8));
                        if(result.optBoolean("erro")) throw new IllegalArgumentException();
                        postalResult(requestId,result,"");
                    }
                }catch(Exception exc){postalResult(requestId,null,"Não foi possível consultar o CEP. Confira a internet ou preencha o endereço manualmente.");}
                finally{if(connection!=null)connection.disconnect();}
            });
        }
    }
    private String safeName(String name){return name.replaceAll("[^a-zA-Z0-9_.-]","_").replaceAll("^\\.+","");}
    private byte[] pdfBytes(String uri){
        if(uri.length()>35*1024*1024 || !uri.contains(","))throw new IllegalArgumentException();
        byte[] bytes=Base64.decode(uri.substring(uri.indexOf(',')+1),Base64.DEFAULT);
        if(bytes.length<5 || !new String(bytes,0,5,StandardCharsets.US_ASCII).equals("%PDF-"))throw new IllegalArgumentException();
        return bytes;
    }
    private void postalResult(String id,JSONObject result,String error){
        try{JSONObject payload=new JSONObject();payload.put("id",id);payload.put("result",result==null?JSONObject.NULL:result);payload.put("error",error);callback("onPostalResult",payload.toString());}catch(Exception ignored){}
    }
    private byte[] read(InputStream input,int limit)throws Exception{
        ByteArrayOutputStream output=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int size;
        while((size=input.read(buffer))!=-1){if(output.size()+size>limit)throw new IllegalArgumentException("Arquivo muito grande.");output.write(buffer,0,size);}return output.toByteArray();
    }
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==PHOTO){if(chooser!=null){chooser.onReceiveValue(result==RESULT_OK && data!=null?new Uri[]{data.getData()}:null);chooser=null;}return;}
        if(request==EXPORT){
            byte[] bytes=pendingExport;pendingExport=null;
            if(result==RESULT_OK && data!=null && bytes!=null){
                try(OutputStream out=getContentResolver().openOutputStream(data.getData())){if(out==null)throw new IllegalStateException();out.write(bytes);callback("onNativeNotice",JSONObject.quote("Arquivo salvo."));}
                catch(Exception exc){message("Não foi possível salvar o arquivo no local escolhido.");}
            }return;
        }
        if(request==IMPORT && result==RESULT_OK && data!=null){
            try(InputStream in=getContentResolver().openInputStream(data.getData())){
                String text=new String(read(in,45*1024*1024),StandardCharsets.UTF_8);
                callback("receiveBackup",new JSONObject(text).toString());
            }catch(Exception exc){message("Backup inválido ou acima de 45 MB.");}
        }
    }
    private void handleBack(){web.evaluateJavascript("window.appBack ? window.appBack() : false",result->{if(!"true".equals(result)) new AlertDialog.Builder(this).setMessage("Fechar o Doce Ateliê? Os dados salvos permanecerão no celular.").setPositiveButton("Fechar",(d,w)->finish()).setNegativeButton("Continuar",null).show();});}
    @Override public void onBackPressed(){handleBack();}
    @Override protected void onDestroy(){network.shutdownNow();web.removeJavascriptInterface("Android");web.destroy();store.close();super.onDestroy();}
}
