import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import fitz  # PyMuPDF

# --- ДВИГАТЕЛЬ 1: WIKTIONARY ---
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

# --- ДВИГАТЕЛЬ 2: ETYMONLINE ---
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

# --- ДВИГАТЕЛЬ 3: AMERICAN HERITAGE DICTIONARY ---
def get_ahd_data(word):
    url = f"https://www.ahdictionary.com/word/search.html?q={word}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200: 
            return "Word not found on AHD.", url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        ety_elements = soup.find_all(class_="ety")
        
        if ety_elements:
            text_blocks = [el.get_text(strip=True) for el in ety_elements]
            return "\n\n".join(text_blocks), url
            
        return "Click the link below to read the information.", url
    except Exception as e:
        return f"Error connecting to AHD: {e}", url

# --- ДВИГАТЕЛЬ 4: THE PHRASE FINDER (НОВЫЙ!) ---
def get_phrasefinder_data(phrase):
    # Заменяем пробелы на дефисы для правильной ссылки (bite the bullet -> bite-the-bullet)
    formatted_phrase = phrase.replace(' ', '-').lower()
    url = f"https://www.phrases.org.uk/meanings/{formatted_phrase}.html"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200: 
            return "Phrase not found. Try searching for a specific idiom instead of a single word.", url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Ищем все абзацы, отсеивая мусор вроде копирайтов и навигации
        paragraphs = soup.find_all("p")
        text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30 and "Copyright" not in p.get_text()]
        
        if text_blocks:
            # Берем первые 4 абзаца, чтобы не перегружать экран лишней информацией
            return "\n\n".join(text_blocks[:4]), url
            
        return "Meaning section could not be parsed.", url
    except Exception as e:
        return f"Error connecting to Phrase Finder: {e}", url

# --- ДВИГАТЕЛЬ 5: ЛОКАЛЬНЫЙ ПОИСК В PDF ---
def get_pdf_data(word, uploaded_files, max_results=3):
    results = []
    seen = set()
    pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)

    for uploaded_file in uploaded_files:
        if len(results) >= max_results: break
        try:
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            fname = uploaded_file.name

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

                    results.append(f"**[{fname} (Page {page_num + 1})]**\n\n{block_text}")
                    if len(results) >= max_results: break
            doc.close()
        except Exception as e: 
            return f"Error reading PDF: {e}"

    if results:
        return "\n\n---\n\n".join(results), "Local PDF"
    return f"No matches found for '{word}' in the uploaded files.", "Local PDF"

# --- ДВИГАТЕЛЬ 6: MULTITRAN (Англо-Русский перевод) ---
def get_multitran_data(word):
    # l1=1 (English), l2=2 (Russian)
    url = f"https://www.multitran.com/m.exe?s={word}&l1=1&l2=2"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200: 
            return "Word not found on Multitran.", url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Multitran хранит переводы в ячейках таблицы с классом "trans"
        trans_cells = soup.find_all('td', class_='trans')
        
        if trans_cells:
            translations = []
            for cell in trans_cells:
                text = cell.get_text(strip=True)
                # Отсеиваем мусор и слишком длинные/короткие строки
                if text and len(text) > 1 and "{" not in text:
                    translations.append(text)
                    if len(translations) >= 15: # Берем топ-15 вариантов
                        break
            
            # Убираем дубликаты
            unique_trans = list(dict.fromkeys(translations))
            if unique_trans:
                formatted_text = "**Современные варианты перевода:**\n\n" + "; ".join(unique_trans)
                return formatted_text, url
                
        return "Translation section could not be parsed cleanly.", url
    except Exception as e:
        return f"Error connecting to Multitran: {e}", url

# --- ВЕБ-ИНТЕРФЕЙС (STREAMLIT) ---

st.set_page_config(page_title="Etymology Aggregator", page_icon="📜", layout="wide")

st.title("📜 Advanced Etymology Aggregator")
st.markdown("Поисковый инструмент для компьютерной лингвистики. Ищет данные по онлайн-словарям, базам идиом и вашим локальным книгам.")

st.write("### ⚙️ Источники поиска")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    use_wik = st.checkbox("Wiktionary", value=True)
with col2:
    use_etym = st.checkbox("Etymonline", value=True)
with col3:
    use_ahd = st.checkbox("AHD Dictionary", value=True)
with col4:
    use_phrase = st.checkbox("Phrase Finder", value=True)
with col5:
    use_multi = st.checkbox("Multitran (RU)", value=False) # По умолчанию выключен

# Боковая панель
st.sidebar.header("📚 Ваши PDF Словари")
st.sidebar.info("Загрузите сюда ваши исторические словари, чтобы программа искала слова внутри них.")
uploaded_pdfs = st.sidebar.file_uploader("Перетащите PDF сюда", type=["pdf"], accept_multiple_files=True)

# Обратите внимание на обновленный placeholder с идиомой!
user_word = st.text_input("Enter a word or phrase to analyze:", placeholder="Например: chivalry, pilgrim, или bite the bullet").strip().lower()

if st.button("Начать поиск", type="primary"):
    if user_word:
        with st.spinner(f"Ищем '{user_word}' по всем базам данных..."):
            
            # --- Wiktionary ---
            if use_wik:
                wik_text, wik_link = get_wiktionary_data(user_word)
                st.subheader("🏛️ Wiktionary API")
                st.write(wik_text)
                st.markdown(f"[Ссылка на источник]({wik_link})")
                st.divider()
            
            # --- Etymonline ---
            if use_etym:
                etym_text, etym_link = get_etymonline_data(user_word)
                st.subheader("🕰️ Online Etymology Dictionary")
                st.write(etym_text)
                st.markdown(f"[Ссылка на источник]({etym_link})")
                st.divider()

            # --- AHD Dictionary ---
            if use_ahd:
                ahd_text, ahd_link = get_ahd_data(user_word)
                st.subheader("🦅 American Heritage Dictionary")
                st.write(ahd_text)
                st.markdown(f"[Ссылка на источник]({ahd_link})")
                st.divider()
                
            # --- The Phrase Finder (Новый блок!) ---
            if use_phrase:
                phrase_text, phrase_link = get_phrasefinder_data(user_word)
                st.subheader("💬 The Phrase Finder (Idioms & Origins)")
                st.write(phrase_text)
                st.markdown(f"[Ссылка на источник]({phrase_link})")
                st.divider()

            # --- Multitran ---
            if use_multi:
                multi_text, multi_link = get_multitran_data(user_word)
                st.subheader("🇷🇺 Multitran (Translation Variants)")
                st.write(multi_text)
                st.markdown(f"[Смотреть все значения]({multi_link})")
                st.divider()
                
            # --- PDF Поиск ---
            if uploaded_pdfs:
                st.subheader("📖 Поиск по локальным PDF")
                for f in uploaded_pdfs: f.seek(0) 
                pdf_text, pdf_source = get_pdf_data(user_word, uploaded_pdfs)
                st.write(pdf_text)
            else:
                st.info("💡 PDF-файлы не загружены. Вы можете перетащить их в меню слева для поиска по локальным книгам.")
    else:
        st.warning("Пожалуйста, введите слово или фразу для поиска.")
