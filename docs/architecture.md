# 構成

入口は Traefik。
ホストで仕事を分ける。`admin.localhost` は Laravel + Inertia、`agent.localhost` は FastAPI。
会話画面は Inertia が描き、ブラウザから FastAPI の `/v1/chat` を呼ぶ。
Teams とメールも同じ Orchestrator に入る。入口だけが違う。

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
検索計画、承認で止める条件、スキルの実行は、Laravel に混ぜない。

## 質問のとき、Orchestrator は DB を直接叩かない

意図を分けて検索計画を作り、Search Service に渡す。
Search Service が全文、グラフ、決裁表、スキルを足して、根拠と欠けているものを返す。
足りなければ計画を直してもう一度探す。まだ足りなければ、足りないものを書いて止める。

```json
{
  "intent": "tacit_lookup",
  "retrieval_modes": ["keyword", "graph", "skills"],
  "required_evidence_type": "tacit"
}
```

スキルを回せと言われたときは、口伝込みの手順を実行する。
送信・発注・削除・公開は、承認待ちで止まる。

原本の更新は `/v1/ingest` が文書庫へ書き、全文とグラフを更新する。
Azure では Service Bus の ingest キューが同じ仕事をする。

課金は FastAPI が Laravel の `/api/internal/agent-access` と `/api/internal/usage` を呼ぶ。
枠が無ければ止める。

## Azure に出すもの

`infra/terraform` が立てる。

VNet、Azure OpenAI、Key Vault、Blob、AI Search、Service Bus を Private Endpoint で閉じる。
Container Apps は内部ロードバランサ。
Neo4j は VNet 内の Container Instance。
PostgreSQL は Flexible Server の VNet 統合。

公開インターネットへ出るのは、イメージを初めて引くときだけである。
`enable_nat_gateway` を後から切れば、それも止められる。

なぜ実行基盤を自前にするかは [self-host.md](self-host.md)。
立て方の注意は [../infra/terraform/README.md](../infra/terraform/README.md)。
