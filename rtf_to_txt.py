#!/usr/bin/env python3
"""
RTFファイルをテキストファイルに一括変換するスクリプト
Shift_JIS (cp932) / UTF-8 混在対応
2026/6/15 Claude修正
"""

import re
import sys
import argparse
from pathlib import Path


def detect_encoding(raw: bytes) -> str:
    """RTFヘッダのコードページ宣言からエンコーディングを推定する。"""
    head = raw[:512]
    if re.search(rb'\\ansicpg932', head):
        return 'cp932'
    if re.search(rb'\\ansicpg65001', head):
        return 'utf-8'
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'cp932'


def rtf_to_text(raw: bytes) -> str:
    """RTFバイナリからプレーンテキストを抽出する。"""
    encoding = detect_encoding(raw)

    # ── UTF-8 RTF: バイト列に生のUTF-8が埋め込まれているケース ──
    # latin-1 でデコードすると文字化けするので、先にUTF-8でデコードを試みる
    if encoding == 'utf-8':
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
    else:
        # Shift_JIS RTF: \'xx エスケープで非ASCII文字が表現される
        text = raw.decode('latin-1')

    # ── Step 1: 最外の {} を除去（しないと全テキストがグループとして消える）──
    text = text.strip()
    if text.startswith('{') and text.endswith('}'):
        text = text[1:-1]

    # ── Step 2: \'xx エスケープを変換（Shift_JIS用、連続するものをまとめてデコード）──
    if encoding == 'cp932':
        def decode_hex_runs(s: str, enc: str) -> str:
            def replacer(m):
                hex_vals = re.findall(r"\\'([0-9a-fA-F]{2})", m.group(0))
                hex_bytes = bytes([int(x, 16) for x in hex_vals])
                return hex_bytes.decode(enc, errors='replace')
            return re.sub(r"(?:\\'[0-9a-fA-F]{2})+", replacer, s)
        text = decode_hex_runs(text, encoding)

    # ── Step 3: 改行・タブ系制御ワードをテキストに変換 ──
    text = re.sub(r'\\par\b *',  '\n', text)
    text = re.sub(r'\\pard\b *', '',   text)
    text = re.sub(r'\\line\b *', '\n', text)
    text = re.sub(r'\\tab\b *',  '\t', text)
    text = re.sub(r'\\page\b *', '\n\n', text)
    text = re.sub(r'\\sect\b *', '\n\n', text)
    text = re.sub(r'\\cell\b *', '\t', text)
    text = re.sub(r'\\row\b *',  '\n', text)

    # ── Step 4: 内部グループを内側から除去（フォントテーブル等）──
    for _ in range(30):
        new = re.sub(r'\{[^{}]*\}', '', text)
        if new == text:
            break
        text = new

    # ── Step 5: 残り制御ワード・制御記号・波括弧を除去 ──
    text = re.sub(r'\\[a-zA-Z]+-?\d* *', '', text)
    text = re.sub(r'\\[^a-zA-Z\n]',       '', text)
    text = re.sub(r'[{}]',                 '', text)

    # ── Step 6: 整形（連続空行を最大2行に圧縮）──
    lines = [line.rstrip() for line in text.splitlines()]
    result, blank_count = [], 0
    for line in lines:
        if line == '':
            blank_count += 1
            if blank_count <= 2:
                result.append('')
        else:
            blank_count = 0
            result.append(line)

    return '\n'.join(result).strip()


def convert_folder(input_dir: str, output_dir: str | None, overwrite: bool) -> None:
    input_path = Path(input_dir)
    if not input_path.is_dir():
        print(f"[ERROR] フォルダが見つかりません: {input_dir}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(output_dir) if output_dir else input_path
    out_path.mkdir(parents=True, exist_ok=True)

    rtf_files = sorted(input_path.glob('*.rtf')) + sorted(input_path.glob('*.RTF'))
    if not rtf_files:
        print("[INFO] RTFファイルが見つかりませんでした。")
        return

    success, skipped, failed = 0, 0, 0

    for rtf_file in rtf_files:
        txt_file = out_path / (rtf_file.stem + '.txt')

        if txt_file.exists() and not overwrite:
            print(f"[SKIP] {rtf_file.name} → {txt_file.name} (--overwrite で上書き可)")
            skipped += 1
            continue

        try:
            raw = rtf_file.read_bytes()
            text = rtf_to_text(raw)
            txt_file.write_text(text, encoding='utf-8')
            print(f"[OK]   {rtf_file.name} → {txt_file.name}")
            success += 1
        except Exception as e:
            print(f"[FAIL] {rtf_file.name}: {e}", file=sys.stderr)
            failed += 1

    print(f"\n変換完了: 成功 {success} / スキップ {skipped} / 失敗 {failed}  (合計 {len(rtf_files)} ファイル)")


def main():
    parser = argparse.ArgumentParser(
        description='RTF → TXT 一括変換（Shift_JIS / UTF-8 混在対応）'
    )
    parser.add_argument('input_dir',
                        help='RTFファイルが入っているフォルダのパス')
    parser.add_argument('-o', '--output_dir', default=None,
                        help='出力先フォルダ（省略時は input_dir と同じ）')
    parser.add_argument('--overwrite', action='store_true',
                        help='既存の .txt ファイルを上書きする')
    args = parser.parse_args()

    convert_folder(args.input_dir, args.output_dir, args.overwrite)


if __name__ == '__main__':
    main()
