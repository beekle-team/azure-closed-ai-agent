import io
import zipfile

import httpx

from closed_agent.knowledge.microsoft import decode_content, pull_graph_items


def _docx(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f"<w:document><w:body><w:p><w:t>{text}</w:t></w:p></w:body></w:document>",
        )
    return buffer.getvalue()


def test_decode_txt_and_docx() -> None:
    assert "保険" in decode_content("note.txt", "出張の保険".encode())
    assert "権限漏れ" in decode_content("規程.docx", _docx("権限漏れ"))
    assert "バイナリ" in decode_content("scan.pdf", b"%PDF-1.4")


def test_pull_graph_reads_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/me/drive/root/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "file-1",
                            "name": "出張メモ.md",
                            "webUrl": "https://contoso.sharepoint.com/memo.md",
                            "parentReference": {"driveId": "drive-1"},
                        },
                        {"id": "folder-1", "name": "archive", "folder": {}},
                    ]
                },
            )
        if path.endswith("/sites"):
            return httpx.Response(200, json={"value": [{"id": "site-1"}]})
        if path.endswith("/sites/site-1/drive/root/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "sp-1",
                            "name": "情報取扱.docx",
                            "webUrl": "https://contoso.sharepoint.com/policy.docx",
                            "parentReference": {"driveId": "drive-sp"},
                        }
                    ]
                },
            )
        if path.endswith("/items/file-1/content"):
            return httpx.Response(200, content="OneDrive の本文。保険は契約管理部。".encode())
        if path.endswith("/items/sp-1/content"):
            return httpx.Response(200, content=_docx("SharePoint の本文。リンクを知っている全員は使わない。"))
        return httpx.Response(404, text=path)

    items = pull_graph_items("token", client=httpx.Client(transport=httpx.MockTransport(handler)))
    titles = {item["title"] for item in items}
    assert "出張メモ.md" in titles
    assert "情報取扱.docx" in titles
    assert "archive" not in titles
    onedrive = next(item for item in items if item["title"] == "出張メモ.md")
    assert "契約管理部" in onedrive["body"]
    assert onedrive["source_system"] == "onedrive"
    sharepoint = next(item for item in items if item["title"] == "情報取扱.docx")
    assert "リンクを知っている全員" in sharepoint["body"]
    assert sharepoint["source_system"] == "sharepoint"
