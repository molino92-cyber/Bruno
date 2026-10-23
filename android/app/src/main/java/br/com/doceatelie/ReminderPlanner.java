package br.com.doceatelie;

import org.json.JSONArray;
import org.json.JSONObject;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

final class ReminderPlanner {
    static final class Reminder {
        final String key, quoteId, title, text;
        Reminder(String key,String quoteId,String title,String text){this.key=key;this.quoteId=quoteId;this.title=title;this.text=text;}
    }
    static List<Reminder> due(JSONObject state,LocalDateTime now) throws Exception {
        List<Reminder> result=new ArrayList<>();
        JSONObject settings=state.getJSONObject("settings");
        if(!settings.optBoolean("reminders_enabled",false))return result;
        LocalTime time=LocalTime.parse(settings.optString("alert_time","09:00"));
        JSONArray days=settings.optJSONArray("alert_days");if(days==null)days=new JSONArray("[3,2]");
        JSONArray quotes=state.getJSONArray("quotes");
        for(int i=0;i<quotes.length();i++){
            JSONObject quote=quotes.getJSONObject(i);
            if(quote.optBoolean("delivered"))continue;
            JSONObject totals=quote.optJSONObject("totals");if(totals==null)continue;
            long total=totals.optLong("total_cents",0),paid=0;
            JSONArray payments=quote.optJSONArray("payments");if(payments!=null)for(int j=0;j<payments.length();j++)paid+=payments.getJSONObject(j).optLong("amount_cents");
            if(total<=0||paid<(total+1)/2)continue;
            LocalDateTime event;
            try{event=LocalDateTime.parse(quote.getString("event_date")+"T"+quote.getString("event_time"));}catch(Exception invalid){continue;}
            if(!event.isAfter(now))continue;
            LocalDateTime latest=null;
            for(int j=0;j<days.length();j++){
                int offset=days.getInt(j);if(offset<0||offset>14)continue;
                LocalDateTime date=event.toLocalDate().minusDays(offset).atTime(time);
                if(!date.isAfter(now)&&(latest==null||date.isAfter(latest)))latest=date;
            }
            if(latest==null)continue;
            String number=String.format(java.util.Locale.ROOT,"%04d",quote.optInt("number",0));
            String text="Encomenda #"+number+" · "+quote.getJSONObject("customer").optString("name","Cliente")+"\nSaída: "+event.format(DateTimeFormatter.ofPattern("dd/MM/yyyy 'às' HH:mm"))+".\nConfira os detalhes e a ficha de produção no sistema.";
            String key=quote.getString("id")+"|"+event+"|"+latest.toLocalDate();
            result.add(new Reminder(key,quote.getString("id"),settings.optString("name","Confeitaria")+" · Lembrete de encomenda",text));
        }
        return result;
    }
}
