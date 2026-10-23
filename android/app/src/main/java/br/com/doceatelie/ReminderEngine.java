package br.com.doceatelie;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.List;

final class ReminderEngine {
    static final String CHANNEL="encomendas";
    static boolean permission(Context context){return (Build.VERSION.SDK_INT<33||context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED)&&context.getSystemService(NotificationManager.class).areNotificationsEnabled();}
    static synchronized void check(Context context){
        SharedPreferences ledger=context.getSharedPreferences("reminder-deliveries",Context.MODE_PRIVATE);
        try(LocalStore store=new LocalStore(context)){
            JSONObject state=store.notificationState();if(state==null)return;
            JSONObject settings=state.getJSONObject("settings");if(!settings.optBoolean("reminders_enabled"))return;
            List<ReminderPlanner.Reminder> due=ReminderPlanner.due(state,LocalDateTime.now());
            ledger.edit().putString("last_check",LocalDateTime.now().toString()).remove("error").apply();
            for(ReminderPlanner.Reminder reminder:due){
                if(settings.optBoolean("local_notifications",true))deliver(context,ledger,reminder,"local",settings);
                if(settings.optBoolean("email_enabled",false))deliver(context,ledger,reminder,"email:"+settings.optString("notification_email"),settings);
            }
        }catch(Exception ignored){ledger.edit().putString("error","Não foi possível verificar os lembretes. Abra o aplicativo e confira os dados.").apply();}
    }
    private static void deliver(Context context,SharedPreferences ledger,ReminderPlanner.Reminder reminder,String channel,JSONObject settings)throws Exception{
        String key=key(reminder.key+"|"+channel);long now=System.currentTimeMillis();
        if(ledger.getBoolean("sent-"+key,false)||ledger.getLong("retry-"+key,0)>now)return;
        try{
            if(channel.equals("local"))show(context,reminder);
            else SmtpMailer.send(settings,MailCredentials.load(context),reminder.title,reminder.text);
            ledger.edit().putBoolean("sent-"+key,true).remove("retry-"+key).remove("error-"+channel).commit();
        }catch(Exception ignored){
            String error=channel.equals("local")?"Notificações bloqueadas. Permita os avisos nas configurações do celular.":"E-mail não enviado. Confira a internet, o servidor SMTP e a senha de aplicativo. Nova tentativa em cerca de 15 minutos.";
            ledger.edit().putLong("retry-"+key,now+15*60*1000).putString("error-"+channel,error).commit();
        }
    }
    static String key(String raw)throws Exception{
        byte[] bytes=MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8));StringBuilder result=new StringBuilder();
        for(byte value:bytes)result.append(String.format(java.util.Locale.ROOT,"%02x",value));return result.toString();
    }
    static void show(Context context,ReminderPlanner.Reminder reminder){
        if(!permission(context))throw new IllegalStateException("Notificações bloqueadas.");
        NotificationManager manager=context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL,"Lembretes de encomendas",NotificationManager.IMPORTANCE_HIGH));
        Intent intent=new Intent(context,MainActivity.class).putExtra("quote_id",reminder.quoteId).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent open=PendingIntent.getActivity(context,reminder.quoteId.hashCode(),intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(context,CHANNEL).setSmallIcon(R.drawable.ic_notification).setContentTitle(reminder.title).setContentText(reminder.text.replace('\n',' ')).setStyle(new Notification.BigTextStyle().bigText(reminder.text)).setContentIntent(open).setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE).build();
        manager.notify(reminder.key.hashCode(),notification);
    }
    static String status(Context context){
        try{
            SharedPreferences ledger=context.getSharedPreferences("reminder-deliveries",Context.MODE_PRIVATE);JSONObject result=new JSONObject();
            result.put("permission",permission(context));result.put("has_password",!MailCredentials.load(context).isEmpty());result.put("last_check",ledger.getString("last_check",""));
            String error=ledger.getString("error","");
            for(java.util.Map.Entry<String,?> row:ledger.getAll().entrySet())if(row.getKey().startsWith("error-")&&row.getValue() instanceof String)error=(String)row.getValue();
            result.put("error",error);return result.toString();
        }catch(Exception ignored){return "{\"permission\":false,\"has_password\":false,\"error\":\"Cadastre novamente a senha de aplicativo neste celular.\"}";}
    }
}
