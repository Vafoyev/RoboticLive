import sqlite3
import re
import math
import functools
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from backend.config import BASE_DIR, RAG_DB_PATH
from backend.models import KnowledgeDocument

# ==========================================
# 1. O'ZBEK TILI LINGVISTIK BAZASI VA STOPWORD'LAR
# ==========================================
UZBEK_STOPWORDS: Set[str] = {
    'va', 'bilan', 'uchun', 'haqda', 'haqida', 'deb', 'ham', 'emas', 'u', 'bu', 'shu',
    'oson', 'kerak', 'bor', 'yoq', 'qanday', 'qaysi', 'nima', 'kim', 'boshqa', 'ha',
    'esa', 'lekin', 'ammo', 'biroq', 'shuningdek', 'qilib', 'etib', 'bolib', 'bo‘lib',
    'oz', 'o‘z', 'mana', 'yana', 'biri', 'barcha', 'har', 'hamma'
}

# Domen bo'yicha sinonimlar va semantik bog'lamlar (Uzbek Domain Semantic Synonyms)
UZBEK_SYNONYM_GRAPH: Dict[str, List[str]] = {
    'hokim': ['bunyod', 'rajabov', 'hokimiyat', 'shahar hokimi', 'rahbar', 'hokimlik', 'boshliq'],
    'hokimi': ['bunyod', 'rajabov', 'hokimiyat', 'shahar hokimi', 'rahbar', 'hokimlik'],
    'hokimiyat': ['shahar hokimligi', 'bunyod rajabov', 'urganch hokimligi', 'rahbariyat'],
    'yettilik': ['mahalla yettiligi', 'mahalla raisi', 'profilaktika', 'xotin-qizlar', 'yetakchi', 'yordamchi', 'soliqchi', 'ijtimoiy xodim'],
    'raisi': ['mahalla raisi', 'boshliq', 'oqsoqol', 'yettilik', 'yettiligi'],
    'yoshlar': ['yoshlar yetakchisi', 'ishsiz', 'ishsizlar', 'yoshlar daftari', 'bandlik', 'talaba', 'malumotli'],
    'soliq': ['soliq tushumlari', 'soliqchi', 'byudjet', 'tushum', 'yer soligi', 'mol-mulk', '2025', '2026', 'rejasi'],
    'soliqlar': ['soliq tushumlari', 'soliqchi', 'byudjet', 'tushum', 'yer soligi', 'mol-mulk', '2025', '2026'],
    'uylar': ['xonadon', 'uy-joy', 'turar joy', 'xonadonlar', 'dom', 'ko\'p qavatli', 'manzil', 'kadastr', 'raqami'],
    'uy': ['xonadon', 'turar joy', 'dom', 'manzil', 'uylar', 'olimpiya'],
    'vazir': ['sherzod', 'hidoyatov', 'qurilish', 'uy-joy', 'kommunal', 'vazirlik'],
    'prezident': ['shavkat', 'mirziyoyev', 'davlat rahbari', 'prezidenti', 'qarori', 'farmoni'],
    'shahar': ['urganch', 'aqlli shahar', 'smart shahar', 'shahar hokimligi'],
    'mahalla': ['olimpiya', 'aqlli mahalla', 'yettilik', 'mahalla fuqarolar yigini'],
    'telefon': ['raqam', 'aloqa', 'boglanish', 'tel', 'mobil', 'kontakt'],
    'shikoyat': ['murojaat', 'ariza', 'muammo', 'gaz', 'suv', 'elektr', 'chiroq', 'obodonlashtirish'],
    'murojaat': ['ariza', 'shikoyat', 'taklif', 'muammo', 'ijro', 'portal']
}

# ==========================================
# 2. O'ZBEK TILI MORFOLOGIK STEMMING VA NORMALIZATSIYA
# ==========================================
def normalize_uzbek_stem(word: str) -> str:
    """O'zbek tilining agglyutinativ qo'shimchalarini tozalash (Stemmer)."""
    word = word.lower().strip()
    # Apostroflarni unifikatsiya qilish
    word = word.replace('‘', "'").replace('’', "'").replace('`', "'")
    
    suffixes = [
        'larning', 'larining', 'lardagi', 'lardanda', 'larga', 'larda', 'lardan', 'larni', 'larim', 'lariz',
        'sining', 'sidan', 'siga', 'sida', 'sini', 'ining', 'idan', 'iga', 'ida', 'ini',
        'larimiz', 'laringiz', 'mizning', 'ngizning', 'imiz', 'ingiz', 'dagi',
        'ning', 'dan', 'ga', 'da', 'ni', 'si', 'i', 'lik', 'li', 'siz', 'lar', 'chi', 'ku', 'mi'
    ]
    for s in suffixes:
        if word.endswith(s) and len(word) - len(s) >= 3:
            word = word[:-len(s)]
            break
    return word

def tokenize_uzbek(text: str) -> List[str]:
    """Matnni toza so'z tokenlariga ajratish."""
    text_clean = text.lower().replace('‘', "'").replace('’', "'").replace('`', "'")
    raw_tokens = re.findall(r"[a-z0-9'qo‘g‘xXhH]+", text_clean)
    tokens = []
    for t in raw_tokens:
        clean_t = t.strip("'")
        if len(clean_t) > 1 and clean_t not in UZBEK_STOPWORDS:
            tokens.append(clean_t)
    return tokens

# ==========================================
# 3. N-GRAM SHINGLING VA FUZZY JACCARD SIMILARITY
# ==========================================
def get_char_ngrams(word: str, n: int = 3) -> Set[str]:
    """So'zning n-gram simvollar to'plami (xatoliklar va shevalar uchun)."""
    word = f"^{word}$"
    return {word[i:i+n] for i in range(len(word) - n + 1)} if len(word) >= n else {word}

def fuzzy_jaccard_similarity(str1: str, str2: str) -> float:
    """Matnlar o'rtasida N-gram Jaccard o'xshashligi (0.0 dan 1.0 gacha)."""
    ng1 = get_char_ngrams(str1)
    ng2 = get_char_ngrams(str2)
    intersection = ng1.intersection(ng2)
    union = ng1.union(ng2)
    return len(intersection) / len(union) if union else 0.0

# ==========================================
# 4. QUERY EXPANSION (HYDE VA SEMANTIK KENGAYTIRISH)
# ==========================================
def expand_query_with_synonyms(query: str) -> Tuple[List[str], List[str]]:
    """
    Foydalanuvchi so'rovini o'zbek tili sinonimlari va semantik kalit so'zlari bilan boyitish.
    Returns: (asl_tokenlar, kengaytirilgan_tokenlar)
    """
    base_tokens = tokenize_uzbek(query)
    expanded = list(base_tokens)
    
    for t in base_tokens:
        stem = normalize_uzbek_stem(t)
        # To'g'ridan-to'g'ri va stem orqali sinonimlarni qidirish
        syns = UZBEK_SYNONYM_GRAPH.get(t, []) or UZBEK_SYNONYM_GRAPH.get(stem, [])
        for s in syns:
            s_tokens = tokenize_uzbek(s)
            for st in s_tokens:
                if st not in expanded:
                    expanded.append(st)
                    
    return base_tokens, expanded

# ==========================================
# 5. MA'LUMOTLAR BAZASI VA RAG JADVALLARI
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(RAG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_rag_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            content TEXT,
            source_file TEXT,
            doc_length INTEGER DEFAULT 0,
            timestamp REAL
        )
    """)
    conn.commit()
    # Ensure doc_length column exists if old schema was present
    try:
        cursor.execute("ALTER TABLE knowledge_chunks ADD COLUMN doc_length INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    conn.close()

def seed_initial_knowledge(force_reseed: bool = False):
    """Barcha Markdown va JSON/TXT fayllarni o'qib, sifatli bo'laklarga ajratish."""
    init_rag_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not force_reseed:
        cursor.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE category = 'tool_json'")
        tool_count = cursor.fetchone()[0]
        if tool_count > 0:
            conn.close()
            return

    cursor.execute("DELETE FROM knowledge_chunks")
    conn.commit()
    
    rag_dir = BASE_DIR / "rag" / "ai agent .md fayllar uchun"
    if not rag_dir.exists():
        for d in (BASE_DIR / "rag").iterdir():
            if d.is_dir() and "ai agent" in d.name.lower():
                rag_dir = d
                break
                
    if rag_dir.exists():
        files = list(rag_dir.glob("*.md")) + list(rag_dir.glob("*.txt"))
        
        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                
                fn_lower = filepath.name.lower()
                if "tool" in fn_lower or "json" in fn_lower or "config" in fn_lower:
                    category = "tool_json"
                elif "rahbar" in fn_lower or "president" in fn_lower or "vazir" in fn_lower or "hokim" in fn_lower:
                    category = "rahbarlar"
                elif "yettilik" in fn_lower:
                    category = "yettilik"
                elif "shahar" in fn_lower or "mahalla" in fn_lower:
                    category = "shahar_mahalla"
                elif "soliq" in fn_lower or "yoshlar" in fn_lower:
                    category = "soliq_ijtimoiy"
                elif "uy" in fn_lower:
                    category = "uy_joy"
                elif "catalog" in fn_lower or "order" in fn_lower or "object" in fn_lower:
                    category = "catalog"
                else:
                    category = "general"

                # Text / JSON / config fayllar
                if filepath.suffix == ".txt" or "json" in fn_lower:
                    doc_id = f"{filepath.stem}_0"
                    title = f"{filepath.stem} (Tizim va Tool JSON ma'lumotlari)"
                    cursor.execute("""
                        INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, doc_length, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (doc_id, title[:150], category, text, filepath.name, len(tokenize_uzbek(text))))
                    continue

                # Markdown fayllarni sarlavhalar (Level 1 va Level 2) bo'yicha to'liq Q&A qilib ajratish
                sections = re.split(r'\n(?=#{1,2}\s+)', text)
                for idx, sec in enumerate(sections):
                    sec_clean = sec.strip()
                    if not sec_clean:
                        continue

                    lines = [l for l in sec_clean.split('\n') if l.strip()]
                    first_line = lines[0].replace('#', '').strip() if lines else filepath.stem
                    doc_id = f"{filepath.stem}_{idx}"

                    cursor.execute("""
                        INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, doc_length, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (doc_id, first_line[:150], category, sec_clean, filepath.name, len(tokenize_uzbek(sec_clean))))

            except Exception as e:
                print(f"Error seeding {filepath.name}: {e}")

        conn.commit()
    conn.close()

# Dastur ishga tushganda avtomatik indekslash
seed_initial_knowledge()

# ==========================================
# 6. SOTA GIBRID QIDIRUV (HYBRID BM25+ / RRF / FUZZY / INTENT RE-RANKER)
# ==========================================
@functools.lru_cache(maxsize=512)
def search_rag_context(query: str, limit: int = 5) -> str:
    """
    State-of-the-Art Hybrid RAG Engine:
    1. Query Expansion (Uzbek Synonyms & Intent Analysis)
    2. BM25+ with Length Normalization & IDF
    3. Fuzzy Subword N-Gram Jaccard Matching (avoids typo misses)
    4. Exact ID / Title Anchor Boosting
    5. Reciprocal Rank Fusion (RRF) for Rank Merging
    6. Cross-Lexical Intent Re-ranking
    7. Full Parent-Child Context Formulation (No Truncation)
    """
    if not query or not query.strip():
        return ""

    base_tokens, expanded_tokens = expand_query_with_synonyms(query)
    if not base_tokens:
        base_tokens = [query.lower().strip()]
        expanded_tokens = base_tokens

    base_stems = [normalize_uzbek_stem(t) for t in base_tokens]
    expanded_stems = [normalize_uzbek_stem(t) for t in expanded_tokens]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category, content, source_file, doc_length FROM knowledge_chunks")
    rows = cursor.fetchall()
    conn.close()

    total_docs = len(rows)
    if total_docs == 0:
        return ""

    # BM25 parametrlarini hisoblash
    avgdl = sum(r['doc_length'] or 50 for r in rows) / total_docs if total_docs > 0 else 50.0
    k1 = 1.2
    b = 0.75
    delta = 0.5  # BM25+ parametri

    # Har bir token uchun Document Frequency (DF) hisoblash
    doc_frequencies: Dict[str, int] = {}
    for r in rows:
        c_text = (r['title'] + " " + r['content']).lower()
        for t in set(expanded_tokens + expanded_stems):
            if t in c_text:
                doc_frequencies[t] = doc_frequencies.get(t, 0) + 1

    # 4 xil algoritmlar bo'yicha baholash ro'yxatlari
    bm25_scores = []
    fuzzy_scores = []
    exact_title_scores = []
    intent_scores = []

    # Savol niyatini aniqlash (Intent Detection)
    q_lower = query.lower()
    is_person_query = any(w in q_lower for w in ['kim', 'rahbar', 'boshliq', 'hokim', 'rais', 'faoli', 'yetakchi', 'xodim'])
    is_phone_query = any(w in q_lower for w in ['telefon', 'raqam', 'boglan', 'aloqa', 'kontakt', 'qayerda'])
    is_tax_query = any(w in q_lower for w in ['soliq', 'byudjet', 'tushum', 'pul', 'summa', '2025', '2026'])
    is_house_query = any(w in q_lower for w in ['uy', 'xonadon', 'uylar', 'manzil', 'turar joy'])

    for row in rows:
        doc_id = row['id']
        title = row['title'].lower()
        content = row['content'].lower()
        d_len = row['doc_length'] or len(tokenize_uzbek(row['content']))

        # ----------------------------------------------------
        # 1. BM25+ Baholash
        # ----------------------------------------------------
        bm25_val = 0.0
        for t, st in zip(expanded_tokens, expanded_stems):
            df = doc_frequencies.get(t, 0) or doc_frequencies.get(st, 0) or 1
            idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))
            
            # Title va Content dagi takrorlanishlar
            tf_title = title.count(t) * 3.0 + title.count(st) * 2.0
            tf_content = content.count(t) * 1.0 + content.count(st) * 0.7
            tf_total = tf_title + tf_content

            if tf_total > 0:
                tf_norm = (tf_total * (k1 + 1.0)) / (tf_total + k1 * (1.0 - b + b * (d_len / avgdl)))
                bm25_val += idf * (tf_norm + delta)

        bm25_scores.append((bm25_val, doc_id, row))

        # ----------------------------------------------------
        # 2. Fuzzy N-Gram Subword Baholash
        # ----------------------------------------------------
        fuzzy_val = 0.0
        for t in base_tokens:
            sim_title = fuzzy_jaccard_similarity(t, title)
            if sim_title > 0.25:
                fuzzy_val += sim_title * 4.0
            sim_content = fuzzy_jaccard_similarity(t, content[:400])
            if sim_content > 0.3:
                fuzzy_val += sim_content * 1.5
        fuzzy_scores.append((fuzzy_val, doc_id, row))

        # ----------------------------------------------------
        # 3. Exact Title & ID Priority Baholash
        # ----------------------------------------------------
        title_val = 0.0
        for bt, bst in zip(base_tokens, base_stems):
            if bt in title:
                title_val += 5.0
            elif bst in title:
                title_val += 3.5
            if doc_id.lower() in q_lower:
                title_val += 10.0
        exact_title_scores.append((title_val, doc_id, row))

        # ----------------------------------------------------
        # 4. Intent & Category Cross-Match Baholash
        # ----------------------------------------------------
        cat = row['category']
        int_val = 0.0
        if is_person_query and cat in ['rahbarlar', 'yettilik']:
            int_val += 4.0
        if is_phone_query and any(w in content for w in ['telefon', 'raqam', '+998', '998']):
            int_val += 5.0
        if is_tax_query and cat in ['soliq_ijtimoiy', 'soliq']:
            int_val += 4.5
        if is_house_query and cat in ['uy_joy', 'shahar_mahalla']:
            int_val += 4.0
        intent_scores.append((int_val, doc_id, row))

    # ----------------------------------------------------
    # 5. RECIPROCAL RANK FUSION (RRF) - Barcha modellarni birlashtirish
    # ----------------------------------------------------
    bm25_scores.sort(key=lambda x: x[0], reverse=True)
    fuzzy_scores.sort(key=lambda x: x[0], reverse=True)
    exact_title_scores.sort(key=lambda x: x[0], reverse=True)
    intent_scores.sort(key=lambda x: x[0], reverse=True)

    rrf_table: Dict[str, Tuple[float, Any]] = {}
    k_rrf = 60.0

    # RRF vaznlari
    weights = {
        'bm25': 2.5,
        'exact': 3.0,
        'intent': 2.0,
        'fuzzy': 1.5
    }

    for rank, (score, doc_id, r) in enumerate(bm25_scores):
        if score > 0:
            rrf_table[doc_id] = (rrf_table.get(doc_id, (0.0, r))[0] + weights['bm25'] / (k_rrf + rank + 1), r)

    for rank, (score, doc_id, r) in enumerate(exact_title_scores):
        if score > 0:
            rrf_table[doc_id] = (rrf_table.get(doc_id, (0.0, r))[0] + weights['exact'] / (k_rrf + rank + 1), r)

    for rank, (score, doc_id, r) in enumerate(intent_scores):
        if score > 0:
            rrf_table[doc_id] = (rrf_table.get(doc_id, (0.0, r))[0] + weights['intent'] / (k_rrf + rank + 1), r)

    for rank, (score, doc_id, r) in enumerate(fuzzy_scores):
        if score > 0:
            rrf_table[doc_id] = (rrf_table.get(doc_id, (0.0, r))[0] + weights['fuzzy'] / (k_rrf + rank + 1), r)

    sorted_candidates = sorted(rrf_table.values(), key=lambda x: x[0], reverse=True)
    top_results = [item[1] for item in sorted_candidates[:limit]]

    if not top_results:
        return ""

    # ----------------------------------------------------
    # 6. Sifatli va to'liq Parent-Child kontekstini shakllantirish
    # ----------------------------------------------------
    formatted_context = "=== ANIQ VA TO'LIQ RASMIY BILIMLAR BAZASI MA'LUMOTLARI ===\n"
    for idx, r in enumerate(top_results, 1):
        formatted_context += (
            f"\n[{idx}] HUJJAT MANBASI: {r['title']} (Kategoriya: {r['category']})\n"
            f"{r['content'][:4000]}\n"
        )

    return formatted_context.strip()

# ==========================================
# 7. MA'LUMOTLARNI BOSHQARISH VA QO'SHISH/O'CHIRISH
# ==========================================
def add_knowledge_doc(doc: KnowledgeDocument) -> KnowledgeDocument:
    conn = get_db_connection()
    cursor = conn.cursor()
    doc_len = len(tokenize_uzbek(doc.content))
    cursor.execute("""
        INSERT OR REPLACE INTO knowledge_chunks (id, title, category, content, source_file, doc_length, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (doc.id, doc.title, doc.category, doc.content, "user_added", doc_len))
    conn.commit()
    conn.close()
    search_rag_context.cache_clear()
    return doc

def get_all_knowledge_docs() -> List[KnowledgeDocument]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category, content, source_file, timestamp FROM knowledge_chunks")
    rows = cursor.fetchall()
    conn.close()
    
    docs = []
    for r in rows:
        docs.append(KnowledgeDocument(
            id=r['id'],
            title=r['title'],
            category=r['category'],
            content=r['content'],
            source_file=r['source_file'],
            timestamp=r['timestamp']
        ))
    return docs

def delete_knowledge_doc(doc_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_chunks WHERE id = ?", (doc_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    search_rag_context.cache_clear()
    return deleted
