# テキストファイルを結合
import os
from pathlib import Path

# === 設定 ===
folder_path = Path(r"D:\Download\JWdoc")   # 結合対象フォルダ
output_file = Path(r"D:\Download\JWdoc\result.txt")  # 出力ファイル名
recursive = False          # サブフォルダも含める場合 True
include_header = True      # 各ファイルの先頭にファイル名見出しを入れる
separator_line = "-" * 80  # ファイル間の区切り線（変更可）
encoding_read = "utf-8"    # 読み取り想定エンコード
# encoding_read = "shift_jis"    # 読み取り想定エンコード 古いテキストファイルなどでUTF-8以外の場合はこちらを使用
encoding_write = "utf-8"   # 出力エンコード

def list_text_files(base: Path, recursive: bool):
    if not base.exists():
        raise FileNotFoundError(f"フォルダが見つかりません: {base}")
    pattern = "**/*.txt" if recursive else "*.txt"
    files = sorted(base.glob(pattern), key=lambda p: p.name.lower())
    return [f for f in files if f.is_file()]

def combine_texts(files, output_path: Path):
    if not files:
        print("結合対象の .txt ファイルが見つかりませんでした。")
        return

    # 出力先フォルダが無ければ作成
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding=encoding_write, newline="\n") as out:
        for idx, f in enumerate(files, start=1):
            try:
                with open(f, "r", encoding=encoding_read, errors="replace") as inp:
                    content = inp.read()
            except Exception as e:
                print(f"[警告] 読み込み失敗: {f} -> {e}")
                continue

            # メタ情報（見出し＋区切り）
            if include_header:
                out.write(f"{separator_line}\n")
                out.write(f"# {f.name}\n")
                out.write(f"{separator_line}\n")

            out.write(content)

            # 最後でなければ改行＋区切りを追加
            if idx != len(files):
                out.write("\n")
                if not include_header:
                    out.write(f"{separator_line}\n")

    print(f"結合完了: {output_path}  (ファイル数: {len(files)})")

if __name__ == "__main__":
    files = list_text_files(folder_path, recursive=recursive)
    combine_texts(files, output_file)
