# admin/

[beekle-team/laravel-react-docker-template](https://github.com/beekle-team/laravel-react-docker-template) を `scripts/bootstrap-admin.sh` で clone し、`admin-overlay/` を上に載せる。

このディレクトリで足したものだけが、閉域エージェント向けの差分である。

- 組織、プラン、利用イベントの Eloquent
- FastAPI が呼ぶ内部API（認証確認と利用枠の消化）
- 管理画面の利用状況ページ
- 社内AIチャット（Inertia）。ブラウザから FastAPI の `/v1/chat` を呼ぶ

書き方は元テンプレのままにする。
Service クラスは置かない。永続化は `App\Models\Eloquent`、外部接続は `App\Models\Gateway`、HTTP 検証は Form Request。
