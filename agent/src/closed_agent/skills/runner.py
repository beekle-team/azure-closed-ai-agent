from closed_agent.retrieve.structured import StructuredStore
from closed_agent.settings import settings
from closed_agent.skills.catalog import Skill


def run_skill(skill: Skill, inputs: dict[str, str] | None = None) -> str:
    payload = inputs or {}
    if skill.id == "trip-precheck":
        return _trip_precheck(payload)
    if skill.id == "ringi-route":
        return _ringi_route(payload)
    if skill.id == "contract-review":
        return _contract_review(payload)
    if skill.id == "investment-check":
        return _investment_check(payload)
    if skill.id == "credit-check":
        return _credit_check(payload)
    if skill.id == "trade-docs":
        return _trade_docs(payload)
    if skill.id == "compliance-check":
        return _compliance_check(payload)
    return skill.body


def _trip_precheck(inputs: dict[str, str]) -> str:
    destination = inputs.get("destination") or "海外"
    days = int(inputs.get("days") or "5")
    lines = [
        f"行き先は{destination}、期間は{days}日として事前チェックした。",
        "申請画面には出ないが、海外出張の保険は契約管理部が裏で見る。先に一声かける。",
    ]
    if "国内" not in destination:
        lines.append("海外旅行保険の加入確認を契約管理部の受付に残す。")
    if days >= 7:
        lines.append("7日以上なので、人事部にも日程を共有する。")
    lines.append("ここまでが口伝だった確認で、今はスキルとして回せる。")
    return "\n".join(lines)


def _ringi_route(inputs: dict[str, str]) -> str:
    amount = int(inputs.get("amount") or "80000000")
    first_time = inputs.get("first_time", "yes") != "no"
    store = StructuredStore(settings.sample_root / "structured.json")
    route_name = "大型稟議" if amount >= 50_000_000 else "通常稟議"
    route = next((item for item in store.data.get("routes", []) if item["name"] == route_name), None)
    steps = route["steps"] if route else "担当 → 部長 → 本部長"
    lines = [
        f"金額{amount:,}円の稟議ルート。",
        f"基本経路は {steps}。",
    ]
    if first_time:
        lines.append("初めての取引先なので、金額より先に与信を見る。与信室を経路に足す。")
    if amount >= 50_000_000:
        lines.append("大型は本部長決裁の前に財務へ一声かける。規程には無い。")
    return "\n".join(lines)


def _contract_review(inputs: dict[str, str]) -> str:
    title = inputs.get("title") or "取引基本契約"
    counterparty = inputs.get("counterparty") or "新規取引先"
    return (
        f"法務部 契約審査 御中\n"
        f"件名: {title} のレビュー依頼（{counterparty}）\n"
        "原本は文書庫に置きました。秘密区分は社外秘です。\n"
        "社内AIチャットへ本文は載せないでください。情報取扱規程の別表に従います。\n"
        "送信は承認後に実行します。"
    )


def _investment_check(inputs: dict[str, str]) -> str:
    target = inputs.get("target") or "対象企業"
    return (
        f"{target}の事業投資申請を、失敗の教訓に照らした。\n"
        "目的: 何を良くしたい申請か。数字の前に一文で書けなければ通さない。\n"
        "撤退: 誰が、どの数字で、いつ判定するかが空欄なら通さない。\n"
        "与信: 初回かどうかは、金額より先に見る。口伝の与信ルートと同じ。\n"
        "要約と翻訳は汎用チャットで足りる。申請の漏れは、このスキルが見る。"
    )


def _credit_check(inputs: dict[str, str]) -> str:
    counterparty = inputs.get("counterparty") or "新規取引先"
    first_time = inputs.get("first_time", "yes") != "no"
    amount = int(inputs.get("amount") or "0")
    store = StructuredStore(settings.sample_root / "structured.json")
    limit = next(
        (int(item["limit"]) for item in store.data.get("credit_limits", []) if item["name"] == counterparty),
        0,
    )
    lines = [
        f"{counterparty}の与信。金額より先に、初めてかどうかを見た。",
    ]
    if first_time or limit == 0:
        lines.append("初回なので与信室を通す。既存の枠は使わない。")
    elif amount > limit:
        lines.append(f"既存先だが、枠{limit:,}円を超える。財務部を乗せる。")
    else:
        lines.append(f"既存先で、枠{limit:,}円の内。担当と部長で足りる。")
    lines.append("画面は金額欄が先に来る。初回を見落とすな、が口伝である。")
    return "\n".join(lines)


def _trade_docs(inputs: dict[str, str]) -> str:
    invoice_ccy = inputs.get("invoice_currency") or "USD"
    bl_ccy = inputs.get("bl_currency") or invoice_ccy
    incoterms = inputs.get("incoterms") or "FOB"
    insured = inputs.get("insured", "no") == "yes"
    lines = [
        "数量を足す前に、通貨と建値を突合した。",
        f"インボイスは{invoice_ccy}、船荷証券は{bl_ccy}、建値は{incoterms}。",
    ]
    if invoice_ccy != bl_ccy:
        lines.append("通貨が食い違っている。船積みを止めて、契約管理部へ戻す。")
    if incoterms == "FOB" and insured:
        lines.append("FOBなのに保険料が乗っている。運賃保険料は買い手側である。")
    if invoice_ccy == bl_ccy and not (incoterms == "FOB" and insured):
        lines.append("通貨と建値は揃っている。次に信用状の船積期限と船荷証券の日付を見る。")
    return "\n".join(lines)


def _compliance_check(inputs: dict[str, str]) -> str:
    destination = inputs.get("destination") or "出荷先"
    reexport = inputs.get("reexport", "no") == "yes"
    gift = inputs.get("gift", "no") == "yes"
    lines = [
        f"{destination}向けの事前確認。国名だけでなく、船積み地と銀行も見る。",
    ]
    if reexport:
        lines.append("再輸出がある。該非判定書はそのまま渡さない。貿易管理部へ先に聞く。")
    if gift:
        lines.append("贈答がある。申請画面の閾値より前に、コンプライアンス室へ一声かける。")
    if not reexport and not gift:
        lines.append("再輸出も贈答も無い。制裁対象に該当しないことだけ、室へ確認する。")
    lines.append("送信は承認後に実行します。")
    return "\n".join(lines)
