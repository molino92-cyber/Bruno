package br.com.doceatelie;

import android.test.AndroidTestCase;
import org.json.JSONObject;
import org.json.JSONArray;

public class LocalStoreTest extends AndroidTestCase {
    private LocalStore store;
    @Override protected void setUp() throws Exception {super.setUp();getContext().deleteDatabase("doce-atelie.sqlite3");store=new LocalStore(getContext());}
    @Override protected void tearDown() throws Exception {store.close();getContext().deleteDatabase("doce-atelie.sqlite3");super.tearDown();}
    private JSONObject empty() throws Exception {
        JSONObject value=new JSONObject();value.put("schema",1);value.put("settings",new JSONObject().put("name","Confeitaria"));
        for(String key:new String[]{"products","customers","inventory","quotes"})value.put(key,new JSONArray());
        return value.put("images",new JSONObject());
    }
    public void testPersistsClientsAndSeparatesDemonstration() throws Exception {
        JSONObject real=empty();real.getJSONArray("customers").put(new JSONObject().put("id","c1").put("name","Maria"));store.save("real",real.toString());store.save("demo",empty().toString());
        assertEquals("Maria",new JSONObject(store.load("real")).getJSONArray("customers").getJSONObject(0).getString("name"));
        assertEquals(0,new JSONObject(store.load("demo")).getJSONArray("customers").length());
        store.close();store=new LocalStore(getContext());assertEquals(1,new JSONObject(store.load("real")).getJSONArray("customers").length());
    }
    public void testRollbackPreservesDataWhenImageIsInvalid() throws Exception {
        JSONObject original=empty();store.save("real",original.toString());JSONObject invalid=empty();invalid.getJSONArray("customers").put(new JSONObject().put("id","c2"));invalid.getJSONObject("images").put("bad","https://example.com");
        try{store.save("real",invalid.toString());fail("Imagem inválida deveria impedir a gravação.");}catch(IllegalArgumentException expected){}
        assertEquals(0,new JSONObject(store.load("real")).getJSONArray("customers").length());
    }
    public void testImagesExceedingCursorWindowAreSplitIntoRows() throws Exception {
        JSONObject value=empty();String image="data:image/jpeg;base64,"+new String(new char[150000]).replace('\0','A');
        for(int i=0;i<20;i++)value.getJSONObject("images").put("foto-"+i,image);
        store.save("real",value.toString());assertEquals(20,new JSONObject(store.load("real")).getJSONObject("images").length());
    }
}
