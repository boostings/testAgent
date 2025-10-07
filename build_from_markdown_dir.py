#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build docs_index.jsonl and chunks.jsonl from a directory of Markdown files.

This avoids scraping and uses the same chunking logic as scrape_and_prepare.py.

Usage:
  python3 build_from_markdown_dir.py \
    --md-dir /path/to/raw_markdown \
    --out /path/to/run_root \
    [--max-chars 2000] [--overlap 200] [--verbose]
"""

import argparse
import hashlib
import json
import os
from typing import Iterable, List, Tuple


def chunk_markdown(
    text: str,
    max_chars: int = 2000,
    overlap: int = 200,
) -> List[str]:
    # Split on paragraphs first, keep headings as chunk boundaries
    paragraphs: List[str] = []
    for block in __import__('re').split(r"\n\n+", text):
        block = block.strip()
        if not block:
            continue
        paragraphs.append(block)

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush():
        nonlocal current, current_len
        if not current:
            return
        chunk = "\n\n".join(current).strip()
        if chunk:
            chunks.append(chunk)
        current = []
        current_len = 0

    for para in paragraphs:
        is_heading = para.lstrip().startswith('#')
        para_len = len(para) + (2 if current else 0)

        if is_heading and current:
            flush()

        if current_len + para_len <= max_chars:
            current.append(para)
            current_len += para_len
        else:
            if current:
                flush()
            # If a single paragraph is longer than max_chars, hard-wrap it
            if len(para) > max_chars:
                start = 0
                while start < len(para):
                    end = min(start + max_chars, len(para))
                    chunks.append(para[start:end])
                    start = max(start + max_chars - overlap, end)
            else:
                current = [para]
                current_len = len(para)

    flush()

    # Add overlap between chunks to preserve context
    if overlap > 0 and chunks:
        with_overlap: List[str] = []
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                with_overlap.append(chunk)
                continue
            prev = chunks[idx - 1]
            tail = prev[-overlap:]
            merged = (tail + "\n" + chunk).strip()
            with_overlap.append(merged)
        return with_overlap
    return chunks


def write_jsonl(path: str, records: Iterable[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _read_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _infer_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        line = line.strip()
        if line.startswith('#') and len(line) > 1:
            # Take the first heading line without leading #'s and spaces
            return line.lstrip('#').strip()
    return fallback


def build_from_md_dir(md_dir: str, out_root: str, max_chars: int, overlap: int, verbose: bool) -> Tuple[str, str]:
    os.makedirs(out_root, exist_ok=True)
    docs_index_path = os.path.join(out_root, 'docs_index.jsonl')
    chunks_path = os.path.join(out_root, 'chunks.jsonl')

    md_files: List[str] = []
    for name in sorted(os.listdir(md_dir)):
        if name.startswith('.'):
            continue
        if not name.lower().endswith('.md'):
            continue
        full = os.path.join(md_dir, name)
        if os.path.isfile(full):
            md_files.append(full)

    if verbose:
        print(f"Found {len(md_files)} markdown files in {md_dir}")

    # Build docs index records
    docs_records: List[dict] = []
    for path in md_files:
        text = _read_file(path)
        title = _infer_title(text, os.path.basename(path))
        sha256 = hashlib.sha256(text.encode('utf-8')).hexdigest()
        docs_records.append({
            'url': f'file://{path}',
            'title': title,
            'md_path': path,
            'sha256': sha256,
        })

    write_jsonl(docs_index_path, docs_records)

    if verbose:
        print(f"Wrote docs index: {docs_index_path} (records={len(docs_records)})")

    # Build chunked dataset
    dataset: List[dict] = []
    for doc in docs_records:
        text = _read_file(doc['md_path'])
        chunks = chunk_markdown(text, max_chars=max_chars, overlap=overlap)
        for i, chunk in enumerate(chunks):
            dataset.append({
                'id': hashlib.sha1((doc['md_path'] + str(i)).encode('utf-8')).hexdigest(),
                'source_url': doc['url'],
                'title': doc['title'],
                'chunk_index': i,
                'text': chunk,
                'doc_path': doc['md_path'],
            })

    write_jsonl(chunks_path, dataset)

    if verbose:
        print(f"Wrote chunked dataset: {chunks_path} (records={len(dataset)})")

    return docs_index_path, chunks_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Build dataset from a directory of Markdown files')
    p.add_argument('--md-dir', required=True, help='Directory containing .md files')
    p.add_argument('--out', required=True, help='Output run root (will contain docs_index.jsonl and chunks.jsonl)')
    p.add_argument('--max-chars', type=int, default=2000, help='Max characters per chunk')
    p.add_argument('--overlap', type=int, default=200, help='Character overlap between chunks')
    p.add_argument('--verbose', action='store_true')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    build_from_md_dir(
        md_dir=args.md_dir,
        out_root=args.out,
        max_chars=args.max_chars,
        overlap=args.overlap,
        verbose=args.verbose,
    )


if __name__ == '__main__':
    main()


