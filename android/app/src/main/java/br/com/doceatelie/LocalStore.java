package br.com.doceatelie;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Iterator;

/** Cada documento e imagem tem sua própria linha, evitando o limite do CursorWindow. */
final class LocalStore extends SQLiteOpenHelper {
    private static final String[] COLLECTIONS = {"products", "customers", "inventory", "quotes"};
    LocalStore(Context context) { super(context, "doce-atelie.sqlite3", null, 1); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE documents (namespace TEXT NOT NULL, kind TEXT NOT NULL, identifier TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(namespace,kind,identifier))");
    }
    @Override public void onUpgrade(SQLiteDatabase db, int previous, int current) {
        throw new IllegalStateException("Migração de banco não disponível para esta versão.");
    }
    private String namespace(String mode) { return "demo".equals(mode) ? "demo" : "real"; }
    synchronized String load(String mode) throws Exception {
        SQLiteDatabase db = getReadableDatabase();
        JSONObject result = null;
        try (Cursor cursor = db.query("documents", new String[]{"payload"}, "namespace=? AND kind='meta'", new String[]{namespace(mode)}, null, null, null)) {
            if (cursor.moveToFirst()) result = new JSONObject(cursor.getString(0));
        }
        if (result == null) return "null";
        for (String kind : COLLECTIONS) {
            JSONArray list = new JSONArray();
            try (Cursor cursor = db.query("documents", new String[]{"payload"}, "namespace=? AND kind=?", new String[]{namespace(mode),kind}, null, null, "identifier")) {
                while (cursor.moveToNext()) list.put(new JSONObject(cursor.getString(0)));
            }
            result.put(kind,list);
        }
        JSONObject images = new JSONObject();
        try (Cursor cursor = db.query("documents", new String[]{"identifier","payload"}, "namespace=? AND kind='image'", new String[]{namespace(mode)}, null, null, null)) {
            while (cursor.moveToNext()) images.put(cursor.getString(0),cursor.getString(1));
        }
        result.put("images",images);
        return result.toString();
    }
    synchronized void save(String mode, String raw) throws Exception {
        if (raw.length()>40*1024*1024) throw new IllegalArgumentException("O cadastro excedeu o tamanho permitido para uma gravação.");
        JSONObject state = new JSONObject(raw);
        if (state.getInt("schema")!=1) throw new IllegalArgumentException("Formato de dados incompatível.");
        SQLiteDatabase db=getWritableDatabase();
        String ns=namespace(mode);
        db.beginTransaction();
        try {
            db.delete("documents","namespace=?",new String[]{ns});
            for (String kind : COLLECTIONS) {
                JSONArray list=state.getJSONArray(kind);
                for (int i=0;i<list.length();i++) {
                    JSONObject item=list.getJSONObject(i);
                    write(db,ns,kind,item.getString("id"),item.toString());
                }
                state.remove(kind);
            }
            JSONObject images=state.getJSONObject("images");
            Iterator<String> keys=images.keys();
            while(keys.hasNext()) {
                String key=keys.next();
                String image=images.getString(key);
                if (image.length()>900000 || !image.startsWith("data:image/")) throw new IllegalArgumentException("Imagem inválida ou muito grande.");
                write(db,ns,"image",key,image);
            }
            state.remove("images");
            write(db,ns,"meta","state",state.toString());
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    synchronized JSONObject notificationState() throws Exception {
        SQLiteDatabase db=getReadableDatabase();JSONObject result=null;
        try(Cursor cursor=db.query("documents",new String[]{"payload"},"namespace='real' AND kind='meta'",null,null,null,null)){
            if(cursor.moveToFirst())result=new JSONObject(cursor.getString(0));
        }
        if(result==null)return null;
        JSONArray quotes=new JSONArray();
        try(Cursor cursor=db.query("documents",new String[]{"payload"},"namespace='real' AND kind='quotes'",null,null,null,"identifier")){
            while(cursor.moveToNext())quotes.put(new JSONObject(cursor.getString(0)));
        }
        return result.put("quotes",quotes);
    }
    private void write(SQLiteDatabase db,String ns,String kind,String identifier,String payload) {
        ContentValues values=new ContentValues();
        values.put("namespace",ns);values.put("kind",kind);values.put("identifier",identifier);values.put("payload",payload);
        db.insertOrThrow("documents",null,values);
    }
}
