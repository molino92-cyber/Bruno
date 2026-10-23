package br.com.doceatelie;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONObject;

/** Senha fica cifrada pelo Android Keystore e nunca entra no backup de cadastros. */
final class MailCredentials {
    private static final String ALIAS="doce-smtp-v1";
    private static SecretKey key() throws Exception {
        KeyStore keys=KeyStore.getInstance("AndroidKeyStore");keys.load(null);
        if(keys.containsAlias(ALIAS))return (SecretKey)keys.getKey(ALIAS,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }
    static synchronized void save(Context context,String password) throws Exception {
        if(password.isEmpty())return;
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        JSONObject value=new JSONObject().put("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).put("value",Base64.encodeToString(cipher.doFinal(password.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP));
        if(!context.getSharedPreferences("smtp-private",Context.MODE_PRIVATE).edit().putString("password",value.toString()).commit())throw new IllegalStateException("Falha ao guardar a senha.");
    }
    static synchronized String load(Context context) throws Exception {
        String raw=context.getSharedPreferences("smtp-private",Context.MODE_PRIVATE).getString("password","");if(raw.isEmpty())return "";
        JSONObject value=new JSONObject(raw);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(value.getString("iv"),Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(value.getString("value"),Base64.NO_WRAP)),java.nio.charset.StandardCharsets.UTF_8);
    }
}
