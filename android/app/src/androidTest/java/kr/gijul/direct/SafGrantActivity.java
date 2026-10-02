package kr.gijul.direct;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.DocumentsContract;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

public class SafGrantActivity extends Activity {
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        String id = getIntent().getStringExtra("document");
        try (FileOutputStream out = new FileOutputStream(new File(getFilesDir(), id))) {
            out.write(getIntent().getStringExtra("text").getBytes(StandardCharsets.UTF_8));
            Intent result = new Intent().setData(DocumentsContract.buildDocumentUri(
                    "kr.gijul.direct.test.fixture", id));
            result.addFlags(getIntent().getIntExtra("grants", 3) | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            setResult(RESULT_OK, result);
        } catch (Exception e) { setResult(RESULT_CANCELED); }
        finish();
    }
}
