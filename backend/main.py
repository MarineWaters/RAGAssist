import tempfile
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader, Settings, SimpleKeywordTableIndex, PromptTemplate
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.indices.query.query_transform.base import HyDEQueryTransform
from llama_index.core.tools import QueryEngineTool
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMMultiSelector
from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core.query_engine import TransformQueryEngine
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

Settings.llm =Ollama(base_url=OLLAMA_BASE_URL, model=MODEL_NAME)
Settings.embed_model = HuggingFaceEmbedding(model_name="intfloat/multilingual-e5-base")
print("✅ Настройки LlamaIndex сконфигурированы")

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "session_documents"

client = qdrant_client.QdrantClient(url=QDRANT_URL)
    
vector_store = QdrantVectorStore(
    client=client, 
    collection_name=COLLECTION_NAME,
    enable_hybrid=True 
)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex([], storage_context=storage_context, embed_model=Settings.embed_model)
keyword_index = SimpleKeywordTableIndex([], storage_context=storage_context, llm=Settings.llm)

print("✅ Новый Qdrant индекс инициализирован")

uploaded_filenames = []

def get_unique_filenames_from_qdrant():
    try:
        all_points = []
        next_page = None
        while True:
            response = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=None,
                limit=1000,
                offset=next_page,
                with_payload=True
            )
            all_points.extend(response[0])
            next_page = response[1]
            if next_page is None:
                break
        unique_names = set()
        for point in all_points:
            if 'file_name' in point.payload:
                unique_names.add(point.payload.get('file_name'))
        return list(unique_names)
    except Exception as e:
        print(f"❌ Невозможно получить список файлов в Qdrant: {e}")
        return []
    
uploaded_filenames = get_unique_filenames_from_qdrant()

def add_document_to_index(doc_bytes: bytes, filename: str):
    global index, storage_context, keyword_index
    file_size = len(doc_bytes)
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
            f.write(doc_bytes)
        print(f"📖 Загрузка документа: {safe_filename}")
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
        storage_context.docstore.add_documents(nodes) #new
        for node in nodes:
            if not hasattr(node, 'metadata') or node.metadata is None:
                node.metadata = {}
        if index is None:
            index = VectorStoreIndex(
                nodes,
                storage_context=storage_context,
                embed_model=Settings.embed_model)
        else:
            index.insert_nodes(nodes)
        if keyword_index is None:
            keyword_index = SimpleKeywordTableIndex(
                nodes, 
                storage_context=storage_context, 
                llm=Settings.llm)
        else:
            keyword_index.insert_nodes(nodes)
        uploaded_filenames.append(safe_filename)
        print(f"✅ Успешно добавлено {len(nodes)} чанков в Qdrant для файла {safe_filename}")
        return len(nodes)

def query(question: str):
    if not uploaded_filenames:
        raise ValueError("Файлы еще не загружены. Пожалуйста, загрузите файлы перед запросами.")
    if not question.strip():
        raise ValueError("Вопрос не может быть пустым")
    print(f"🔍 Обработка запроса: {question}")
    try:
        QA_PROMPT = PromptTemplate(
            "Context information is below.\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Given the context information and not prior knowledge, "
            "answer the question comprehensively but shortly. If the answer is not in the context, inform "
            "the user that you can't answer the question - DO NOT MAKE UP AN ANSWER.\n"
            "Answer in russian.\n"
            "Question: {query_str}\n"
            "Answer: "
        )
        vector_query_engine = index.as_query_engine(
            response_mode="compact",
            similarity_top_k=7,
            text_qa_template=QA_PROMPT
        )
        keyword_query_engine = keyword_index.as_query_engine(
            text_qa_template=QA_PROMPT,
            response_mode="compact",
            similarity_top_k=7,
        )
        hyde_query_engine = TransformQueryEngine(vector_query_engine, HyDEQueryTransform(include_original=True))
        keyword_tool = QueryEngineTool.from_defaults(
            query_engine=keyword_query_engine,
            description="Useful for answering questions about this document. Searches matches by keywords.",
        )
        vector_tool = QueryEngineTool.from_defaults(
            query_engine=vector_query_engine,
            description="Useful for answering questions about this document. Semantic search with embeddings.",
        )
        hyde_tool = QueryEngineTool.from_defaults(
            query_engine=hyde_query_engine,
            description="Useful for answering questions about this document. Search by matching to assumed answer.",
        )
        tree_summarize = TreeSummarize(
            summary_template=PromptTemplate(
                "Context information from multiple sources is below. "
                "\n---------------------\n{context_str}\n---------------------\nGiven"
                " the information from multiple sources"
                " and not prior knowledge, answer the question comprehensively. If"
                " the answer is not in the context, inform the user that you can't answer"
                " the question. Answer in russian. Provide compact answer. All formatting should be removed. Prefer actual answers to undecided ones. "
                "\nQuestion: {query_str}\nAnswer: "
            )
        )
        query_engine = RouterQueryEngine(
            selector=LLMMultiSelector.from_defaults(),
            query_engine_tools=[
                keyword_tool,
                vector_tool,
                hyde_tool
            ],
            summarizer=tree_summarize,
        )
        response = query_engine.query(question)
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
                            key="file_name",
                            match=models.MatchValue(value=filename))])))
        print(f"✅ Удалены все векторы для файла: {filename}")
        return True
    except Exception as e:
        print(f"❌ Ошибка удаления файла {filename} из Qdrant: {e}")
        return False
    
def delete_all_files_from_index():
    global index, storage_context, vector_store, keyword_index
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            enable_hybrid=True
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex([], storage_context=storage_context, embed_model=Settings.embed_model)
        keyword_index = SimpleKeywordTableIndex([], storage_context=storage_context, llm=Settings.llm)
        uploaded_filenames.clear()
        print("✅ Все файлы удалены из Qdrant, коллекция пересоздана")
        return True
    except Exception as e:
        print(f"❌ Ошибка полной очистки Qdrant: {e}")
        return False