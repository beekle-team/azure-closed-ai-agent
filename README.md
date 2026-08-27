# Azure閉域AIエージェント

Microsoft 365 と Entra と Azure OpenAI はそのまま使う。
エージェントのループ、業務の関係、承認とログは FastAPI とグラフDBで持つ。
ユーザー、組織、課金、管理画面は Laravel と PostgreSQL に置く。

入口は Traefik、画面は [laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template) の Inertia、推論は FastAPI、関係は Neo4j。
サンプルの中身は、総合商社の社内AIチャットである。マニュアルに無い口伝をスキルにして回す。

Copilot Studio や Azure AI Foundry のマネージドエージェントは、SharePoint を検索して答える仕事には向く。
規程と組織と案件の関係をたどる、実行の前に人の承認を挟む、トークン課金を自前の口座に載せる、といった仕事は、ループを自前で持った方が後から変えられる。

## 誰向けか

Microsoft 環境の情シス、またはその顧客に閉域のAIエージェントを配りたい開発会社。
「Copilot を入れたが、業務の実行と課金まで届かない」が起点になる。

## 構成

```
ブラウザ / Teams
        │
     Traefik
        │
        ├── admin.localhost  → Laravel + Inertia
        │                      社内AIチャット、利用状況、ユーザー、課金
        │                      会話画面は FastAPI の /v1 を呼ぶ
        │
        └── agent.localhost  → FastAPI
                               Orchestrator が検索計画を立てる
                                 │
                                 ├── Search Service
                                 │     グラフ / 全文 / 決裁・与信
                                 ├── Skills（口伝を手順化）
                                 ├── Blob（原本）
                                 └── Azure OpenAI
```

原本は Blob、関係はグラフ、文言は全文検索、口座は PostgreSQL。
FastAPI はユーザー表を持たない。利用のたびに Laravel の内部APIへ問い合わせる。

## ローカルで動かす

```bash
cp .env.example .env
make bootstrap
make up
```

| URL | 中身 |
| --- | --- |
| http://admin.localhost/chat | 社内AIチャット (Inertia) |
| http://admin.localhost/usage | 利用状況 |
| http://agent.localhost/docs | エージェント API |
| http://admin.localhost:8025 | Mailpit |

初期ユーザーは `admin@example.com` / `password`。
聞き方の例は `docs/sample-shosha.md`。

Azure へ出すときは `infra/terraform` を使う。
VNet、Private Endpoint、Azure OpenAI、AI Search、Blob、Service Bus、Key Vault、Container Apps、Neo4j 用 ACI までを一式で立てる。

## Copilot で足りる仕事、このテンプレが要る仕事

社内の Word と Excel を検索して「あの資料どこ」と聞くだけなら、Microsoft 365 Copilot の方が早い。

このテンプレが要るのは、次のどれかが業務要件になったときである。

- 関係をたどる。「この規程を変えると、どの手順とどのシステムが影響するか」
- 口伝を残す。画面に無い確認を、スキルとして量産する
- 実行する。照会のあと依頼文まで進め、送信の直前で止める
- 閉域にする。プロンプトもログも、公開インターネットへ出さない
- 課金する。組織ごとの利用枠を、自前の管理画面で見る

Entra、Azure OpenAI、VNet、Key Vault、Monitor はマネージドのまま使う。
手放すと後で困るのは、エージェントの頭（ループ、グラフ、承認、課金）だけである。

## ディレクトリ

```
admin/                 laravel-react-docker-template を土台にした管理画面
agent/                 FastAPI エージェント（API）
agent/samples/shosha/  総合商社サンプル（原本・口伝・スキル）
infra/terraform/       Azure 閉域の IaC
docker/traefik/        入口
docs/                  構成の補足
```

`make bootstrap` が `laravel-react-docker-template` を `admin/` に clone し、課金と内部APIの差分を載せる。
`admin/` の書き方は元テンプレのルールに従う。Service クラスは置かない。

## ライセンス

MIT
