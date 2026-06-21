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
    fallback_message = f"Parsing was blocked by the site. Please click the link below to read the information about the word '{word}'."
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=5) # Добавили timeout, чтобы сайт не "висел"
        
        # Если сайт заблокировал нас (ошибка 403) или не ответил (не 200)
        if response.status_code != 200: 
            return fallback_message, url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        ety_elements = soup.find_all(class_="ety")
        
        if ety_elements:
            text_blocks = [el.get_text(strip=True) for el in ety_elements]
            return "\n\n".join(text_blocks), url
            
        # Если сайт открылся, но блок этимологии не найден
        return fallback_message, url
        
    except Exception:
        # Если пропал интернет или сайт "упал"
        return fallback_message, url

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
    url = f"https://www.multitran.com/m.exe?s={word}&l1=1&l2=2"
    fallback_message = f"Parsing was blocked by the site. Please click the link below to read the translation variants for the word '{word}'."
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200: 
            return fallback_message, url
        
        soup = BeautifulSoup(response.text, 'html.parser')
        translation_links = soup.find_all('a', href=re.compile(r'm\.exe\?t='))
        
        if translation_links:
            translations = []
            for link in translation_links:
                text = link.get_text(strip=True)
                if text and re.search(r'[а-яА-Я]', text):
                    translations.append(text)
                    if len(translations) >= 15: 
                        break
            
            unique_trans = list(dict.fromkeys(translations))
            if unique_trans:
                return "**Топ вариантов перевода:**\n\n" + "; ".join(unique_trans), url
                
        # Если защита Мультитрана скрыла от нас таблицу с переводами
        return fallback_message, url
        
    except Exception:
        return fallback_message, url

# --- ДВИГАТЕЛЬ 7: MERRIAM-WEBSTER API (НОВЫЙ!) ---
def get_mw_data(word, api_key):
    if not api_key:
        return "⚠️ Пожалуйста, введите ваш Merriam-Webster API Key в боковом меню слева.", ""
    
    url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200: 
            return "Ошибка подключения к Merriam-Webster API.", ""
        
        data = response.json()
        # Если слово не найдено, API возвращает список похожих слов
        if not data or not isinstance(data[0], dict):
            suggestions = ", ".join(data[:5]) if data else "Нет вариантов."
            return f"Слово не найдено. Возможно, вы имели в виду: {suggestions}", ""

        entry = data[0]
        result_text = ""
        
        if 'shortdef' in entry:
            result_text += "**Краткое значение:** " + "; ".join(entry['shortdef']) + "\n\n"
            
        if 'et' in entry:
            # Парсинг сложного JSON-массива этимологии от MW
            et_text = str(entry['et'][0][1])
            # Очистка от технических тегов вроде {it}
            et_text = re.sub(r'\{.*?\}', '', et_text)
            result_text += "**Этимология:** " + et_text

        if not result_text:
            result_text = "Слово найдено, но раздел этимологии отсутствует."

        return result_text, f"https://www.merriam-webster.com/dictionary/{word}"
    except Exception as e:
        return f"Error: {e}", ""



# --- ВЕБ-ИНТЕРФЕЙС (STREAMLIT) ---

st.set_page_config(page_title="Etymology Aggregator", page_icon="📜", layout="wide")

st.title("📜 Advanced Etymology Aggregator")
st.markdown("Поисковый инструмент для лингвистов. Ищет данные по онлайн-словарям, базам идиом и вашим локальным книгам. ⚠️ Хотим предупредить: некотрые источники (такие как Multitran, AHD Dictionary) имеют строгую систему отслеживания автоматического сбора данных, поэтому текст может не отображаться в приложении. Если вы столкнулись с этим, пожалуйста, перейдите по ссылке для быстрого доступа к оригинальной статье на сайте.")

# Настройки поиска (расширенные)
st.write("### ⚙️ Источники поиска")
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
with col1: use_wik = st.checkbox("Wiktionary", value=True)
with col2: use_etym = st.checkbox("Etymonline", value=True)
with col3: use_ahd = st.checkbox("AHD", value=True)
with col4: use_phrase = st.checkbox("Phrase Finder", value=False) 
with col5: use_multi = st.checkbox("Multitran", value=False)
with col6: use_mw = st.checkbox("Merriam-Webster", value=True)
    
# --- СЕКРЕТНЫЕ КЛЮЧИ API (Берем из хранилища Streamlit) ---
try:
    mw_key = st.secrets["MW_KEY"]
except:
    mw_key = ""

st.sidebar.divider()
st.sidebar.header("📚 Ваши PDF Словари")
st.sidebar.info("Загрузите сюда исторические словари для локального поиска.")
uploaded_pdfs = st.sidebar.file_uploader("Перетащите PDF сюда", type=["pdf"], accept_multiple_files=True)

user_word = st.text_input("Enter a word or phrase to analyze:", placeholder="For example: chivalry, knight, bite the bullet").strip().lower()

if st.button("Начать поиск", type="primary"):
    if user_word:
        with st.spinner(f"Опрашиваем лингвистические базы данных для '{user_word}'..."):
            
            if use_wik:
                wik_text, wik_link = get_wiktionary_data(user_word)
                st.subheader("🏛️ Wiktionary API")
                st.write(wik_text)
                st.markdown(f"[Ссылка на источник]({wik_link})")
                st.divider()
            

            if use_mw:
                mw_text, mw_link = get_mw_data(user_word, mw_key)
                st.subheader("📙 Merriam-Webster Collegiate API")
                st.write(mw_text)
                if mw_link: st.markdown(f"[Ссылка на источник]({mw_link})")
                st.divider()

            if use_etym:
                etym_text, etym_link = get_etymonline_data(user_word)
                st.subheader("🕰️ Online Etymology Dictionary")
                st.write(etym_text)
                st.markdown(f"[Ссылка на источник]({etym_link})")
                st.divider()

            if use_ahd:
                ahd_text, ahd_link = get_ahd_data(user_word)
                st.subheader("🦅 American Heritage Dictionary")
                st.write(ahd_text)
                st.markdown(f"[Ссылка на источник]({ahd_link})")
                st.divider()
                
            if use_phrase:
                phrase_text, phrase_link = get_phrasefinder_data(user_word)
                st.subheader("💬 The Phrase Finder (Idioms)")
                st.write(phrase_text)
                st.markdown(f"[Ссылка на источник]({phrase_link})")
                st.divider()
                
            if use_multi:
                multi_text, multi_link = get_multitran_data(user_word)
                st.subheader("🇷🇺 Multitran (Translation Variants)")
                st.write(multi_text)
                st.markdown(f"[Смотреть все значения]({multi_link})")
                st.divider()
            
            if uploaded_pdfs:
                st.subheader("📖 Поиск по локальным PDF")
                for f in uploaded_pdfs: f.seek(0) 
                pdf_text, pdf_source = get_pdf_data(user_word, uploaded_pdfs)
                st.write(pdf_text)
            elif not (use_wik or use_etym or use_ahd or use_phrase or use_multi or use_mw or use_oxford):
                st.info("Вы не выбрали ни одного источника для поиска.")
    else:
        st.warning("Пожалуйста, введите слово или фразу для поиска.")
