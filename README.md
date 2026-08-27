# Azure閉域AIエージェント

Microsoft 店向けのテンプレート。
口伝をスキルにして回す実行基盤に、身元・部署 ACL・承認の永続化・監査を載せた。

スキルは Markdown、ハーネスは FastAPI、画面は Laravel の Inertia。
モデルは Azure OpenAI。手元確認だけ OpenRouter を許す。本番 (`APP_ENV=production`) では閉域外へ出さない。

```bash
cp .env.example .env
make bootstrap
make up
```

ブラウザは http://agent.localhost/app 。
身元トークンを入れてから動かす。

| トークン | 部署 | 見えるもの |
| --- | --- | --- |
| `local-admin` | 情報システム部 | 全部。承認と監査 |
| `local-sales` | 営業部 | 全社規程と営業の口伝。与信室は見えない |
| `local-hr` | 人事部 | 全社規程と出張マニュアル。契約管理部の保険口伝は見えない |
| `local-credit` | 与信室 | 与信の口伝 |
| `local-legal` | 法務部 | 法務。承認可 |
| `local-compliance` | コンプライアンス室 | 該非。承認と監査 |

未知の差出人は管理者に寄せない。受け付けない。

| URL | 中身 |
| --- | --- |
| http://agent.localhost/app | チャット / ナレッジ / メール / 承認 / 監査 |
| http://admin.localhost/chat | Laravel の社内AIチャット |
| http://agent.localhost/docs | API |
| http://127.0.0.1:8025 | Mailpit |

`Authorization: Bearer local-admin` が無い `/v1/*` は 401。
送信・発注・削除・公開は承認レコードを残す。存在しない ID は通らない。
監査はハッシュ連鎖。改ざんすると `/v1/audit` が壊れていると言う。
契約書本文・与信点・社外秘以上は DLP で止める。

```
Teams / メール / ブラウザ
        │  Bearer + 部署 ACL
     Traefik
        ├── Laravel + Inertia     画面、ユーザー、課金
        └── FastAPI
              ├── 身元 / 承認 / 監査
              ├── スキル
              ├── Search Service（権限で削る）
              └── Azure OpenAI（本番） / OpenRouter（手元）
```

手元の Azure は公式エミュレータ。閉域（VNet / Private Endpoint）はエミュレータでは見ない。
ナレッジの正本は文書庫。部署の口伝と全社規程を混ぜない。
Graph のトークンが無いときは `samples/office/microsoft` を取り込む。

`make bootstrap` が [laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template) を clone し、`admin-overlay/` を載せる。
Azure は `infra/terraform`。構成は `docs/architecture.md`。

MIT
