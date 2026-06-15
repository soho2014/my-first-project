#!/usr/bin/env python3
"""
RTFファイルをテキストファイルに一括変換するスクリプト
Shift_JIS / UTF-8 混在に対応
2026/6/15 Claudeが作成
"""

import re
import os
import sys
import glob
import argparse
from pathlib import Path


# ── RTFデコード用ユーティリティ ────────────────────────────────────────

def detect_encoding(raw: bytes) -> str:
    """RTFヘッダのコードページ宣言からエンコーディングを推定する。"""
    head = raw[:512]
    # \ansicpg932 → Shift_JIS (cp932)
    if re.search(rb'\\ansicpg932', head):
        return 'cp932'
    # \ansicpg65001 → UTF-8
    if re.search(rb'\\ansicpg65001', head):
        return 'utf-8'
    # ヘッダに宣言がない場合はバイト列で推定
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'cp932'


def decode_rtf_bytes(raw: bytes, encoding: str) -> str:
    """バイト列をRTFテキストとしてデコードする（\'xx エスケープを処理）。"""
    # \'xx エスケープ（RTFの非ASCII文字）を対応バイトに変換
    def replace_hex(m):
        byte_val = bytes([int(m.group(1), 16)])
        try:
            return byte_val.decode(encoding)
        except Exception:
            return ''

    text = re.sub(rb"\\'([0-9a-fA-F]{2})", replace_hex, raw)

    # 残りのバイト列をASCII範囲のみデコード（制御コードは無視）
    if isinstance(text, bytes):
        text = text.decode('ascii', errors='ignore')
    return text


def rtf_to_text(raw: bytes) -> str:
    """RTFバイナリからプレーンテキストを抽出する。"""
    encoding = detect_encoding(raw)
    rtf = decode_rtf_bytes(raw, encoding)

    # ── 改行・タブ制御コードを変換 ──
    rtf = re.sub(r'\\par\b', '\n', rtf)
    rtf = re.sub(r'\\line\b', '\n', rtf)
    rtf = re.sub(r'\\tab\b', '\t', rtf)
    rtf = re.sub(r'\\page\b', '\n\n', rtf)
    rtf = re.sub(r'\\sect\b', '\n\n', rtf)

    # ── 無視すべきグループ（フォントテーブル・カラーテーブル・スタイルシート等）を除去 ──
    ignored = (
        r'fonttbl', r'colortbl', r'stylesheet', r'listtable',
        r'listoverridetable', r'rsidtbl', r'generator', r'info',
        r'pict', r'object', r'fldinst',
    )
    for group in ignored:
        pattern = r'\{[^{}]*\\' + group + r'[^{}]*(?:\{[^{}]*\}[^{}]*)?\}'
        rtf = re.sub(pattern, '', rtf)

    # ── ネストしたグループを再帰的に除去（最大5パス）──
    for _ in range(5):
        rtf_new = re.sub(r'\{[^{}]*\}', '', rtf)
        if rtf_new == rtf:
            break
        rtf = rtf_new

    # ── RTF制御ワード・残余制御記号を除去 ──
    rtf = re.sub(r'\\[a-zA-Z]+\-?\d*\s?', '', rtf)
    rtf = re.sub(r'\\[^a-zA-Z]', '', rtf)
    rtf = re.sub(r'[{}]', '', rtf)

    # ── 連続空白行を整理 ──
    lines = [line.rstrip() for line in rtf.splitlines()]
    # 3行以上連続する空行を2行に圧縮
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


# ── メイン処理 ─────────────────────────────────────────────────────────

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
            print(f"[SKIP] {rtf_file.name} → {txt_file.name} (既存ファイル。--overwrite で上書き可)")
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
        description='RTF → TXTを一括変換（Shift_JIS / UTF-8 混在対応）'
    )
    parser.add_argument('input_dir',        help='RTFファイルが入っているフォルダのパス')
    parser.add_argument('-o', '--output_dir', default=None,
                        help='テキストファイルの出力先フォルダ（省略時は input_dir と同じ）')
    parser.add_argument('--overwrite', action='store_true',
                        help='既存の .txt ファイルを上書きする')
    args = parser.parse_args()

    convert_folder(args.input_dir, args.output_dir, args.overwrite)


if __name__ == '__main__':
    main()
