from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import (
    add_document_to_index, query, delete_file_from_index, delete_all_files_from_index, uploaded_filenames, get_unique_filenames_from_qdrant, Settings)
from evaluator import run_evaluation
from llama_index.core import SimpleDirectoryReader, Document
import tempfile
from pathlib import Path
import qdrant_client
from collections import defaultdict

app = FastAPI()
origins = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    mode: str = "vector"

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    allowed_extensions = ['.pdf', '.docx', '.doc', '.odt']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Разрешены только файлы: {', '.join(allowed_extensions)}")
    if file.filename in uploaded_filenames:
        raise HTTPException(status_code=400, detail="Файл с таким именем уже существует")
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Загружен пустой файл")
    try:
        chunks_added = add_document_to_index(contents, file.filename)
        response_data = {
            "message": f"'{file.filename}' успешно обработан",
            "filename": file.filename,
            "chunks_added": chunks_added
        }
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")

@app.get("/files")
async def list_files():
    try:
        uploaded_filenames = get_unique_filenames_from_qdrant()
        return {"files": [{"filename": name} for name in uploaded_filenames]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving files: {str(e)}")

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    if filename in uploaded_filenames:
        success = delete_file_from_index(filename) 
        if not success:
            raise HTTPException(status_code=500, detail=f"Не удалось удалить файл '{filename}' из векторной базы")
        uploaded_filenames.remove(filename)
        return {"message": f"'{filename}' полностью удален из системы"}
    else:
        raise HTTPException(status_code=404, detail="Файл не найден в сессии")

@app.delete("/files")
async def delete_all_files():
    try:
        success = delete_all_files_from_index()
        if not success:
            raise HTTPException(status_code=500, detail="Не удалось очистить векторную базу")
        uploaded_filenames.clear()
        return {"message": "Все файлы полностью удалены из системы"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления всех файлов: {str(e)}")

@app.post("/query")
async def ask_question(request: QueryRequest):
    if not uploaded_filenames:
        raise HTTPException(status_code=400, detail="Документы еще не загружены. Пожалуйста, загрузите документы перед запросами.")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")
    try:
        answer = await query(request.question, request.mode)
        return {
            "answer": answer,
            "files_used": uploaded_filenames
        }
    except Exception as e:
        print(f"❌ Ошибка в API запросе: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")

@app.post("/evaluate")
async def evaluate_ragas():
    if not uploaded_filenames:
        raise HTTPException(status_code=400, detail="Документы еще не загружены. Пожалуйста, загрузите документы перед оценкой.")
    try:
        documents = []
        client = qdrant_client.QdrantClient(url="http://localhost:6333")
        all_points = []
        next_page = None
        while True:
            response = client.scroll(
                collection_name="session_documents",
                scroll_filter=None,
                limit=1000,
                offset=next_page,
                with_payload=True,
                with_vectors=False
            )
            all_points.extend(response[0])
            next_page = response[1]
            if next_page is None:
                break
        file_texts = defaultdict(str)
        for point in all_points:
            filename = point.payload.get('file_name', '')
            text = point.payload.get('text', '')
            file_texts[filename] += text + " "
        for filename, text in file_texts.items():
            documents.append(Document(text=text.strip(), metadata={"filename": filename}))

        if not documents:
            raise HTTPException(status_code=400, detail="Не удалось извлечь документы для оценки")
        results = await run_evaluation(
            llm_model=Settings.llm,
            llm_embed_model=Settings.embed_model,
            documents=documents,
            testset_size=5
        )
        return {
            "message": "Оценка с Ragas завершена",
            "results": results
        }
    except Exception as e:
        print(f"❌ Ошибка оценки Ragas: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка оценки системы: {str(e)}")
