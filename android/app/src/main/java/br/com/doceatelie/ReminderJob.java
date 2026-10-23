package br.com.doceatelie;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

/** Job persistente: continua após fechar a interface e reiniciar o aparelho. */
public class ReminderJob extends JobService {
    static final int PERIODIC=4101, IMMEDIATE=4102;
    static void schedule(Context context){
        try(LocalStore store=new LocalStore(context)){
            org.json.JSONObject state=store.notificationState();JobScheduler scheduler=context.getSystemService(JobScheduler.class);
            if(state==null||!state.getJSONObject("settings").optBoolean("reminders_enabled")){
                scheduler.cancel(PERIODIC);scheduler.cancel(IMMEDIATE);return;
            }
            ComponentName component=new ComponentName(context,ReminderJob.class);
            if(scheduler.getPendingJob(PERIODIC)==null)scheduler.schedule(new JobInfo.Builder(PERIODIC,component).setPeriodic(15*60*1000L).setPersisted(true).build());
            scheduler.schedule(new JobInfo.Builder(IMMEDIATE,component).setMinimumLatency(1000).build());
        }catch(Exception ignored){}
    }
    @Override public boolean onStartJob(JobParameters parameters){
        new Thread(()->{ReminderEngine.check(getApplicationContext());jobFinished(parameters,false);},"Lembretes de encomendas").start();return true;
    }
    @Override public boolean onStopJob(JobParameters parameters){return true;}
}
