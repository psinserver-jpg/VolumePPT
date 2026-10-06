package com.volumeppt.remote;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.Vibrator;
import android.view.KeyEvent;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.TextView;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 볼륨 ▲ → PC 에 /next, 볼륨 ▼ → PC 에 /prev 를 보낸다.
 * 앱이 화면에 떠 있는 동안 볼륨키는 휴대폰 음량을 바꾸지 않고 리모컨으로만 쓰인다.
 */
public class MainActivity extends Activity {

    private static final int DEFAULT_PORT = 8765;

    private final ExecutorService net = Executors.newSingleThreadExecutor();
    private SharedPreferences prefs;
    private EditText hostInput;
    private EditText tokenInput;
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        // 발표 중 화면이 꺼지면 볼륨키를 받을 수 없으므로 화면을 켜 둔다
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        prefs = getSharedPreferences("volumeppt", MODE_PRIVATE);
        hostInput = findViewById(R.id.host);
        tokenInput = findViewById(R.id.token);
        status = findViewById(R.id.status);

        hostInput.setText(prefs.getString("host", ""));
        tokenInput.setText(prefs.getString("token", ""));

        findViewById(R.id.connect).setOnClickListener(v -> {
            saveSettings();
            hideKeyboard();
            send("ping");
        });
        findViewById(R.id.next).setOnClickListener(v -> send("next"));
        findViewById(R.id.prev).setOnClickListener(v -> send("prev"));

        handleConnectLink(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleConnectLink(intent);
    }

    /** volumeppt://connect?host=192.168.0.10:8765&token=1234 로 열리면 주소와 PIN 을 자동 입력 */
    private void handleConnectLink(Intent intent) {
        Uri data = intent == null ? null : intent.getData();
        if (data == null || !"volumeppt".equals(data.getScheme())) return;
        String host = data.getQueryParameter("host");
        String token = data.getQueryParameter("token");
        if (host == null || host.isEmpty()) return;
        hostInput.setText(host);
        tokenInput.setText(token == null ? "" : token);
        saveSettings();
        send("ping");
    }

    @Override
    protected void onPause() {
        super.onPause();
        saveSettings();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        net.shutdownNow();
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        String action = actionFor(event.getKeyCode());
        if (action == null) {
            return super.dispatchKeyEvent(event);
        }
        // 누를 때 한 번만 전송 (길게 눌러 생기는 반복 입력은 무시)
        if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
            send(action);
        }
        // DOWN/UP 모두 소비해야 시스템 음량 UI 가 뜨지 않는다
        return true;
    }

    private static String actionFor(int keyCode) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_VOLUME_UP:
            case KeyEvent.KEYCODE_PAGE_DOWN:      // 블루투스 프레젠터
            case KeyEvent.KEYCODE_MEDIA_NEXT:
                return "next";
            case KeyEvent.KEYCODE_VOLUME_DOWN:
            case KeyEvent.KEYCODE_PAGE_UP:
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                return "prev";
            default:
                return null;
        }
    }

    private void send(final String action) {
        String host = normalizeHost(hostInput.getText().toString());
        if (host.isEmpty()) {
            status.setText("먼저 PC 주소를 입력하세요");
            return;
        }
        String token = tokenInput.getText().toString().trim();
        if (!action.equals("ping")) {
            vibrate();
        }
        final String target;
        try {
            target = "http://" + host + "/" + action
                    + (token.isEmpty() ? "" : "?token=" + URLEncoder.encode(token, "UTF-8"));
        } catch (IOException e) {
            return;
        }

        net.execute(() -> {
            String message;
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(target).openConnection();
                conn.setConnectTimeout(1500);
                conn.setReadTimeout(1500);
                int code = conn.getResponseCode();
                if (code == 200) {
                    message = action.equals("ping") ? "✅ 연결됨: " + host
                            : action.equals("next") ? "다음 ▶" : "◀ 이전";
                } else if (code == 403) {
                    message = "❌ PIN 이 맞지 않습니다\nPC 화면의 QR 을 다시 찍어 주세요";
                } else {
                    message = "❌ 오류 " + code;
                }
            } catch (IOException e) {
                message = "❌ PC에 연결할 수 없습니다\n같은 Wi-Fi 인지, 서버가 실행 중인지 확인하세요";
            } finally {
                if (conn != null) conn.disconnect();
            }
            final String text = message;
            runOnUiThread(() -> status.setText(text));
        });
    }

    /** "192.168.0.10" → "192.168.0.10:8765", 앞의 http:// 와 끝의 / 는 제거 */
    private static String normalizeHost(String raw) {
        String h = raw.trim().replaceFirst("^https?://", "");
        while (h.endsWith("/")) h = h.substring(0, h.length() - 1);
        if (h.isEmpty()) return h;
        if (!h.contains(":")) h = h + ":" + DEFAULT_PORT;
        return h;
    }

    private void saveSettings() {
        prefs.edit()
                .putString("host", hostInput.getText().toString().trim())
                .putString("token", tokenInput.getText().toString().trim())
                .apply();
    }

    private void hideKeyboard() {
        InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(hostInput.getWindowToken(), 0);
        hostInput.clearFocus();
        tokenInput.clearFocus();
    }

    @SuppressWarnings("deprecation")
    private void vibrate() {
        Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        if (v != null && v.hasVibrator()) v.vibrate(30);
    }
}
