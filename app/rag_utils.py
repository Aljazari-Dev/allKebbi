# rag_utils.py
import os
import re
from types import SimpleNamespace

import numpy as np
from docx import Document
from sentence_transformers import SentenceTransformer
from urllib.parse import unquote_plus

from app.config import SUBJECT_RAG_DIR, RAG_MODEL_NAME, RAG_TOP_K
from app.ai_utils import openai_chat_completion

# cache in-memory: key -> {"paragraphs": [...], "embeddings": np.ndarray}
SUBJECT_RAG_CACHE = {}

RAG_SYSTEM_PROMPT = """
أنت روبوت معلم مواد علمية (مثل الأحياء والكيمياء) لطلبة الصف الأول المتوسط في العراق.
سيتم تزويدك بمقاطع من كتاب مدرسي وسؤال طالب.

دورك أن تتصرّف مثل أستاذ في الصف يشرح للطالب، لكن:
- كل ما تقوله يجب أن يكون مبنياً حصراً على المعلومات الموجودة في المقاطع.
- لا يُسمح لك باختراع حقائق جديدة أو جلب معلومات من خارج النصوص المزوَّدة.

القواعد المهمة:
1- ابحث في المقاطع عن الجملة أو الفقرة التي تجيب على السؤال بشكل مباشر.
2- حرّر الجواب بأسلوب معلم يشرح لطلابه:
   - استعمل جملاً واضحة وقصيرة.
   - يمكنك تبسيط اللغة أو إعادة ترتيب الجمل.
   - يمكنك الدمج بين جمل متفرقة من النص ما دام المعنى نفسه.
3- تجنّب الاقتباس الحرفي الطويل من الكتاب؛ إن احتجت اقتباساً حرفياً فليكن قصيراً (تعريف أو جملة واحدة).
4- لا تعِد كتابة السؤال في الجواب، ولا تذكر رقم الفقرة أو اسم الكتاب أو أي تفاصيل تقنية.
5- إذا لم يكن الجواب واضحاً في النص، قل حرفياً:
"لا أستطيع إيجاد جواب مطابق لهذا السؤال في الكتاب."
6- أجب بالعربية الفصحى المبسطة، وبإيجاز (من 2 إلى 5 جمل)، وكأنك تشرح لطلبة الصف الأول المتوسط.
"""

print("🔧 Loading RAG embedding model...")
try:
    RAG_EMBED_MODEL = SentenceTransformer(RAG_MODEL_NAME)
except Exception as e:
    print("⚠️ RAG feature disabled (embedding model load error):", e)
    RAG_EMBED_MODEL = None


def subject_rag_key(stage, section, subject):
    return f"{stage}|||{section}|||{subject}"


def subject_book_paths(stage, section, subject):
    safe_stage = re.sub(r"[^A-Za-z0-9]+", "_", stage)
    safe_section = re.sub(r"[^A-Za-z0-9]+", "_", section)
    safe_subject = re.sub(r"[^A-Za-z0-9]+", "_", subject)
    base = f"{safe_stage}_{safe_section}_{safe_subject}".strip("_")
    docx_path = os.path.join(SUBJECT_RAG_DIR, base + ".docx")
    cleaned_path = os.path.join(SUBJECT_RAG_DIR, base + "_cleaned.txt")
    return docx_path, cleaned_path


def subject_book_exists(stage, section, subject):
    docx_path, _ = subject_book_paths(stage, section, subject)
    return os.path.exists(docx_path)


def rag_embed_texts(texts, is_query=False):
    if RAG_EMBED_MODEL is None:
        raise RuntimeError("RAG embedding model is not available on this server.")
    prefix = "query: " if is_query else "passage: "
    return RAG_EMBED_MODEL.encode(
        [prefix + t for t in texts],
        normalize_embeddings=True
    )


def load_subject_book_into_memory(stage, section, subject):
    """
    تحميل كتاب المادة (Word) لهذه المادة إلى الذاكرة وبناء الفقرات + embeddings.
    """
    key = subject_rag_key(stage, section, subject)
    docx_path, cleaned_path = subject_book_paths(stage, section, subject)
    if not os.path.exists(docx_path):
        return False, "لم يتم رفع أي كتاب لهذه المادة حتى الآن."

    if os.path.exists(cleaned_path):
        with open(cleaned_path, "r", encoding="utf-8") as f:
            book_text = f.read()
    else:
        print(f"📖 قراءة ملف Word للمادة {stage}/{section}/{subject}: {docx_path}")
        doc = Document(docx_path)
        text = "\n".join(p.text for p in doc.paragraphs)

        text = re.sub(r"[ـ]+", "", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"اال", "ال", text)
        text = re.sub(r"\s*([،؛:.؟])\s*", r"\1 ", text)
        text = re.sub(r"(?<![\.\؟!])\n+", ". ", text)
        text = text.strip()

        sentences = re.split(r"(?<=[\.؟!])\s+", text)
        paragraphs = []
        temp = []
        for s in sentences:
            if not s.strip():
                continue
            temp.append(s.strip())
            if len(temp) >= 3:
                paragraphs.append(" ".join(temp))
                temp = []
        if temp:
            paragraphs.append(" ".join(temp))

        cover = f"{stage} / {section} / {subject}\n\n"
        book_text = cover + "\n\n".join(paragraphs)

        with open(cleaned_path, "w", encoding="utf-8") as f:
            f.write(book_text)

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", book_text) if p.strip()]
    if not paragraphs:
        return False, "الكتاب فارغ بعد التنظيف، تحقق من الملف."

    try:
        para_embeddings = rag_embed_texts(paragraphs, is_query=False).astype("float32")
    except Exception as e:
        return False, f"خطأ في حساب الـ embeddings: {e}"

    SUBJECT_RAG_CACHE[key] = {
        "paragraphs": paragraphs,
        "embeddings": para_embeddings,
    }
    print(f"📘 RAG book loaded for {stage}/{section}/{subject}: {len(paragraphs)} فقرة.")
    return True, None


def retrieve_top_k_for_subject(question, stage, section, subject, k=RAG_TOP_K):
    key = subject_rag_key(stage, section, subject)
    if key not in SUBJECT_RAG_CACHE:
        ok, err = load_subject_book_into_memory(stage, section, subject)
        if not ok:
            return [], err
    data = SUBJECT_RAG_CACHE[key]
    paragraphs = data["paragraphs"]
    embeddings = data["embeddings"]
    q_emb = rag_embed_texts([question], is_query=True)[0].astype("float32")
    scores = np.dot(embeddings, q_emb)
    idx = np.argsort(-scores)[:k]
    results = [(int(i), float(scores[i]), paragraphs[i]) for i in idx]
    return results, None


def subject_rag_answer(question, stage, section, subject):
    """
    استدعاء GPT للإجابة على سؤال من كتاب المادة المحدد فقط.
    """
    retrieved, err = retrieve_top_k_for_subject(question, stage, section, subject, k=RAG_TOP_K)
    if err:
        return None, [], err

    context_blocks = []
    for idx, score, text in retrieved:
        context_blocks.append(f"[فقرة {idx}] {text}")
    context_str = "\n\n".join(context_blocks)

    prompt = f"""
السؤال من الطالب:
{question}

المقاطع المتاحة من الكتاب (هذه للمرجع فقط، لا تعِد إرسالها للطالب كما هي):
{context_str}

أعطِ جوابك النهائي للطالب بأسلوب معلم يشرح الدرس، ملتزماً بالقواعد في رسالة النظام.
"""

    answer, api_err = None, None
    try:
        answer, api_err = openai_chat_completion(RAG_SYSTEM_PROMPT, prompt)
    except Exception as e:
        api_err = str(e)

    if api_err:
        return None, retrieved, api_err
    return (answer or "").strip(), retrieved, None


def save_uploaded_book(file_storage, stage, section, subject):
    """
    تستعمل في صفحة الويب لرفع / استبدال كتاب المادة.
    """
    docx_path, cleaned_path = subject_book_paths(stage, section, subject)
    os.makedirs(os.path.dirname(docx_path), exist_ok=True)
    file_storage.save(docx_path)
    if os.path.exists(cleaned_path):
        os.remove(cleaned_path)
    key = subject_rag_key(stage, section, subject)
    if key in SUBJECT_RAG_CACHE:
        del SUBJECT_RAG_CACHE[key]
    ok, err = load_subject_book_into_memory(stage, section, subject)
    return ok, err


def run_book_rag(stage, section, subject, question, lang="ar-SA"):
    """
    دالة وسيطة تشغّل RAG على كتاب المادة المحددة فقط.
    ترجع نصّ الجواب الجاهز للطالب.
    """
    stage = unquote_plus(stage)
    section = unquote_plus(section)
    subject = unquote_plus(subject)

    question = (question or "").strip()
    if not question:
        return "لم أفهم سؤالك، حاول أن تكتب السؤال مرة أخرى بشكل أوضح."

    if not subject_book_exists(stage, section, subject):
        return "لم يتم رفع كتاب لهذه المادة بعد."

    answer, retrieved, err = subject_rag_answer(question, stage, section, subject)
    if err:
        print("RAG error:", err)
        return "حدث خطأ في خادم الذكاء الاصطناعي أثناء قراءة الكتاب، حاول مرة أخرى لاحقاً."

    if not (answer or "").strip():
        return "لا أستطيع إيجاد جواب واضح لهذا السؤال داخل الكتاب."

    return (answer or "").strip()


def wrap_contexts(retrieved):
    return [
        SimpleNamespace(index=idx, score=score, text=text)
        for idx, score, text in retrieved
    ]
