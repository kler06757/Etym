import requests
from bs4 import BeautifulSoup
import textwrap
import os
import re

try:
    import fitz
except ImportError:
    os.system('pip install pymupdf -q')
    import fitz

def get_wiktionary_data(word):
    url = f"https://en.wiktionary.org/w/api.php?action=query&prop=extracts&titles={word}&format=json&explaintext=1"
    link_to_source = f"https://en.wiktionary.org/wiki/{word}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            if "extract" in page_info:
                text = page_info["extract"]
                if "== English ==" in text:
                    english_section = text.split("== English ==")[1].split("\n== ")[0]
                    if "=== Etymology ===" in english_section:
                        etym = english_section.split("=== Etymology ===")[1].split("===")[0]
                        return etym.strip().replace('\n', ' '), link_to_source
                    elif "=== Etymology 1 ===" in english_section:
                        etym = english_section.split("=== Etymology 1 ===")[1].split("===")[0]
                        return etym.strip().replace('\n', ' '), link_to_source
        return "No specific English etymology found.", link_to_source
    except Exception:
        return "Error connecting to Wiktionary.", link_to_source

def get_etymonline_data(word):
    url = f"https://www.etymonline.com/word/{word}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return "Word not found on Etymonline.", url
        soup = BeautifulSoup(response.text, 'html.parser')
        sections = soup.find_all("section")
        for sec in sections:
            if sec.find("p"):
                paragraphs = sec.find_all("p")
                ad_keywords = ["remove ads", "premium member", "log into see", "share this"]
                text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20 and not any(k in p.get_text().lower() for k in ad_keywords)]
                if text_blocks:
                    return "\n\n".join(text_blocks), url
        return "Etymology text could not be parsed.", url
    except Exception:
        return "Error connecting to Etymonline.", url

def get_pdf_data(word, max_results=3):
    # Mapping of filenames to their online source links
    pdf_links = {
        'wedghe0001dicofev00002.pdf': 'https://brittlebooks.library.illinois.edu/brittlebooks_open/Books2010-05/wedghe0001dicofe/wedghe0001dicofev00002/wedghe0001dicofev00002.pdf',
        'A_dictionary_of_English_etymology_(IA_cu31924031471711).pdf': 'https://upload.wikimedia.org/wikipedia/commons/2/2c/A_dictionary_of_English_etymology_%28IA_cu31924031471711%29.pdf',
        '1874_Chambers_Etymological.pdf': 'https://i2i.org/wp-content/uploads/2017/11/1874_Chambers_Etymological.pdf'
    }

    results = []
    seen = set()
    pdf_files = set()
    search_dirs = ['.', '/content', '/content/drive/MyDrive']

    for directory in search_dirs:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if filename.lower().endswith('.pdf'):
                    pdf_files.add(os.path.abspath(os.path.join(directory, filename)))

    print(f"[Debug] Found {len(pdf_files)} unique PDF files to search.")
    pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)

    for full_path in sorted(pdf_files):
        if len(results) >= max_results: break
        if not os.path.exists(full_path): continue
        try:
            doc = fitz.open(full_path)
            fname = os.path.basename(full_path)
            link = pdf_links.get(fname, "Local File")

            for page_num in range(len(doc)):
                if len(results) >= max_results: break
                page = doc.load_page(page_num)
                blocks = page.get_text("blocks")
                blocks = sorted(blocks, key=lambda b: (round(b[1]), round(b[0])))

                for block in blocks:
                    block_text = block[4]
                    block_text = re.sub(r'-\n', '', block_text)
                    block_text = re.sub(r'\s+', ' ', block_text).strip()
                    if len(block_text) < 30 or not pattern.search(block_text): continue

                    normalized = block_text.lower()
                    if normalized in seen: continue
                    seen.add(normalized)

                    wrapped_text = textwrap.fill(block_text, width=75)
                    results.append((wrapped_text, f"{fname} (Page {page_num + 1})\nLink: {link}"))
                    if len(results) >= max_results: break
            doc.close()
        except Exception as e: print(f"[Error] {full_path}: {e}")

    if results:
        output = "\n\n---\n\n".join(f"[{source}]\n{text}" for text, source in results)
        return output, "PDF Library"
    return f"No matches found for '{word}' in the files checked.", "PDF Library"

def print_comparative_table(word, wik_data, etym_data, pdf_data):
    print("\n" + "="*80)
    print(f" AGGREGATED SEARCH FOR: {word.upper()}")
    print("="*80)
    def wrap(t): return textwrap.fill(t, width=75)
    print(f"\n[ SOURCE: Wiktionary ]\n{wrap(wik_data[0])}\nLink: {wik_data[1]}")
    print("\n" + "-"*80)
    print(f"\n[ SOURCE: Online Etymology Dictionary ]\n{wrap(etym_data[0])}\nLink: {etym_data[1]}")
    print("\n" + "-"*80)
    print(f"\n[ SOURCE: Local PDF Search ]\n{pdf_data[0]}\n")
    print("="*80 + "\n")

if __name__ == "__main__":
    user_word = input("Enter a word to analyze: ").strip().lower()
    if user_word:
        print(f"Scanning sources for '{user_word}'...")
        wik_data = get_wiktionary_data(user_word)
        etym_data = get_etymonline_data(user_word)
        pdf_results = get_pdf_data(user_word)
        print_comparative_table(user_word, wik_data, etym_data, pdf_results)