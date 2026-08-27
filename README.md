# Azure閉域AIエージェント

Microsoft 365 と Azure を既に使っている組織向けのテンプレートである。
Entra、Azure OpenAI、Teams、VNet は顧客が持っている。
この箱に入るのは、口伝をスキルにして回す実行基盤である。

スキルは Markdown、ハーネスは FastAPI、画面は Laravel の Inertia。
モデルは Azure OpenAI に残し、ループは Container Apps の中で回す。

## 箱を開ける

```bash
cp .env.example .env
make bootstrap
make up
```

| URL | 中身 |
| --- | --- |
| http://admin.localhost/chat | 社内AIチャット |
| http://admin.localhost/skills | スキル一覧 |
| http://admin.localhost/usage | 利用枠 |
| http://agent.localhost/docs | ハーネスの API |

初期ユーザーは `admin@example.com` / `password`。
ローカル用なので、公開環境では必ず変える。

最初のゴールは、業務を1つスキル化して回すこと。
架空の総合商社サンプルでは、出張と事業投資が動く。

Azure へ出すときは `infra/terraform`。
説明の入口は [docs/README.md](docs/README.md)。

## 構成

```
Teams / メール / ブラウザ
        │
     Traefik
        │
        ├── Laravel + Inertia     画面、ユーザー、課金
        └── FastAPI ハーネス
              ├── スキル実行
              ├── Search Service（グラフ / 全文 / 決裁）
              ├── Teams / メールの受け口
              └── Azure OpenAI
```

Microsoft に残すもの: Entra、OpenAI、VNet、Key Vault、Monitor、Teams、Exchange、AI Search。
箱に残すもの: ループ、スキル、グラフ、承認、口座。

## ディレクトリ

```
admin-overlay/         Laravel 差分（チャット、スキル、課金）
agent/                 ハーネスとサンプルスキル
agent/samples/shosha/  架空の総合商社サンプル
infra/terraform/       閉域の一式
docs/                  公開ドキュメント
```

`make bootstrap` が [laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template) を clone し、差分を載せる。

## ライセンス

MIT
