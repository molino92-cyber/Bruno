package br.com.doceatelie;

import android.util.Base64;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/** SMTP autenticado somente após TLS, com validação do certificado e hostname. */
final class SmtpMailer {
    interface Transport { Socket connect(String host,int port) throws Exception; Socket secure(Socket socket,String host,int port) throws Exception; }
    static final Transport NETWORK=new Transport(){
        public Socket connect(String host,int port)throws Exception{Socket socket=new Socket();socket.connect(new InetSocketAddress(host,port),12000);socket.setSoTimeout(12000);return socket;}
        public Socket secure(Socket socket,String host,int port)throws Exception{
            SSLSocket ssl=(SSLSocket)((SSLSocketFactory)SSLSocketFactory.getDefault()).createSocket(socket,host,port,true);
            SSLParameters parameters=ssl.getSSLParameters();parameters.setEndpointIdentificationAlgorithm("HTTPS");ssl.setSSLParameters(parameters);ssl.setSoTimeout(12000);ssl.startHandshake();return ssl;
        }
    };
    static boolean email(String value){return value!=null&&value.matches("[^\\s<>@,;\\r\\n]+@[^\\s<>@,;\\r\\n]+\\.[^\\s<>@,;\\r\\n]+");}
    static void validate(JSONObject settings,String password)throws Exception{
        String host=settings.optString("smtp_host","");int port=settings.optInt("smtp_port",465);
        if(!host.matches("[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")||port<1||port>65535)throw new IllegalArgumentException("Confira o servidor e a porta SMTP.");
        if(!email(settings.optString("notification_email"))||!email(settings.optString("smtp_sender")))throw new IllegalArgumentException("Confira os e-mails de notificação e do remetente.");
        String security=settings.optString("smtp_security","SSL/TLS");if(!security.equals("SSL/TLS")&&!security.equals("STARTTLS"))throw new IllegalArgumentException("Escolha SSL/TLS ou STARTTLS.");
        String user=settings.optString("smtp_username");if(user.isEmpty()||user.contains("\r")||user.contains("\n")||password.isEmpty())throw new IllegalArgumentException("Cadastre o usuário e a senha de aplicativo.");
    }
    static void send(JSONObject settings,String password,String title,String text)throws Exception{send(settings,password,title,text,NETWORK);}
    static void send(JSONObject s,String password,String title,String text,Transport transport)throws Exception{
        validate(s,password);String host=s.getString("smtp_host");int port=s.getInt("smtp_port");Socket socket=transport.connect(host,port);
        try{
            boolean direct=s.optString("smtp_security","SSL/TLS").equals("SSL/TLS");
            if(direct)socket=transport.secure(socket,host,port);
            Session session=new Session(socket);session.expect(220);session.command("EHLO doce-atelie",250);
            if(!direct){session.command("STARTTLS",220);socket=transport.secure(socket,host,port);session=new Session(socket);session.command("EHLO doce-atelie",250);}
            session.command("AUTH LOGIN",334);session.command(encoded(s.getString("smtp_username")),334);session.command(encoded(password),235);
            session.command("MAIL FROM:<"+s.getString("smtp_sender")+">",250);session.command("RCPT TO:<"+s.getString("notification_email")+">",250);session.command("DATA",354);
            String body="From: <"+s.getString("smtp_sender")+">\r\nTo: <"+s.getString("notification_email")+">\r\nSubject: =?UTF-8?B?"+encoded(title.replace('\r',' ').replace('\n',' '))+"?=\r\nDate: "+java.time.ZonedDateTime.now().format(java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME)+"\r\nMessage-ID: <"+UUID.randomUUID()+"@doce-atelie.local>\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"+Base64.encodeToString(text.getBytes(StandardCharsets.UTF_8),Base64.CRLF).trim()+"\r\n.\r\n";
            session.write(body);session.expect(250);
            // A aceitação pelo servidor já conta como envio, mesmo se QUIT falhar.
            try{session.command("QUIT",221);}catch(Exception ignored){}
        }finally{try{socket.close();}catch(Exception ignored){}}
    }
    private static String encoded(String value){return Base64.encodeToString(value.getBytes(StandardCharsets.UTF_8),Base64.NO_WRAP);}
    private static final class Session{
        final BufferedReader input;final OutputStream output;
        Session(Socket socket)throws Exception{input=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.US_ASCII));output=socket.getOutputStream();}
        void write(String text)throws Exception{output.write(text.getBytes(StandardCharsets.US_ASCII));output.flush();}
        void command(String command,int code)throws Exception{write(command+"\r\n");expect(code);}
        void expect(int code)throws Exception{
            for(int i=0;i<100;i++){String line=input.readLine();if(line==null||line.length()>8192||line.length()<3||!line.startsWith(String.valueOf(code)))throw new IllegalStateException("O servidor SMTP recusou o envio.");if(line.length()<4||line.charAt(3)!='-')return;}
            throw new IllegalStateException("Resposta SMTP inválida.");
        }
    }
}
