package kr.gijul.direct;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;

/** 테스트 APK에만 들어가는 문서 제공자. 실제 URI grant와 쓰기 실패를 재현한다. */
public class SafFixtureProvider extends DocumentsProvider {
    @Override public boolean onCreate() { return true; }
    private MatrixCursor document(String id, String[] projection) {
        String[] cols = projection == null ? new String[]{Document.COLUMN_DOCUMENT_ID,
                Document.COLUMN_DISPLAY_NAME, Document.COLUMN_MIME_TYPE, Document.COLUMN_FLAGS,
                Document.COLUMN_SIZE, Document.COLUMN_LAST_MODIFIED} : projection;
        MatrixCursor c = new MatrixCursor(cols);
        MatrixCursor.RowBuilder row = c.newRow();
        for (String col : cols) {
            Object value = null;
            if (Document.COLUMN_DOCUMENT_ID.equals(col)) value = id;
            else if (Document.COLUMN_DISPLAY_NAME.equals(col)) value = id + ".json";
            else if (Document.COLUMN_MIME_TYPE.equals(col)) value = "application/json";
            else if (Document.COLUMN_FLAGS.equals(col)) value = Document.FLAG_SUPPORTS_WRITE;
            else if (Document.COLUMN_SIZE.equals(col)) value = new File(getContext().getFilesDir(), id).length();
            row.add(value); // LAST_MODIFIED를 제공하지 않는 provider도 시험한다.
        }
        return c;
    }
    @Override public Cursor queryRoots(String[] projection) {
        MatrixCursor c = new MatrixCursor(new String[]{Root.COLUMN_ROOT_ID, Root.COLUMN_DOCUMENT_ID,
                Root.COLUMN_TITLE, Root.COLUMN_FLAGS, Root.COLUMN_MIME_TYPES});
        c.addRow(new Object[]{"fixture", "root", "SAF test", Root.FLAG_SUPPORTS_CREATE, "application/json"});
        return c;
    }
    @Override public Cursor queryDocument(String id, String[] projection) { return document(id, projection); }
    @Override public Cursor queryChildDocuments(String id, String[] projection, String order) { return document("good", projection); }
    @Override public ParcelFileDescriptor openDocument(String id, String mode, CancellationSignal cancel)
            throws FileNotFoundException {
        File file = new File(getContext().getFilesDir(), id);
        if ("failed".equals(id) && mode.contains("w")) {
            try (FileOutputStream out = new FileOutputStream(file)) { out.flush(); }
            catch (Exception e) { throw new FileNotFoundException(e.getMessage()); }
            throw new FileNotFoundException("provider failed after truncate");
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.parseMode(mode));
    }
}
