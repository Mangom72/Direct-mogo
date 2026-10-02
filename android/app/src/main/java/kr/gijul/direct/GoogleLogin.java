package kr.gijul.direct;

import android.content.MutableContextWrapper;
import android.os.CancellationSignal;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.ClearCredentialStateRequest;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.ClearCredentialException;
import androidx.credentials.exceptions.GetCredentialException;
import androidx.credentials.exceptions.GetCredentialCancellationException;
import androidx.credentials.exceptions.NoCredentialException;
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/** System Google sign-in UI; Firebase verifies the ID token before granting database access. */
final class GoogleLogin {
    private final MainActivity activity;
    private final CredentialManager manager;
    private final AtomicBoolean busy = new AtomicBoolean();
    private CancellationSignal cancellation;
    GoogleLogin(MainActivity activity) { this.activity = activity; manager = CredentialManager.create(activity); }
    private String activeId;
    void start(String clientId, String requestId) {
        if (requestId == null || !requestId.matches("[A-Za-z0-9-]{36}")) return;
        if (clientId == null || !clientId.matches("[A-Za-z0-9_-]{10,200}\\.apps\\.googleusercontent\\.com")) {
            reply(requestId, false, "로그인 연결 정보가 올바르지 않습니다"); return;
        }
        if (!busy.compareAndSet(false, true)) { reply(requestId, false, "로그인이 진행 중입니다"); return; }
        activeId = requestId;
        cancellation = new CancellationSignal();
        try {
            GetCredentialRequest request = new GetCredentialRequest.Builder()
                    .addCredentialOption(new GetSignInWithGoogleOption.Builder(clientId).build()).build();
            manager.getCredentialAsync(new MutableContextWrapper(activity), request, cancellation,
                    androidx.core.content.ContextCompat.getMainExecutor(activity), new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                @Override public void onResult(GetCredentialResponse response) {
                    try {
                        if (!(response.getCredential() instanceof CustomCredential)) throw new IllegalArgumentException();
                        CustomCredential credential = (CustomCredential) response.getCredential();
                        if (!GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(credential.getType())) throw new IllegalArgumentException();
                        result(requestId, true, GoogleIdTokenCredential.createFrom(credential.getData()).getIdToken());
                    } catch (Exception e) { result(requestId, false, "로그인 응답을 확인하지 못했습니다"); }
                }
                @Override public void onError(GetCredentialException e) {
                    String message = e instanceof GetCredentialCancellationException ? "로그인을 취소했습니다"
                            : e instanceof NoCredentialException ? "Google 계정을 기기에 추가한 뒤 다시 로그인해 주세요"
                            : "로그인을 완료하지 못했습니다. 계정과 인터넷 연결을 확인해 주세요";
                    result(requestId, false, message);
                }
            });
        } catch (Exception e) { result(requestId, false, "로그인을 시작하지 못했습니다"); }
    }
    private void result(String requestId, boolean ok, String value) {
        if (!requestId.equals(activeId)) return;
        activeId = null;
        busy.set(false);
        reply(requestId, ok, value);
    }
    private void reply(String requestId, boolean ok, String value) {
        activity.eval("window.gijulGoogleSignIn&&window.gijulGoogleSignIn(" + JSONObject.quote(requestId) + "," + ok + "," + JSONObject.quote(value) + ")");
    }
    void clear() {
        manager.clearCredentialStateAsync(new ClearCredentialStateRequest(), null,
                androidx.core.content.ContextCompat.getMainExecutor(activity), new CredentialManagerCallback<Void, ClearCredentialException>() {
            @Override public void onResult(Void result) { }
            @Override public void onError(ClearCredentialException e) { }
        });
    }
    void cancel(String requestId) { if (requestId != null && requestId.equals(activeId)) cancel(); }
    void cancel() {
        activeId = null; busy.set(false);
        if (cancellation != null) cancellation.cancel();
    }
}
