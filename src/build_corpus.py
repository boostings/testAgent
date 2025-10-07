#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
from typing import List


def load_jsonl(path: str) -> List[dict]:
    items: List[dict] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def main():
    parser = argparse.ArgumentParser(description='Build plain text corpus from chunks.jsonl')
    parser.add_argument('--dataset', required=True, help='Path to chunks.jsonl')
    parser.add_argument('--out', required=True, help='Output text file path')
    args = parser.parse_args()

    data = load_jsonl(args.dataset)
    # Sort by (source_url, chunk_index) for stable doc order
    data.sort(key=lambda x: (x.get('source_url', ''), int(x.get('chunk_index', 0))))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        current_url = None
        for item in data:
            url = item.get('source_url', '')
            if url != current_url:
                current_url = url
                f.write(f"\n\n<|doc|> {url}\n")
            text = item.get('text', '').strip()
            if not text:
                continue
            f.write(text + "\n\n")

    print(f"Wrote corpus to: {args.out}")


if __name__ == '__main__':
    main()


