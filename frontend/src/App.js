import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [files, setFiles] = useState([]);
  const [chunkSettings, setChunkSettings] = useState({
    chunk_size: 512,
    chunk_overlap: 50
  });
  const [showChunkSettings, setShowChunkSettings] = useState(false);

  useEffect(() => {
    fetchFiles();
    fetchChunkSettings();
  }, []);

  const fetchFiles = async () => {
    try {
      const res = await fetch('http://localhost:8000/files');
      const data = await res.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Ошибка загрузки файлов:', error);
    }
  };

  const fetchChunkSettings = async () => {
    try {
      const res = await fetch('http://localhost:8000/chunk-settings');
      const data = await res.json();
      setChunkSettings(data);
    } catch (error) {
      console.error('Ошибка загрузки настроек чанков:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setAnswer('');

    try {
      const res = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Не удалось получить ответ');
      }

      const data = await res.json();
      setAnswer(data.answer);
    } catch (error) {
      console.error('Ошибка:', error);
      setAnswer('❌ ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      alert('Пожалуйста, загружайте только PDF файлы');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', chunkSettings.chunk_size); 
    formData.append('chunk_overlap', chunkSettings.chunk_overlap); 

    try {
      const url = 'http://localhost:8000/upload';
      
      const res = await fetch(url, {
        method: 'POST',
        body: formData, 
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ошибка загрузки');
      }

      const data = await res.json();
      alert(`${data.message}\nДобавлено чанков: ${data.chunks_added}\nРазмер чанка: ${data.chunk_size}\nПерекрытие: ${data.chunk_overlap}`);
      await fetchFiles(); 
      e.target.value = ''; 
    } catch (error) {
      console.error('Ошибка загрузки:', error);
      alert('Ошибка загрузки: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (filename) => {
    if (!window.confirm(`Вы уверены, что хотите удалить "${filename}"?`)) return;

    try {
      const res = await fetch(`http://localhost:8000/files/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ошибка удаления');
      }

      const data = await res.json();
      alert(data.message);
      await fetchFiles(); 
    } catch (error) {
      console.error('Ошибка удаления:', error);
      alert('Ошибка удаления: ' + error.message);
    }
  };

  const handleChunkSettingsUpdate = async (e) => {
    e.preventDefault();
    
    try {
      const res = await fetch('http://localhost:8000/chunk-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chunkSettings),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ошибка обновления настроек');
      }

      const data = await res.json();
      alert(`✅ ${data.message}\nНовый размер чанка: ${data.chunk_size}\nНовое перекрытие: ${data.chunk_overlap}`);
      setShowChunkSettings(false);
    } catch (error) {
      console.error('Ошибка обновления настроек:', error);
      alert('Ошибка обновления настроек: ' + error.message);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>📄 PDF Ассистент вопросов и ответов</h1>
      
      {/* Настройки чанков */}
      <div style={{ marginBottom: '2rem', padding: '1rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>Настройки разделения текста</h3>
          <button
            onClick={() => setShowChunkSettings(!showChunkSettings)}
            style={{
              background: '#28a745',
              color: 'white',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            {showChunkSettings ? 'Скрыть настройки' : 'Показать настройки'}
          </button>
        </div>

        {showChunkSettings && (
          <form onSubmit={handleChunkSettingsUpdate}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Размер чанка (100-2000):
                </label>
                <input
                  type="number"
                  min="100"
                  max="2000"
                  value={chunkSettings.chunk_size}
                  onChange={(e) => setChunkSettings({
                    ...chunkSettings,
                    chunk_size: parseInt(e.target.value) || 512
                  })}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
                />
                <small style={{ color: '#666' }}>
                  Больше = больше контекста, но менее точный поиск
                </small>
              </div>
              
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Перекрытие чанков (0-{chunkSettings.chunk_size - 1}):
                </label>
                <input
                  type="number"
                  min="0"
                  max={chunkSettings.chunk_size - 1}
                  value={chunkSettings.chunk_overlap}
                  onChange={(e) => setChunkSettings({
                    ...chunkSettings,
                    chunk_overlap: parseInt(e.target.value) || 50
                  })}
                  style={{ width: '100%', padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
                />
                <small style={{ color: '#666' }}>
                  Больше = лучше сохранение контекста между чанками
                </small>
              </div>
            </div>
            
            <div style={{ 
              padding: '1rem', 
              background: '#f8f9fa', 
              borderRadius: '4px',
              marginBottom: '1rem'
            }}>
              <strong>Текущие настройки:</strong><br />
              📏 Размер чанка: <strong>{chunkSettings.chunk_size}</strong> символов<br />
              🔄 Перекрытие: <strong>{chunkSettings.chunk_overlap}</strong> символов
            </div>
            
            <button
              type="submit"
              style={{
                background: '#007bff',
                color: 'white',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              💾 Сохранить настройки
            </button>
          </form>
        )}
      </div>

      {/* Загрузка файлов */}
      <div style={{ marginBottom: '2rem', padding: '1rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h3>Загрузить PDF файлы</h3>
        <p style={{ color: '#666', marginBottom: '1rem' }}>
          Файлы будут обработаны с текущими настройками разделения
        </p>
        <input
          type="file"
          accept=".pdf"
          onChange={handleFileUpload}
          disabled={uploading}
          style={{ marginBottom: '1rem' }}
        />
        {uploading && <p>📤 Загрузка и обработка файла...</p>}
      </div>

      {/* Список файлов */}
      <div style={{ marginBottom: '2rem', padding: '1rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h3>Загруженные файлы ({files.length})</h3>
        {files.length === 0 ? (
          <p>PDF файлы еще не загружены.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {files.map((file, index) => (
              <li key={index} style={{ 
                padding: '0.5rem', 
                margin: '0.5rem 0', 
                background: '#f9f9f9',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>📄 {file.filename}</span>
                <button
                  onClick={() => handleDeleteFile(file.filename)}
                  style={{ 
                    background: '#ff4444', 
                    color: 'white', 
                    border: 'none', 
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  Удалить
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Вопросы и ответы */}
      <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h3>Задать вопросы</h3>
        <form onSubmit={handleSubmit}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Задайте вопрос о ваших загруженных PDF файлах..."
            rows="3"
            style={{ width: '100%', padding: '0.5rem', marginBottom: '1rem' }}
          />
          <button
            type="submit"
            disabled={loading || !question.trim() || files.length === 0}
            style={{ 
              padding: '0.5rem 1rem',
              background: files.length === 0 ? '#ccc' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: files.length === 0 ? 'not-allowed' : 'pointer'
            }}
          >
            {loading ? 'Думаю...' : 'Задать вопрос'}
          </button>
          {files.length === 0 && (
            <p style={{ color: '#666', marginTop: '0.5rem' }}>
              Пожалуйста, загрузите хотя бы один PDF файл для задавания вопросов.
            </p>
          )}
        </form>

        {answer && (
          <div style={{ marginTop: '2rem', padding: '1rem', background: '#f0f0f0', borderRadius: '4px' }}>
            <h3>Ответ:</h3>
            <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;