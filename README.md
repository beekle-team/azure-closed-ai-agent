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
| http://admin.localhost/chat | 社内AIチャット |
| http://admin.localhost/skills | スキル |
| http://admin.localhost/usage | 利用枠 |
| http://agent.localhost/docs | API |

初期ユーザーは `admin@example.com` / `password`。本番では変える。
まずはチャット。スキルを回すと、ブラウザから出張・稟議・契約・投資の工程が動く。

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

`make bootstrap` が [laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template) を clone し、`admin-overlay/` を載せる。
Azure は `infra/terraform`。構成は `docs/architecture.md`。

MIT
