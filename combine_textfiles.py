# テキストファイルを結合
import os
import sys
import logging
from pathlib import Path
from argparse import ArgumentParser
from typing import List

# === ロギング設定 ===
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# === デフォルト設定 ===
DEFAULT_CONFIG = {
    "folder_path": Path(r"D:\Download\JWdoc"),
    "output_file": Path(r"D:\Download\JWdoc\result.txt"),
    "recursive": False,
    "include_header": True,
    "separator_line": "-" * 80,
    "encoding_read": "utf-8",
# 古いテキストファイルなどでUTF-8以外の場合はこちらを使用    
#     "encoding_read": "shift_jis",
    "encoding_write": "utf-8",
}

def list_text_files(base: Path, recursive: bool, exclude_output: Path = None) -> List[Path]:
    """
    指定フォルダ内のテキストファイルを取得
    
    Args:
        base: 対象フォルダ
        recursive: サブフォルダも含めるか
        exclude_output: 除外するファイルパス（出力ファイル）
    
    Returns:
        ファイルパスのリスト
    
    Raises:
        FileNotFoundError: フォルダが存在しない場合
    """
    if not base.exists():
        raise FileNotFoundError(f"フォルダが見つかりません: {base}")
    
    if not base.is_dir():
        raise NotADirectoryError(f"ディレクトリではありません: {base}")
    
    pattern = "**/*.txt" if recursive else "*.txt"
    files = sorted(base.glob(pattern), key=lambda p: p.name.lower())
    
    # 出力ファイル自体を除外
    if exclude_output:
        files = [f for f in files if f.resolve() != exclude_output.resolve()]
    
    return [f for f in files if f.is_file()]

def combine_texts(
    files: List[Path],
    output_path: Path,
    include_header: bool = True,
    separator_line: str = "-" * 80,
    encoding_read: str = "utf-8",
#     encoding_read: str = "shift_jis",
    encoding_write: str = "utf-8"
) -> bool:
    """
    複数のテキストファイルを結合
    
    Args:
        files: 結合対象ファイルのリスト
        output_path: 出力ファイルパス
        include_header: ファイル名ヘッダーを含めるか
        separator_line: ファイル間の区切り線
        encoding_read: 入力ファイルのエンコーディング
        encoding_write: 出力ファイルのエンコーディング
    
    Returns:
        成功時 True、失敗時 False
    """
    if not files:
        logger.warning("結合対象の .txt ファイルが見つかりませんでした。")
        return False

    # 出力ファイルが既に存在する場合は確認
    if output_path.exists():
        response = input(f"出力ファイルが既に存在します: {output_path}\n上書きしますか？ (y/n): ")
        if response.lower() != 'y':
            logger.info("処理をキャンセルしました。")
            return False

    try:
        # 出力先フォルダが無ければ作成
        output_path.parent.mkdir(parents=True, exist_ok=True)

        skipped_count = 0
        with open(output_path, "w", encoding=encoding_write, newline="\n") as out:
            for idx, file_path in enumerate(files, start=1):
                try:
                    with open(file_path, "r", encoding=encoding_read, errors="replace") as inp:
                        content = inp.read()
                except Exception as e:
                    logger.warning(f"読み込み失敗: {file_path} -> {e}")
                    skipped_count += 1
                    continue

                # メタ情報（見出し＋区切り）
                if include_header:
                    out.write(f"{separator_line}\n")
                    out.write(f"# {file_path.name}\n")
                    out.write(f"{separator_line}\n")

                out.write(content)

                # 最後でなければ改行＋区切りを追加
                if idx != len(files):
                    out.write("\n")
                    if not include_header:
                        out.write(f"{separator_line}\n")

        processed_count = len(files) - skipped_count
        logger.info(f"結合完了: {output_path}  (処理: {processed_count}/{len(files)}ファイル)")
        
        if skipped_count > 0:
            logger.warning(f"{skipped_count}個のファイルがスキップされました。")
        
        return True

    except Exception as e:
        logger.error(f"ファイル書き込みエラー: {e}")
        return False

def main():
    """メイン処理"""
    parser = ArgumentParser(description="テキストファイルを結合します")
    parser.add_argument("-f", "--folder", type=Path, default=DEFAULT_CONFIG["folder_path"],
                        help="結合対象フォルダ")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_CONFIG["output_file"],
                        help="出力ファイル")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="サブフォルダも含める")
    parser.add_argument("--no-header", action="store_true",
                        help="ファイル名ヘッダーを表示しない")
    parser.add_argument("--encoding", default=DEFAULT_CONFIG["encoding_read"],
                        help="入力ファイルのエンコーディング")
    
    args = parser.parse_args()

    try:
        files = list_text_files(
            args.folder,
            recursive=args.recursive,
            exclude_output=args.output
        )
        
        success = combine_texts(
            files,
            args.output,
            include_header=not args.no_header,
            encoding_read=args.encoding,
            encoding_write=DEFAULT_CONFIG["encoding_write"]
        )
        
        sys.exit(0 if success else 1)

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
