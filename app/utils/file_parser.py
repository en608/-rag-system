"""文件解析：支持纯文本与基础 PDF。"""

from io import BytesIO

from pypdf import PdfReader


def parse_upload_file(filename: str, content: bytes) -> tuple[str, str]:
    """
    根据文件扩展名解析上传内容，返回 (source_type, 纯文本)。

    :raises ValueError: 不支持的文件类型或解析失败
    """
    lower_name = filename.lower()

    if lower_name.endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("gbk", errors="ignore")
        return "txt", text.strip()

    if lower_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
        full_text = "\n".join(pages).strip()
        if not full_text:
            raise ValueError("PDF 未能提取到有效文本内容")
        return "pdf", full_text

    raise ValueError("仅支持 .txt 与 .pdf 格式文件")
