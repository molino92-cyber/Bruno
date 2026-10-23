package br.com.doceatelie;

import android.test.AndroidTestCase;
import org.json.JSONObject;
import org.json.JSONArray;
import java.time.LocalDateTime;

public class ReminderTest extends AndroidTestCase {
    private JSONObject state()throws Exception{
        JSONObject settings=new JSONObject("{\"name\":\"Minha loja\",\"reminders_enabled\":true,\"alert_days\":[3,2],\"alert_time\":\"09:00\"}");
        JSONObject quote=new JSONObject("{\"id\":\"q1\",\"number\":1,\"event_date\":\"2027-01-01\",\"event_time\":\"14:00\",\"customer\":{\"name\":\"Ana\"},\"totals\":{\"total_cents\":15000},\"payments\":[{\"amount_cents\":7500}]}");
        return new JSONObject().put("settings",settings).put("quotes",new JSONArray().put(quote));
    }
    public void testCalendarThresholdCatchupAndDeliveredOrders()throws Exception{
        JSONObject state=state();LocalDateTime now=LocalDateTime.of(2026,12,29,9,0);
        assertEquals(0,ReminderPlanner.due(state,now.minusSeconds(1)).size());
        ReminderPlanner.Reminder first=ReminderPlanner.due(state,now).get(0);
        assertTrue(first.text,first.text.contains("01/01/2027 às 14:00"));
        assertFalse(first.key.equals(ReminderPlanner.due(state,now.plusDays(1)).get(0).key));
        assertEquals(1,ReminderPlanner.due(state,now.plusDays(2)).size());
        assertEquals(0,ReminderPlanner.due(state,LocalDateTime.of(2027,1,1,14,0)).size());
        JSONObject q=state.getJSONArray("quotes").getJSONObject(0);q.put("delivered",true);
        assertEquals(0,ReminderPlanner.due(state,now).size());q.put("delivered",false);q.put("payments",new JSONArray());
        assertEquals(0,ReminderPlanner.due(state,now).size());
    }
    public void testEncryptedPasswordDoesNotEnterStateOrBackup()throws Exception{
        getContext().getSharedPreferences("smtp-private",0).edit().clear().commit();
        try{
            MailCredentials.save(getContext(),"senha-ficticia-123");
            assertEquals("senha-ficticia-123",MailCredentials.load(getContext()));
            assertFalse(getContext().getSharedPreferences("smtp-private",0).getString("password","").contains("senha-ficticia-123"));
            assertFalse(state().toString().contains("senha-ficticia-123"));
        }finally{getContext().getSharedPreferences("smtp-private",0).edit().clear().commit();}
    }
    public void testPostedNotificationDeduplicatesAndStopsAfterDelivery()throws Exception{
        android.app.NotificationManager manager=getContext().getSystemService(android.app.NotificationManager.class);
        android.content.SharedPreferences ledger=getContext().getSharedPreferences("reminder-deliveries",0);
        assertTrue("Permissão POST_NOTIFICATIONS necessária no emulador",ReminderEngine.permission(getContext()));
        try(LocalStore store=new LocalStore(getContext())){
            String previous=store.load("real");manager.cancelAll();ledger.edit().clear().commit();
            try{
                JSONObject value=state();value.put("schema",1).put("images",new JSONObject());
                for(String kind:new String[]{"products","customers","inventory"})value.put(kind,new JSONArray());
                value.getJSONObject("settings").put("alert_time","00:00");
                JSONObject quote=value.getJSONArray("quotes").getJSONObject(0);quote.put("event_date",java.time.LocalDate.now().plusDays(3).toString());
                store.save("real",value.toString());ReminderEngine.check(getContext());
                awaitCount(manager,1);
                manager.cancelAll();awaitCount(manager,0);ReminderEngine.check(getContext());Thread.sleep(150);assertEquals(0,manager.getActiveNotifications().length);
                quote.put("delivered",true).put("event_date",java.time.LocalDate.now().plusDays(2).toString());store.save("real",value.toString());
                ReminderEngine.check(getContext());assertEquals(0,manager.getActiveNotifications().length);
            }finally{
                manager.cancelAll();ledger.edit().clear().commit();
                if(!previous.equals("null"))store.save("real",previous);else store.getWritableDatabase().delete("documents","namespace=?",new String[]{"real"});
            }
        }
    }
    private void awaitCount(android.app.NotificationManager manager,int count)throws Exception{
        for(int attempt=0;attempt<40;attempt++){
            if(manager.getActiveNotifications().length==count)return;
            Thread.sleep(50);
        }
        assertEquals(count,manager.getActiveNotifications().length);
    }
    public void testPersistentJobCanBeEnabledAndCancelledWithoutChangingCadastros()throws Exception{
        try(LocalStore store=new LocalStore(getContext())){
            String old=store.load("real");
            try{
                JSONObject value=new JSONObject().put("schema",1).put("settings",state().getJSONObject("settings")).put("images",new JSONObject());
                for(String kind:new String[]{"products","customers","inventory","quotes"})value.put(kind,new JSONArray());
                store.save("real",value.toString());ReminderJob.schedule(getContext());
                android.app.job.JobScheduler scheduler=getContext().getSystemService(android.app.job.JobScheduler.class);
                android.app.job.JobInfo job=scheduler.getPendingJob(ReminderJob.PERIODIC);
                assertNotNull(job);assertTrue(job.isPersisted());assertTrue(job.isPeriodic());
                value.getJSONObject("settings").put("reminders_enabled",false);store.save("real",value.toString());ReminderJob.schedule(getContext());
                assertNull(scheduler.getPendingJob(ReminderJob.PERIODIC));
            }finally{
                getContext().getSystemService(android.app.job.JobScheduler.class).cancel(ReminderJob.PERIODIC);getContext().getSystemService(android.app.job.JobScheduler.class).cancel(ReminderJob.IMMEDIATE);
                if(!old.equals("null"))store.save("real",old);else store.getWritableDatabase().delete("documents","namespace=?",new String[]{"real"});
            }
        }
    }
}
