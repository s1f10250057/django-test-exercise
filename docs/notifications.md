# 期限通知の本番運用

`django-test-notify-due-tasks` は毎時0分（UTC）に実行され、24時間以内が期限の未完了タスクを各所有者の登録メールアドレスへ通知します。メールアドレス未設定の所有者はスキップされ、タスクは未通知のまま残ります。

## Render設定

Blueprintを同期した後、cron jobのEnvironmentへ次の値を設定します。

- `EMAIL_HOST`: SMTPサーバー
- `EMAIL_HOST_USER`: SMTPユーザー
- `EMAIL_HOST_PASSWORD`: SMTPパスワードまたはAPIキー
- `DEFAULT_FROM_EMAIL`: SMTPプロバイダで送信を許可されたFromアドレス

既存Blueprintへ後から追加した `sync: false` の値は自動設定されないため、Render Dashboardで入力します。`EMAIL_PORT=587` と `EMAIL_USE_TLS=true` はBlueprintに定義済みです。

## 確認

1. 通知対象ユーザーのメールアドレスをDjango adminで設定します。
2. Render Dashboardでcron jobを開き、`Trigger Run` を実行します。
3. ログの `Sent N notification(s).` と受信メールを確認します。
4. 送信失敗時はSMTP設定を修正し、再度手動実行します。送信済みになっていないタスクは次回実行でも対象になります。
