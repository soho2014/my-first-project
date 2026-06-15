#!/usr/bin/env python3
"""
RTFファイルをテキストファイルに一括変換するスクリプト
Shift_JIS (cp932) / UTF-8 混在対応
標準ライブラリのみ使用
2026/6/12 Claude修正
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
    """
    スタックベースのRTFパーサーでプレーンテキストを抽出する。

    正規表現ベースの方法はグループのネスト処理が不完全になるため、
    1文字ずつ解析するパーサーを使用する。
    """
    encoding = detect_encoding(raw)

    # UTF-8 RTFは生のUTF-8バイト列が埋め込まれているのでそのままデコード。
    # Shift_JIS RTFは \'xx エスケープで非ASCII文字が表現されるため latin-1 を使う。
    if encoding == 'utf-8':
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
    else:
        text = raw.decode('latin-1')

    # スキップすべきグループ（フォントテーブル、画像、ハイパーリンク命令等）
    SKIP_WORDS = {
        'fonttbl', 'colortbl', 'stylesheet', 'listtable', 'listoverridetable',
        'rsidtbl', 'generator', 'info', 'pict', 'object', 'fldinst',
        'header', 'footer', 'headerl', 'headerr', 'footerl', 'footerr',
        'footnote', 'annotation', 'upr',
    }

    output = []
    stack  = []   # グループを抜けたときに skip を元に戻すためのスタック
    skip   = False
    i      = 0
    n      = len(text)

    while i < n:
        c = text[i]

        # ── グループ開始 ──────────────────────────────────────────────
        if c == '{':
            stack.append(skip)
            # {\* ...} は省略可能グループ（常にスキップ）
            if text[i+1:i+3] == '\\*':
                skip = True
            i += 1

        # ── グループ終了 ──────────────────────────────────────────────
        elif c == '}':
            if stack:
                skip = stack.pop()
            i += 1

        # ── 制御ワード / 制御記号 ─────────────────────────────────────
        elif c == '\\':
            i += 1
            if i >= n:
                break

            nc = text[i]

            if nc == '\\':                          # \\ → バックスラッシュ
                if not skip: output.append('\\')
                i += 1

            elif nc == '{':                         # \{ → 左波括弧リテラル
                if not skip: output.append('{')
                i += 1

            elif nc == '}':                         # \} → 右波括弧リテラル
                if not skip: output.append('}')
                i += 1

            elif nc == '\n':                        # \<改行> → 段落区切り
                if not skip: output.append('\n')
                i += 1

            elif nc == '~':                         # \~ → ノーブレークスペース
                if not skip: output.append('\u00a0')
                i += 1

            elif nc == '-':                         # \- → オプショナルハイフン（無視）
                i += 1

            elif nc == '_':                         # \_ → ノーブレークハイフン
                if not skip: output.append('-')
                i += 1

            elif nc == "'":                         # \'xx → バイトエスケープ
                if i + 2 < n and re.match(r'[0-9a-fA-F]{2}', text[i+1:i+3]):
                    if not skip:
                        # 連続する \'xx をまとめてデコード（マルチバイト対応）
                        hex_bytes = [int(text[i+1:i+3], 16)]
                        j = i + 3
                        while (j + 2 < n
                               and text[j] == '\\'
                               and text[j+1] == "'"
                               and re.match(r'[0-9a-fA-F]{2}', text[j+2:j+4])):
                            hex_bytes.append(int(text[j+2:j+4], 16))
                            j += 4
                        output.append(bytes(hex_bytes).decode(encoding, errors='replace'))
                        i = j
                    else:
                        i += 3
                else:
                    i += 1

            elif nc.isalpha():                      # \word → 制御ワード
                j = i
                while j < n and text[j].isalpha():
                    j += 1
                word = text[i:j]

                # オプションの数値パラメータ
                num_start = j
                if j < n and (text[j] == '-' or text[j].isdigit()):
                    if text[j] == '-': j += 1
                    while j < n and text[j].isdigit(): j += 1
                num_str = text[num_start:j]
                num = int(num_str) if num_str and num_str != '-' else None

                # 制御ワードの後続スペースは区切りとして消費
                if j < n and text[j] == ' ':
                    j += 1
                i = j

                if word in SKIP_WORDS:
                    # このグループの終わり(})まで出力しない
                    skip = True
                elif word == 'fldrslt':
                    # ハイパーリンクの表示テキスト部分は出力する
                    skip = False
                elif not skip:
                    if   word == 'par':  output.append('\n')
                    elif word == 'line': output.append('\n')
                    elif word == 'tab':  output.append('\t')
                    elif word == 'page': output.append('\n\n')
                    elif word == 'sect': output.append('\n\n')
                    elif word == 'cell': output.append('\t')
                    elif word == 'row':  output.append('\n')
                    elif word == 'u' and num is not None:
                        # \uN? → Unicode文字（\uN の後の代替文字 ? をスキップ）
                        code = num if num >= 0 else num + 65536
                        output.append(chr(code))
                        if i < n and text[i] == '?':
                            i += 1
                    # その他の制御ワード（フォント指定・書式等）は無視

            else:
                # 未知の制御記号は無視
                i += 1

        # ── 通常文字 ──────────────────────────────────────────────────
        else:
            if not skip:
                output.append(c)
            i += 1

    result = ''.join(output)

    # 整形：連続する空行を最大2行に圧縮
    lines = [line.rstrip() for line in result.splitlines()]
    out, blank_count = [], 0
    for line in lines:
        if line == '':
            blank_count += 1
            if blank_count <= 2:
                out.append('')
        else:
            blank_count = 0
            out.append(line)

    return '\n'.join(out).strip()


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
            print(f"[SKIP] {rtf_file.name} → {txt_file.name}  (--overwrite で上書き可)")
            skipped += 1
            continue

        try:
            raw  = rtf_file.read_bytes()
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
