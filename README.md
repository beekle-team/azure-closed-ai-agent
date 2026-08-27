# Azure閉域AIエージェント

Microsoft 店向けのテンプレート。
Entra、Azure OpenAI、Teams、VNet は既にある前提で、口伝をスキルにして回す実行基盤だけを箱に入れた。

スキルは Markdown、ハーネスは FastAPI、画面は Laravel の Inertia。
モデルは Azure OpenAI。ループは Container Apps。
Hosted Agent はイメージ置き場をプライベートにできないので、既定にしない。

```bash
cp .env.example .env
make bootstrap
make up
```

| URL | 中身 |
| --- | --- |
| http://agent.localhost/app | チャット / ナレッジ / メール |
| http://admin.localhost/chat | Laravel の社内AIチャット |
| http://admin.localhost/skills | スキル |
| http://admin.localhost/usage | 利用枠 |
| http://agent.localhost/docs | API |
| http://127.0.0.1:8025 | Mailpit |

初期ユーザーは `admin@example.com` / `password`。本番では変える。
まずはチャット。口伝を引けるだけでも使える。
ナレッジは部署が rules と口伝を持つ。全社規程は組織側。部署をまたいで混ぜない。
スキルを回すと、ブラウザから書類チェックが動く。
出張、稟議、契約、投資、与信、貿易、コンプラ。大手の現場でもそのまま差し替えられる工程を入れた。

```
Teams / メール / ブラウザ
        │
     Traefik
        ├── Laravel + Inertia     画面、ユーザー、課金
        └── FastAPI
              ├── スキル
              ├── Search Service
              └── Azure OpenAI
```

手元の Azure は公式エミュレータ。`make up` で Azurite（Blob / Queue）。Service Bus は `make up-emulators`。
閉域（VNet / Private Endpoint）はエミュレータでは見ない。Jumpbox から見る。
推論は Azure OpenAI が空ならモック。`OPENROUTER_API_KEY` を置くと OpenRouter で口伝の答え方を踏める。
ナレッジの正本は文書庫。社内の口伝に加え、SharePoint / Teams / Outlook / OneDrive / Purview の形の文書を入れる。
Graph のトークンが無いときは `samples/office/microsoft` を取り込む。本物のテナント文書は `GRAPH_ACCESS_TOKEN` が要る。
メールは Graph 通知を `/v1/channels/mail` で受ける。手元では Mailpit に返信を出す。

`make bootstrap` が [laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template) を clone し、`admin-overlay/` を載せる。
Azure は `infra/terraform`。構成は `docs/architecture.md`。

MIT
