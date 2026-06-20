import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import fitz  # PyMuPDF

# --- ВАШ ДВИГАТЕЛЬ (Оставлен без изменений логики) --- 

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

def get_pdf_data(word, uploaded_files, max_results=3):
    # Адаптировано для работы с файлами, загруженными через интерфейс сайта
    results = []
    seen = set()
    pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)

    for uploaded_file in uploaded_files:
        if len(results) >= max_results: break
        try:
            # Читаем PDF прямо из оперативной памяти сервера!
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


# --- ВЕБ-ИНТЕРФЕЙС STREAMLIT ---

st.set_page_config(page_title="Etymology Aggregator", page_icon="📜", layout="centered")

st.title("📜 Advanced Etymology Aggregator")
st.markdown("Поисковый инструмент для компьютерной лингвистики. Ищет данные по API, сайтам и локальным книгам.")

# Боковая панель для загрузки ваших книг
st.sidebar.header("📚 Ваши PDF Словари")
st.sidebar.info("Загрузите сюда ваши исторические словари (например, Chambers 1874), чтобы программа искала слова внутри них.")
uploaded_pdfs = st.sidebar.file_uploader("Перетащите PDF сюда", type=["pdf"], accept_multiple_files=True)

user_word = st.text_input("Enter a word to analyze:", placeholder="Например: knight, chivalry, pilgrim").strip().lower()

if st.button("Начать поиск", type="primary"):
    if user_word:
        with st.spinner(f"Ищем '{user_word}' по всем базам данных..."):
            
            # 1. Запуск ваших веб-функций
            wik_text, wik_link = get_wiktionary_data(user_word)
            etym_text, etym_link = get_etymonline_data(user_word)
            
            st.subheader("🏛️ Wiktionary API")
            st.write(wik_text)
            st.markdown(f"[Ссылка на источник]({wik_link})")
            
            st.divider()
            
            st.subheader("🕰️ Online Etymology Dictionary")
            st.write(etym_text)
            st.markdown(f"[Ссылка на источник]({etym_link})")
            
            # 2. Запуск вашей функции чтения PDF (если файлы загружены)
            if uploaded_pdfs:
                st.divider()
                st.subheader("📖 Поиск по локальным PDF")
                # Возвращаем файлы в начало (на случай повторного поиска)
                for f in uploaded_pdfs: f.seek(0) 
                
                pdf_text, pdf_source = get_pdf_data(user_word, uploaded_pdfs)
                st.write(pdf_text)
            else:
                st.info("💡 PDF-файлы не загружены. Поиск выполнен только по онлайн-источникам.")
    else:
        st.warning("Пожалуйста, введите слово для поиска.")
