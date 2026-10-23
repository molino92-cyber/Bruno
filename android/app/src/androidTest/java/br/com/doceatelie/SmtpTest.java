package br.com.doceatelie;

import android.test.AndroidTestCase;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

public class SmtpTest extends AndroidTestCase {
    static final class FakeSocket extends Socket {
        final ByteArrayOutputStream out=new ByteArrayOutputStream();final ByteArrayInputStream in;
        FakeSocket(String responses){in=new ByteArrayInputStream(responses.getBytes(StandardCharsets.US_ASCII));}
        @Override public java.io.InputStream getInputStream(){return in;}
        @Override public java.io.OutputStream getOutputStream(){return out;}
    }
    private JSONObject settings()throws Exception{return new JSONObject("{\"smtp_host\":\"smtp.example.com\",\"smtp_port\":465,\"smtp_security\":\"SSL/TLS\",\"smtp_username\":\"loja@example.com\",\"smtp_sender\":\"loja@example.com\",\"notification_email\":\"cozinha@example.com\"}");}
    public void testSslAndStartTlsNeverAuthenticateBeforeEncryption()throws Exception{
        for(boolean direct:new boolean[]{true,false}){
            JSONObject s=settings();s.put("smtp_security",direct?"SSL/TLS":"STARTTLS");
            FakeSocket plain=new FakeSocket("220 ready\r\n250 server\r\n220 TLS ready\r\n");
            FakeSocket secure=new FakeSocket((direct?"220 ready\r\n":"")+"250-server\r\n250 AUTH LOGIN\r\n334 user\r\n334 pass\r\n235 accepted\r\n250 sender\r\n250 recipient\r\n354 body\r\n250 queued\r\n");
            SmtpMailer.Transport transport=new SmtpMailer.Transport(){
                public Socket connect(String host,int port){return plain;}
                public Socket secure(Socket socket,String host,int port){return secure;}
            };
            SmtpMailer.send(s,"senha-ficticia","Minha loja · Lembrete","Encomenda às 14:00",transport);
            String raw=secure.out.toString("US-ASCII");assertTrue(raw,raw.contains("AUTH LOGIN\r\n"));assertTrue(raw,raw.contains("RCPT TO:<cozinha@example.com>"));assertTrue(raw,raw.contains("Content-Transfer-Encoding: base64"));assertFalse(raw.contains("senha-ficticia"));
            assertFalse(plain.out.toString("US-ASCII").contains("AUTH"));
            if(!direct)assertTrue(plain.out.toString("US-ASCII").contains("STARTTLS"));
        }
    }
    public void testHeaderInjectionAndUnencryptedTransportAreRejected()throws Exception{
        for(String key:new String[]{"smtp_sender","notification_email","smtp_host","smtp_security"}){
            JSONObject s=settings();s.put(key,"a\r\nBcc: atacante@example.com");
            try{SmtpMailer.validate(s,"senha-ficticia");fail("Configuração inválida deveria ser recusada");}catch(IllegalArgumentException expected){}
        }
    }
}
