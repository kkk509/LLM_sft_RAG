import os
import re
import json
from pathlib import Path

# 可调参数：chunk 长度
MAX_CHARS = 2000
MIN_CHARS = 300


def extract_title(text: str, fallback: str) -> str:
    """取第一个 '# ' 当文档标题，没有就用文件名."""
    for line in text.splitlines():
        m = re.match(r"^#\s+(.*)", line.strip())
        if m:
            return m.group(1).strip()
    return fallback


def split_to_sections(text: str, doc_title: str):
    """
    按 ## / ### 切成 section.
    返回: list[dict] -> {"heading": str, "content": str}
    """
    lines = text.splitlines()
    sections = []

    current_heading = doc_title  # 开头没有小标题时就算 Overview
    current_lines = []

    # 跳过首行大标题 '# ...'
    started = False

    for line in lines:
        if not started:
            if re.match(r"^#\s+", line):
                started = True
            continue  # 丢掉大标题本行

        heading_match = re.match(r"^(#{2,3})\s+(.*)", line)
        if heading_match:
            # 收尾上一个 section
            if current_lines:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip()
                })
                current_lines = []

            current_heading = heading_match.group(2).strip()
        else:
            current_lines.append(line)

    # 最后一节
    if current_lines:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_lines).strip()
        })

    # 如果一个 ## / ### 都没有，就整个文件当一个 section
    if not sections:
        sections.append({"heading": doc_title, "content": text})

    return sections


def chunk_section_text(text: str, max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS):
    """
    按长度切 chunk，尽量不拆代码块 ```...```
    返回: list[str]
    """
    lines = text.splitlines(keepends=True)
    chunks = []
    buf = []
    cur_len = 0
    in_code = False

    for line in lines:
        # 判断是否进入 / 离开代码块
        if line.strip().startswith("```"):
            in_code = not in_code

        # 如果超长，并且不在代码块内部，可以切一块
        if cur_len + len(line) > max_chars and not in_code and cur_len >= min_chars:
            chunks.append("".join(buf).strip())
            buf = []
            cur_len = 0

        buf.append(line)
        cur_len += len(line)

    if buf:
        chunk = "".join(buf).strip()
        if chunk:
            chunks.append(chunk)

    # 如果只有一个 chunk 而且太短，也照样返回（避免丢内容）
    return chunks


def process_fastapi_docs_to_jsonl(
    docs_root: str,
    output_file: str,
    base_url: str = "https://fastapi.tiangolo.com",
    doc_id_prefix: str = "fastapi",
):
    """
    docs_root: FastAPI docs 根目录，例如 'data/raw_docs/docs/en/docs'
    output_file: 输出 jsonl 路径
    """
    docs_root_path = Path(docs_root)
    print("当前工作目录:", os.getcwd())
    print("docs_root 传入:", docs_root)
    print("docs_root 绝对路径:", docs_root_path.resolve())
    print("exists:", docs_root_path.exists(), "is_dir:", docs_root_path.is_dir())

    if not docs_root_path.exists():
        raise ValueError(f"docs_root 不存在: {docs_root}")

    md_files = list(docs_root_path.rglob("*.md"))
    print("找到的 md 文件数量:", len(md_files))
    for p in md_files[:5]:
        print("示例 md 文件:", p)

    idx = 1
    with open(output_file, "w", encoding="utf-8") as out_f:
        for md_path in docs_root_path.rglob("*.md"):
            text = md_path.read_text(encoding="utf-8")

            # 文档标题
            title = extract_title(text, md_path.stem)

            # 相对路径，用作 source
            rel_path = md_path.relative_to(docs_root_path)

            # 构造 URL 粗略规则：用 docs_root 之后的路径当 slug
            parts = md_path.relative_to(docs_root_path).with_suffix("").parts
            slug = "/".join(parts)
            url = f"{base_url}/{slug}/"

            # 按 section 切
            sections = split_to_sections(text, title)

            for sec in sections:
                sec_heading = sec["heading"]
                sec_text = sec["content"]

                # 再按长度切 chunk
                chunks = chunk_section_text(sec_text)

                for chunk in chunks:
                    doc_id = f"{doc_id_prefix}_{idx:04d}"
                    record = {
                        "doc_id": doc_id,
                        "title": title,
                        "section": sec_heading,
                        "content": chunk,
                        "source": str(rel_path).replace("\\", "/"),
                        "url": url,
                        "tags": [doc_id_prefix] + list(parts),
                    }
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    idx += 1

    print(f"✅ 已生成 RAG jsonl: {output_file}")


if __name__ == "__main__":
    # 示例：把 FastAPI 英文文档目录导出为 jsonl
    process_fastapi_docs_to_jsonl(
        docs_root="data/raw_docs/docs/en/docs",
        output_file="data/processed/fastapi_rag_complex.jsonl",
    )
