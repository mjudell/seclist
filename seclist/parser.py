from typing import Dict, Generator, List
import re
import subprocess
import sys


SECURITY_SCHEMA = \
"""
cusip         str
issuer        str
date          m/d/y str
description   str
page          int (page number where security was found)
optionable    bool
added         bool
deleted       bool
"""


def is_first_page(pdf_file: str, page_num: int) -> bool:
    """
    Determine if a PDF page is the start of the securities index

    Parameters
    ----------
    pdf_file: str
        Path to the pdf
    page_num: int
        Candidate page number

    Returns
    -------
    bool
        True if the provided page num is the start of the securities index
    """
    pn = str(page_num)
    command = ['pdftotext', '-f', pn, '-l', pn, '-layout', pdf_file, '-']
    try:
        proc = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            raise ValueError("Malformed data. Parse failed.")
        return stdout
    except OSError:
        raise RuntimeError("It looks like you are not running Linux or dont have pdftotext installed")

    return re.search(b'run[ ]*?date.*?\x0c', re.DOTALL|re.IGNORECASE) is not None


def find_first_page(pdf_file: str) -> str:
    """
    Find the first PDF page that has the securities index in it

    Parameters
    ----------
    pdf_file: str
        Path the the pdf file

    Returns
    -------
    str
        A string representation of the page number containing the first  filings index page    
    """
    for i in range(1, 4):
        if is_first_page(pdf_file, i):
            return str(i)
    raise ValueError("More than two header pages detected")


def get_pdf_text_bytes(pdf_file: str) -> bytes:
    """
    Convert pdf to text and return result as raw bytes

    Parameters
    ----------
    pdf_file: str
        Path of the pdf file

    Returns
    -------
    buf
        The raw text as bytes
    """
    first_page = find_first_page(pdf_file)
    command = ['pdftotext', '-f', first_page, '-layout', pdf_file, '-']
    try:
        proc = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            raise ValueError("Malformed data. Parse failed.")
        return stdout
    except OSError:
        raise RuntimeError("It looks like you are not running Linux or dont have pdftotext installed")


def yield_pages_as_bytes(pdf_file: str) -> Generator[None, bytes, None]:
    """
    Yield raw bytes of text pages in pdf

    Parameters
    ----------
    pdf_file: str
        Path to pdf file
    """
    pdf_text = get_pdf_text_bytes(pdf_file)
    page_sep = re.compile(b'run[ ]*?date.*?\x0c', re.DOTALL|re.IGNORECASE)
    for page in page_sep.finditer(pdf_text):
        yield pdf_text[page.start():page.end()]
    return None


def validate_header(utf_list: List[str]) -> None:
    """
    Raise an exception if the page header is malformed

    Parameters
    ----------
    utf_list: List[str]
        Parsed header
    """
    if ('run date' not in utf_list[0].lower() or
        'page' not in utf_list[0].lower() or
        'run time' not in utf_list[1].lower() or
        'year' not in utf_list[1].lower() or
        utf_list[2] != '' or
        'CUSIP NO' not in utf_list[3] or
        'ISSUER NAME' not in utf_list[3] or
        'ISSUER DESCRIPTION' not in utf_list[3] or
        'STATUS' not in utf_list[3]):
        raise ValueError('Malformed page header.')
    return None


def extract_date(line: str) -> str:
    """
    Extract a date from a text line

    Parameters
    ----------
    line: str
        A text line from the pdf

    Returns
    -------
    str
        The extracted date
    """
    m = re.search('run\s*?date:\s*?[0-9]{1,2}/[0-9]{1,2}/[0-9]{4,4}', line, re.IGNORECASE)
    date_full = line[m.start():m.end()]
    m = re.search('[0-9]{1,2}/[0-9]{1,2}/[0-9]{4,4}', line)
    date = date_full[m.start():m.end()]
    return date


def extract_pagenum(line: str) -> int:
    """
    Extract the pdf page's number label

    Parameters
    ----------
    line: str
        A line of text from the pdf

    Returns
    -------
    int
        The page number
    """
    m = re.search('page\s*?[0-9]{1,40}', line, re.IGNORECASE)
    pagenum = line[m.start():m.end()]
    pagenum = pagenum.lower().replace('page', '').strip()
    return int(pagenum)


def parse_page(bytes_arr: bytes) -> List[Dict[str, str]]:
    """
    Parse security entries out of a single pdf page

    Parameters
    ----------
    bytes_arr: bytes
        Raw page bytes

    Returns
    -------
    List[Dict]
        The securities on the page
    """

    '''Parse security entries out of a pdf page

    Args
    ----
    bytes_arr (bytes): a single page of entries

    Returns
    -------
    securities (list[dict]): a list of security entries conforming to security_schema
    expected_lines (int): number of securities expected in the whole document,
        None if this is not the final page
    '''
    if bytes_arr[-1].to_bytes(1, 'little') != b'\x0c':
        raise ValueError('Page feed should be final byte.')

    lines = bytes_arr[:-1].decode('utf-8').split('\n')
    validate_header(lines[:4])

    date = extract_date(lines[0])
    pagenum = extract_pagenum(lines[0])

    cusip_s, cusip_e = re.search('CUSIP NO', lines[3]).span()
    issuer_s, issuer_e = re.search('ISSUER NAME', lines[3]).span()
    descrp_s, descrp_e = re.search('ISSUER DESCRIPTION', lines[3]).span()

    securities = []
    expected_lines = None
    for line in lines[4:]:

        if line.strip() == '':
            continue

        if 'total count' in line.lower():
            expected_lines = int(''.join([s for s in line if s.isdigit()]))
            continue

        cusip = line[cusip_s:issuer_s]      # note the bounds
        issuer = line[issuer_s:descrp_s].strip()
        description = line[descrp_s:]

        security = {
            'cusip': cusip.replace('*', '').strip(),
            'issuer': issuer,
            'description': description.replace('ADDED','')\
                                      .replace('DELETED','').strip(),
            'date': date,
            'page': pagenum,
            'optionable': '*' in cusip,
            'added': 'ADDED' in description,
            'deleted': 'DELETED' in description}

        cmatch = re.match('^[a-zA-Z0-9]{6,6} [a-zA-Z0-9]{2,2} [a-zA-Z0-9]{1,1}$',
            security['cusip'])
        if cmatch is None:
            raise MalformedDataError('Malformed CUSIP {:}'.format(security['cusip']))

        securities.append(security)

    return securities, expected_lines


def parse_pdf_index(pdf_file: str) -> List[Dict[str, str]]:
    """
    Parse all the securities information from a pdf file

    Parameters
    ----------
    pdf_file: str
        Path to the securities list pdf

    Returns
    -------
    List[Dict[str, str]]
        The securities index
    """
    securities = []
    for page in yield_pages_as_bytes(pdf_file):
        sec, expected_lines = parse_page(page)
        securities.extend(sec)

    if len(securities) != expected_lines:
        raise ValueError(f"Total securities {len(securities)} does not match expectation {expected_lines}")

    return securities
