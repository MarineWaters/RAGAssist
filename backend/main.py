import os
import tempfile
from io import BytesIO
from llama_index.core import Settings, Document
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import SimpleDirectoryReader
import qdrant_client
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

current_chunk_settings = {
    "chunk_size": 512,
    "chunk_overlap": 50
}


def add_pdf_to_index(pdf_bytes: bytes, filename: str, chunk_size: int = None, chunk_overlap: int = None):
    global index, current_chunk_settings
    
    if chunk_size is None:
        chunk_size = current_chunk_settings["chunk_size"]
    if chunk_overlap is None:
        chunk_overlap = current_chunk_settings["chunk_overlap"]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / filename
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)
        
        print(f"📖 Загрузка PDF: {filename}")
        documents = SimpleDirectoryReader(input_files=[str(filepath)]).load_data()
        print(f"📄 Загружено {len(documents)} чанков документа из {filename}")
        
        print(f"⚙️ Применение настроек чанков: размер={chunk_size}, перекрытие={chunk_overlap}")
        
        parser = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        
        index = VectorStoreIndex.from_documents(
            documents,
            transformations=[parser],
            storage_context=storage_context,
            embed_model=Settings.embed_model
        )
        
        print(f"✅ Успешно добавлено документов в Qdrant")
        return len(documents)

def query_index(question: str):
    if not index:
        raise ValueError("Индекс не инициализирован")
    
    print(f"🔍 Запрос: {question}")
    query_engine = index.as_query_engine()
    response = query_engine.query(question)
    return str(response)

def get_index_stats():
    try:
        collection_info = client.get_collection(collection_name=COLLECTION_NAME)
        points_count = collection_info.points_count
        return {
            "points_count": points_count,
            "collection_name": COLLECTION_NAME,
            "status": "работает"
        }
    except Exception as e:
        return {"error": str(e), "status": "недоступно"}

def update_chunk_settings(chunk_size: int, chunk_overlap: int):
    global current_chunk_settings
    current_chunk_settings.update({
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap
    })
    
    print(f"⚙️ Настройки чанков обновлены: размер={chunk_size}, перекрытие={chunk_overlap}")
    
    return {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap
    }

def get_current_chunk_settings():
    return current_chunk_settings