# 構成

入口は Traefik。
ホストで仕事を分ける。`admin.localhost` は Laravel + Inertia、`agent.localhost` は FastAPI。
会話画面は Inertia が描き、ブラウザから FastAPI の `/v1/chat` を呼ぶ。

## 正本の分け方

PostgreSQL がユーザーとお金の正本。
誰がどの組織に属するか、今月あと何トークン使えるか、管理画面から見る履歴は、ここ以外に置かない。

Blob が原本の正本。
マニュアルも口伝メモも、まず文書庫に置く。検索面はコピーである。

Neo4j が関係の正本。
部門、規程、手順、口伝、スキルのつながりは、ユーザー表に正規化しない。

Azure AI Search（ローカルでは全文インデックス）が文言の正本。
見出し単位で引き、グラフと構造化データと足す。

FastAPI が推論と実行の正本。
検索計画、承認で止める条件、スキルの実行は、Laravel に渗ませない。

管理画面と課金を Laravel に寄せ、ドメイン処理を別プロセスに出す線は、業務システムと同じである。

## リクエストの流れ

1. 利用者が社内AIチャットに質問する
2. Orchestrator が検索計画を立てる。関係、全文、決裁表、スキルのどれを見るか
3. Search Service（Retrieval Facade）が経路を引き、順位を足す
4. FastAPI が Laravel の `/api/internal/agent-access` を呼び、組織と残枠を見る
5. 枠が無ければ止める
6. スキルを回せと言われたときは、口伝込みの手順を実行する。送信は承認待ち
7. それ以外は Azure OpenAI に根拠を渡して答える
8. 使ったトークンを Laravel の `/api/internal/usage` に書く

原本を足すときは `/v1/ingest` が文書庫へ書き、全文とグラフを更新する。
Azure では Service Bus の ingest キューが同じ仕事をする。

## Azure 閉域

`infra/terraform` は次を立てる。

- VNet と NSG
- Azure OpenAI の Private Endpoint
- Key Vault の Private Endpoint
- Blob Storage の Private Endpoint
- Azure AI Search の Private Endpoint
- Service Bus（Premium）の Private Endpoint
- Container Apps Environment（内部 LB）
- FastAPI 用 Container App
- Laravel 用 Container App
- Neo4j 用 Container Instance（VNet 内、公開IPなし）
- PostgreSQL Flexible Server（VNet 統合）
- Log Analytics

公開インターネットへ出るのは、イメージを初めて引くときだけである。
`enable_nat_gateway` を後から切れば、それも止められる。
