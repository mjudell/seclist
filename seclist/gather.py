from bs4 import BeautifulSoup
from tqdm.auto import tqdm
from typing import Dict, List
import os
import re
import requests
import time


SEC_IDX = 'https://www.sec.gov/divisions/investment/13flists.htm'


def get_uri_content(uri: str, user_agent: str) -> bytes:
    """
    Get raw bytes from a URI

    Parameters
    ----------
    uri: str
        The uri to fetch
    user_agent: str
        The user agent for the SEC query

    Returns
    -------
    bytes
        The raw content
    """
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate"
    }

    resp = requests.get(uri, verify=True, headers=headers)

    resp.raise_for_status()

    return resp.content


def get_sec_index(user_agent: str) -> List[Dict[str, str]]:
    """
    Get the index of all index files

    Parameters
    ----------
    user_agent: str
        The user agent for the SEC query

    Returns
    -------
    List[Dict[str, str]]
        Each item has "URI" and "file_name"
    """
    idx = get_uri_content(SEC_IDX, user_agent)
    soup = BeautifulSoup(idx, "lxml")
    matcher = re.compile(r"([0-9])(st|nd|rd|th) quarter ([0-9]{4,4})", re.IGNORECASE)
    index = []
    for ref in soup.find_all("a", href=True):
        if matcher.search(ref.text) is None:
            continue
        quarter, _, year = matcher.search(ref.text).groups()
        href = ref.get("href")
        uri = f"https://www.sec.gov{href}"
        if int(year) >= 2004:
            row = {"uri": uri, "file_name": f"{quarter}_{year}.pdf"}
            index.append(row)
    return index


def get_missing_files(output_dir: str, user_agent: str) -> None:
    """
    Collect the missing filing indexes

    Parameters
    ----------
    output_dir: str
        The directory that contains the raw indexes
    user_agent: str
        The user agent for the SEC query
    """
    all_files = get_sec_index(user_agent)

    for file in tqdm(all_files):

        pth = os.path.join(output_dir, file["file_name"])

        if os.path.exists(pth):
            continue

        content = get_uri_content(file["uri"], user_agent)

        with open(pth, "wb") as f:
            f.write(content)

        time.sleep(0.2)

    return None
