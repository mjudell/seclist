from tqdm.auto import tqdm
import argparse
import os
import pandas as pd
import sys
import shutil

from seclist.gather import get_missing_files
from seclist.parser import parse_pdf_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect SEC 13F filing indexes")
    parser.add_argument("task", help="[ pull | parse ]", type=str)
    parser.add_argument("-i", "--input", help="Input directory", type=str)
    parser.add_argument("-o", "--output", help="Output directory", type=str)
    parser.add_argument("-r", "--replace-existing", help="Replace existing files", action="store_true")
    parser.add_argument("-a", "--user-agent", help="Name and email for SEC user agent", type=str)
    args = parser.parse_args()

    if args.task == "pull":
        return get_raw_indexes(args.output, args.replace_existing, args.user_agent)
    elif args.task == "parse":
        return parse_raw_indexes(args.input, args.output, args.replace_existing)

    parser.print_help()

    return 1


def get_raw_indexes(output_dir: str, replace_existing: bool, user_agent: str) -> int:
    """
    Collect missing raw indexes

    Parameters
    ----------
    output_dir: str
        The path where the raw indexes are saved
    replace_existing: bool
        Delete existing index files
    user_agent: str
        The user-agent for the SEC query
    """
    if os.path.exists(output_dir) and replace_existing:
        shutil.rmtree(output_dir)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    get_missing_files(output_dir, user_agent)

    return 0


def parse_raw_indexes(input_dir: str, output_dir: str, replace_existing: bool) -> int:
    """
    Parse any unparsed raw filing indexes

    Parameters
    ----------
    input_dir: str
        Directory with the raw pdfs
    output_dir: str
        Directory with the parsed pdf contents
    replace_existing: bool
        Replace existing parses
    """ 
    if os.path.exists(output_dir) and replace_existing:
        shutil.rmtree(output_dir)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for file in tqdm(os.listdir(input_dir)):
        print(file)

        src = os.path.join(input_dir, file)
        tgt = os.path.join(output_dir, file)

        if os.path.exists(tgt):
            continue

        securities = parse_pdf_index(src)

        df = pd.DataFrame(securities, dtype=object)

        df.to_csv(tgt, header=True, index=False)

    return 0
