# 構成

入口は Traefik。
ホストで仕事を分ける。`admin.localhost` は Laravel + Inertia、`agent.localhost` は FastAPI。
会話画面は Inertia が描き、ブラウザから FastAPI の `/v1/chat` を呼ぶ。
Teams とメールも同じ Orchestrator に入る。入口だけが違う。

エージェントの `/v1/*` は Bearer（または `X-Agent-Token`）が無いと動かない。
`user_id` はクライアントが名乗っても使わない。トークンから Principal を開く。
未知のメール / Teams 差出人は `user_id=1` に寄せない。拒否する。

## 正本の分け方

PostgreSQL がユーザーとお金の正本。
誰がどの組織に属するか、今月あと何トークン使えるか、管理画面から見る履歴は、ここ以外に置かない。

Blob が原本の正本。
マニュアルも口伝メモも、まず文書庫に置く。検索面はコピーである。

Neo4j が関係の正本。
部門、規程、手順、口伝、スキルのつながりは、ユーザー表に正規化しない。

ナレッジの正本は、部署が rules と口伝を持つ形である。
全社は規程だけを持つ。検索はヒットしたあと、質問者の部署と機密区分で削る。
他部署の口伝は返さない。口伝はマニュアルより現場の正本として扱う。

Azure AI Search（ローカルでは全文インデックス）が文言の正本。
見出し単位で引き、グラフと構造化データと足す。権限フィルタの前に計画を書く。

FastAPI が推論と実行の正本。
検索計画、承認で止める条件、スキルの実行は、Laravel に混ぜない。
承認はファイルに残す。無い ID は 404。通した人だけ実行できる。
監査は追記の JSONL に前件ハッシュを繋ぐ。

## 質問のとき、Orchestrator は DB を直接叩かない

身元を開き、DLP を通し、意図を分けて検索計画を作り、Search Service に渡す。
Search Service が全文、グラフ、決裁表、スキルを足して、質問者が読んでよいものだけ残す。
足りなければ計画を直してもう一度探す。まだ足りなければ、足りないものを書いて止める。

```json
{
  "intent": "tacit_lookup",
  "retrieval_modes": ["keyword", "graph", "skills"],
  "required_evidence_type": "tacit",
  "filters": {"permission_scope": "user-accessible"}
}
```

スキルを回せと言われたときは、その部署のスキルだけを実行する。
出張、稟議、契約、投資、与信、貿易、コンプラがサンプルである。
送信・発注・削除・公開は、承認レコードを残して止まる。

原本の更新は `/v1/ingest` が文書庫へ書き、ingest キュー経由で全文とグラフを更新する。
起動時に文書庫を読み直し、検索面を戻す。書くときも部署と DLP を見る。
Microsoft 365 の文書は Graph から取る。トークンが無い手元では SharePoint / Teams / Outlook / OneDrive / Purview の見本を入れる。
公式ドキュメントそのもの（learn.microsoft.com）は入れない。入れるのはテナントの中の文書である。

メールと Teams は入口だけが違う。チャネル API は共有秘密が要る。
手元の返信は Mailpit。本番の送信は Graph のメールである。
受信箱は自分宛か監査役だけが見る。

手元では Azurite が Blob と Queue。Service Bus emulator を足すと、本番と同じ AMQP クライアントを踏める。
VNet と Private Endpoint はエミュレータには無い。

課金は FastAPI が Laravel の `/api/internal/agent-access` と `/api/internal/usage` を呼ぶ。
枠が無ければ止める。

本番 (`APP_ENV=production`) では OpenRouter を使わない。閉域の Azure OpenAI だけ。

## Azure に出すもの

`infra/terraform` が立てる。

VNet、Azure OpenAI、Key Vault、Blob、AI Search、Service Bus を Private Endpoint で閉じる。
Container Apps は内部ロードバランサ。
イメージは Private ACR を変数で渡す。公開レジストリのまま出さない。
診断設定を Log Analytics に流す。
Neo4j は VNet 内の Container Instance。
PostgreSQL は Flexible Server の VNet 統合。

公開インターネットへ出るのは、イメージを初めて引くときだけである。
`enable_nat_gateway` を後から切れば、それも止められる。
