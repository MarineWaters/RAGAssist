import tempfile
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
import qdrant_client
from qdrant_client import models
import requests
from ollama_getter import ollama_url
from pathlib import Path

OLLAMA_BASE_URL = ollama_url.rstrip('/')
MODEL_NAME = "gpt-oss:20b"

print(f"🔗 Проверка подключения к: {OLLAMA_BASE_URL}")
try:
    response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=30)
    if response.status_code == 200:
        print("✅ Успешное подключение к Ollama")
        models_data = response.json()
        if 'models' in models_data:
            available_models = [model['name'] for model in models_data['models']]
            if MODEL_NAME not in available_models:
                print(f"⚠️ Модель '{MODEL_NAME}' не найдена. Используется: {available_models[0]}")
                MODEL_NAME = available_models[0]
    else:
        print(f"❌ Ошибка Ollama: {response.status_code}")
        exit(1)
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    exit(1)

Settings.llm = Ollama(base_url=OLLAMA_BASE_URL, model=MODEL_NAME, request_timeout=60.0)
Settings.embed_model = HuggingFaceEmbedding(model_name="intfloat/multilingual-e5-base")
print("✅ Настройки LlamaIndex сконфигурированы")

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "session_documents"

client = qdrant_client.QdrantClient(url=QDRANT_URL)
try:
    client.delete_collection(collection_name=COLLECTION_NAME)
    print("🧹 Существующая Qdrant коллекция очищена")
except Exception as e:
    print(f"ℹ️ Нет существующей коллекции для очистки: {e}")
    
vector_store = QdrantVectorStore(
    client=client, 
    collection_name=COLLECTION_NAME,
    enable_hybrid=True 
)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex([], storage_context=storage_context, embed_model=Settings.embed_model)
print("✅ Новый Qdrant индекс инициализирован (пустой)")

uploaded_filenames = []
uploaded_documents = []

def add_pdf_to_index(pdf_bytes: bytes, filename: str):
    global index, storage_context
    file_size = len(pdf_bytes)
    if file_size > 1048576: #1MB
        chunk_size = 2048
        chunk_overlap = 200
    elif file_size > 524288: #512KB
        chunk_size = 1024
        chunk_overlap = 100
    else:
        chunk_size = 512
        chunk_overlap = 50
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_filename = filename.encode('utf-8', errors='ignore').decode('utf-8')
        filepath = Path(tmpdir) / safe_filename
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)
        print(f"📖 Загрузка PDF: {safe_filename}")
        documents = SimpleDirectoryReader(
            input_files=[str(filepath)]
        ).load_data()
        print(f"📄 Загружено {len(documents)} документов из {safe_filename}")
        print(f"⚙️ Применение настроек чанков: размер={chunk_size}, перекрытие={chunk_overlap}")
        parser = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        nodes = parser.get_nodes_from_documents(documents)
        for node in nodes:
            if not hasattr(node, 'metadata') or node.metadata is None:
                node.metadata = {}
            node.metadata['file_name'] = safe_filename
        if index is None:
            index = VectorStoreIndex(
                nodes,
                storage_context=storage_context,
                embed_model=Settings.embed_model)
        else:
            index.insert_nodes(nodes)
        uploaded_filenames.append(safe_filename)
        uploaded_documents.extend(documents)
        print(f"✅ Успешно добавлено {len(nodes)} чанков в Qdrant для файла {safe_filename}")
        return len(nodes)

def query(question: str):
    if not uploaded_filenames:
        raise ValueError("PDF файлы еще не загружены. Пожалуйста, загрузите PDF файлы перед запросами.")
    if not question.strip():
        raise ValueError("Вопрос не может быть пустым")
    print(f"🔍 Обработка запроса: {question}")
    try:
        query_engine = index.as_query_engine(
            response_mode="compact",
            similarity_top_k=5
        )
        enhanced_question = (
            "Ответь на вопрос, используя ТОЛЬКО информацию из загруженных документов. "
            "Если точный ответ не содержится в документах, напиши: "
            "'Информация по этому вопросу отсутствует в документах.'\n\n"
            f"Вопрос: {question}"
        )
        response = query_engine.query(enhanced_question)
        answer = str(response).strip()
        if not answer or "empty response" in answer.lower() or len(answer) < 5:
            answer = "Информация по этому вопросу отсутствует в документах."
        print(f"✅ Ответ получен")
        return answer
    except Exception as e:
        print(f"❌ Ошибка при обработке запроса: {e}")
        raise Exception(f"Ошибка при обработке запроса: {str(e)}")

def delete_file_from_index(filename: str):
    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.file_name",
                            match=models.MatchValue(value=filename))])))
        print(f"✅ Удалены все векторы для файла: {filename}")
        return True
    except Exception as e:
        print(f"❌ Ошибка удаления файла {filename} из Qdrant: {e}")
        return False
    
def delete_all_files_from_index():
    global index, storage_context, vector_store
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        vector_store = QdrantVectorStore(
            client=client, 
            collection_name=COLLECTION_NAME,
            enable_hybrid=True 
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex([], storage_context=storage_context, embed_model=Settings.embed_model)
        uploaded_documents.clear()
        print("✅ Все файлы удалены из Qdrant, коллекция пересоздана")
        return True
    except Exception as e:
        print(f"❌ Ошибка полной очистки Qdrant: {e}")
        return False