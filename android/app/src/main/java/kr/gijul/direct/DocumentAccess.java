package kr.gijul.direct;

import android.content.ContentResolver;
import android.content.Intent;
import android.content.UriPermission;
import android.net.Uri;

/** 고르기가 실제로 준 권한만 붙들고, 다음 실행에도 남았는지 확인한다. */
final class DocumentAccess {
    static final int READ_WRITE = Intent.FLAG_GRANT_READ_URI_PERMISSION
            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION;

    static int grantedFlags(int resultFlags) { return resultFlags & READ_WRITE; }

    static boolean persisted(ContentResolver resolver, Uri uri) {
        if (uri == null || !"content".equals(uri.getScheme())) return false;
        for (UriPermission permission : resolver.getPersistedUriPermissions()) {
            if (uri.equals(permission.getUri()) && permission.isReadPermission()
                    && permission.isWritePermission()) return true;
        }
        return false;
    }

    static void take(ContentResolver resolver, Uri uri, int resultFlags) {
        int grants = grantedFlags(resultFlags);
        if (uri == null || !"content".equals(uri.getScheme()) || grants != READ_WRITE)
            throw new SecurityException("읽기와 쓰기 권한이 있는 파일을 다시 골라 주세요");
        resolver.takePersistableUriPermission(uri, grants);
        if (!persisted(resolver, uri))
            throw new SecurityException("파일의 영구권한을 받지 못했습니다. 다시 골라 주세요");
    }

    static void release(ContentResolver resolver, Uri uri) {
        for (UriPermission permission : resolver.getPersistedUriPermissions()) {
            if (!uri.equals(permission.getUri())) continue;
            int grants = (permission.isReadPermission() ? Intent.FLAG_GRANT_READ_URI_PERMISSION : 0)
                    | (permission.isWritePermission() ? Intent.FLAG_GRANT_WRITE_URI_PERMISSION : 0);
            resolver.releasePersistableUriPermission(uri, grants);
            return;
        }
    }

    private DocumentAccess() { }
}
