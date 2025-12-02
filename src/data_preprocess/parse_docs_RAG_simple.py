import os
import re
import json
from pathlib import Path


def extract_title(text: str, fallback: str):
    """取第一个 '# ' 当文档标题，没有就用文件名."""
    for line in text.splitlines():
        m = re.match(r"^#\s+(.*)", line)
        if m:
            return m.group(1).strip()
    return fallback


def split_sections(text: str, doc_title: str):
    """
    按 ## / ### 切成若干 section。
    返回: list[dict] -> {"heading": str, "content": str}
    """
    lines = text.splitlines()
    sections = []
    current_heading = doc_title
    current_lines = []

    skip_first_title = True

    for line in lines:
        # 跳过第一行 # 标题
        if skip_first_title and re.match(r"^#\s+", line):
            skip_first_title = False
            continue

        m = re.match(r"^(#{2,3})\s+(.*)", line)
        if m:
            if current_lines:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip()
                })
                current_lines = []
            current_heading = m.group(2).strip()
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_lines).strip()
        })

    return sections


def build_rag_jsonl(docs_root: str, output_file: str, prefix="fastapi"):
    docs_root = Path(docs_root)
    md_files = list(docs_root.rglob("*.md"))
    print(f"找到 {len(md_files)} 个 Markdown 文件")

    idx = 1
    with open(output_file, "w", encoding="utf-8") as out:
        for md in md_files:
            text = md.read_text(encoding="utf-8")
            title = extract_title(text, md.stem)
            sections = split_sections(text, title)

            for sec in sections:
                record = {
                    "doc_id": f"{prefix}_{idx:04d}",
                    "title": title,
                    "section": sec["heading"],
                    "content": sec["content"],
                    "source": str(md.relative_to(docs_root))
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                idx += 1

    print(f"已生成 jsonl：{output_file}")


if __name__ == "__main__":
    # 修改这里，让它指向你的 docs 根目录
    build_rag_jsonl(
        docs_root="data/raw_docs/docs/en/docs",
        output_file="data/processed/fastapi_rag_simple.jsonl"
    )

