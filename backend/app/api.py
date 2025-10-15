from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from main import add_pdf_to_index, query_index, index, get_index_stats, update_chunk_settings

app = FastAPI(title="PDF RAG API", version="1.0.0")

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

uploaded_filenames = []

chunk_settings = {
    "chunk_size": 512,
    "chunk_overlap": 50
}

@app.on_event("startup")
async def startup_event():
    print("🚀 Запуск новой сессии с пустым Qdrant индексом")

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(50)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Разрешены только PDF файлы")
    
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Загружен пустой файл")
    
    if chunk_size < 100 or chunk_size > 2000:
        raise HTTPException(status_code=400, detail="Размер чанка должен быть между 100 и 2000")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise HTTPException(status_code=400, detail="Перекрытие чанков должно быть между 0 и размером чанка")
    
    try:
        print(f"⚙️ Применение настроек чанков: размер={chunk_size}, перекрытие={chunk_overlap}")
        chunks_added = add_pdf_to_index(contents, file.filename, chunk_size, chunk_overlap)
        uploaded_filenames.append(file.filename)
        
        update_chunk_settings(chunk_size, chunk_overlap)
        
        return {
            "message": f"'{file.filename}' успешно обработан", 
            "filename": file.filename,
            "chunks_added": chunks_added,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки PDF: {str(e)}")

@app.get("/files")
async def list_files():
    return {"files": [{"filename": name} for name in uploaded_filenames]}

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    if filename in uploaded_filenames:
        uploaded_filenames.remove(filename)
        return {"message": f"'{filename}' удален из списка сессии"}
    else:
        raise HTTPException(status_code=404, detail="Файл не найден в сессии")

class QueryRequest(BaseModel):
    question: str

@app.post("/query")
async def ask_question(request: QueryRequest):
    if not uploaded_filenames:
        raise HTTPException(status_code=400, detail="PDF файлы еще не загружены")
    
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")
    
    try:
        answer = query_index(request.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запроса: {str(e)}")

class ChunkSettingsRequest(BaseModel):
    chunk_size: int
    chunk_overlap: int

@app.post("/chunk-settings")
async def update_chunk_settings_api(request: ChunkSettingsRequest):
    if request.chunk_size < 100 or request.chunk_size > 2000:
        raise HTTPException(status_code=400, detail="Размер чанка должен быть между 100 и 2000")
    if request.chunk_overlap < 0 or request.chunk_overlap >= request.chunk_size:
        raise HTTPException(status_code=400, detail="Перекрытие чанков должно быть между 0 и размером чанка")
    
    result = update_chunk_settings(request.chunk_size, request.chunk_overlap)
    
    chunk_settings.update({
        "chunk_size": request.chunk_size,
        "chunk_overlap": request.chunk_overlap
    })
    
    return {
        "message": "Настройки чанков обновлены",
        "chunk_size": result["chunk_size"],
        "chunk_overlap": result["chunk_overlap"]
    }

@app.get("/chunk-settings")
async def get_chunk_settings():
    return chunk_settings

@app.get("/health")
async def health_check():
    stats = get_index_stats()
    return {
        "status": "работает", 
        "files_uploaded": len(uploaded_filenames),
        "index_stats": stats,
        "chunk_settings": chunk_settings
    }

@app.get("/stats")
async def get_stats():
    stats = get_index_stats()
    return {
        "uploaded_files": uploaded_filenames,
        "vector_db_stats": stats,
        "chunk_settings": chunk_settings
    }