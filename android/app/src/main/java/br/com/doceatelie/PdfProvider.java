package br.com.doceatelie;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;
import java.util.List;

/** Compartilha somente PDFs gerados no cache, por concessão temporária de leitura. */
public class PdfProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    private File target(Uri uri)throws FileNotFoundException{
        List<String> parts=uri.getPathSegments();
        if(parts.isEmpty() || !parts.get(0).matches("[a-f0-9-]{36}\\.pdf"))throw new FileNotFoundException();
        File file=new File(new File(getContext().getCacheDir(),"pdfs"),parts.get(0));
        if(!file.isFile())throw new FileNotFoundException();return file;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
        if(!"r".equals(mode))throw new FileNotFoundException();return ParcelFileDescriptor.open(target(uri),ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public String getType(Uri uri){return "application/pdf";}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){
        try{File file=target(uri);String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;
            MatrixCursor result=new MatrixCursor(columns);Object[] values=new Object[columns.length];
            List<String> parts=uri.getPathSegments();String name=parts.size()>1?parts.get(1):file.getName();
            for(int i=0;i<columns.length;i++)values[i]=OpenableColumns.SIZE.equals(columns[i])?file.length():OpenableColumns.DISPLAY_NAME.equals(columns[i])?name:null;
            result.addRow(values);return result;
        }catch(Exception exc){return null;}
    }
    @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
    @Override public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
    @Override public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}
