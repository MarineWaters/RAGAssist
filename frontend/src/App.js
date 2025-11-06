import React, { useState, useEffect } from 'react';
import { RingLoader, PropagateLoader } from 'react-spinners';
import './App.css';

function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(true);
  const [filesError, setFilesError] = useState('');
  const [answerMode, setAnswerMode] = useState('vector');

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    setLoadingFiles(true);
    setFilesError('');
    try {
      const res = await fetch('http://localhost:8000/files');
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Ошибка загрузки файлов:', error);
      setFilesError('Не удалось загрузить список файлов. Проверьте подключение к серверу.');
    } finally {
      setLoadingFiles(false);
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
        body: JSON.stringify({ question, mode: answerMode }),
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

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadProgress({ current: 0, total: files.length, currentFile: '' });

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(prev => ({ ...prev, current: i + 1, currentFile: file.name }));

      if (file.type !== 'application/pdf' &&
      file.type !== 'application/vnd.oasis.opendocument.text' &&
      file.type !== 'application/msword' &&
      file.type !== 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
        alert(`Пожалуйста, загружайте только pdf, doc, docx, odt файлы. Файл "${file.name}" пропущен.`);
        continue;
      }

      const formData = new FormData();
      formData.append('file', file);

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
        alert(`${data.message}\nДобавлено чанков: ${data.chunks_added}`);
      } catch (error) {
        console.error('Ошибка загрузки:', error);
        alert(`Ошибка загрузки файла "${file.name}": ${error.message}`);
      }
    }

    await fetchFiles();
    setUploadProgress(null);
    setUploading(false);
  };

  const handleInputChange = (e) => {
    handleFileUpload(Array.from(e.target.files));
    e.target.value = '';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = Array.from(e.dataTransfer.files);
    handleFileUpload(files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDeleteFile = async (filename) => {
    if (!window.confirm(`Вы уверены, что хотите удалить "${filename}"?`)) 
      return;
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

  const handleDeleteAllFiles = async () => {
    if (!window.confirm(`Вы уверены, что хотите удалить ВСЕ файлы (${files.length})?`)) return;
    try {
      const res = await fetch('http://localhost:8000/files', {
        method: 'DELETE',
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ошибка удаления всех файлов');
      }
      const data = await res.json();
      alert(data.message);
      await fetchFiles();
    } catch (error) {
      console.error('Ошибка удаления всех файлов:', error);
      alert('Ошибка удаления всех файлов: ' + error.message);
    }
  };

  
  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Ассистент поиска по документам</h1>
      {/* Загрузка файлов */}
      <div
        style={{
          marginBottom: '2rem',
          padding: '2rem',
          border: dragActive ? '2px dashed #007bff' : '2px dashed #ccc',
          borderRadius: '8px',
          backgroundColor: dragActive ? '#f0f8ff' : '#fafafa',
          textAlign: 'center',
          cursor: uploading ? 'not-allowed' : 'pointer',
          transition: 'all 0.3s ease',
          position: 'relative'
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !uploading && document.getElementById('file-upload').click()}
      >
        <input
          id="file-upload"
          type="file"
          accept=".pdf, .odt, .doc, .docx"
          multiple
          onChange={handleInputChange}
          disabled={uploading}
          style={{
            position: 'absolute',
            opacity: 0,
            width: '100%',
            height: '100%',
            cursor: uploading ? 'not-allowed' : 'pointer'
          }}
        />
        <div style={{ pointerEvents: 'none' }}>
          {uploading && uploadProgress ? (
            <>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>
                ⏳
              </div>
              <h3 style={{ margin: '0 0 1rem 0', color: '#333' }}>
                Загрузка файлов
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ marginLeft: '-20px' }}>
                  <PropagateLoader size={20} color="#007bff" />
                </div>
                <p></p>
                <p style={{ margin: '1rem 0 0.5rem 0', color: '#666', textAlign: 'center' }}>📤 Обработка файлов...</p>
                <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem', color: '#666', textAlign: 'center' }}>
                  Файл {uploadProgress.current} из {uploadProgress.total}: {uploadProgress.currentFile}
                </p>
                <div style={{
                  width: '80%',
                  height: '8px',
                  backgroundColor: '#e0e0e0',
                  borderRadius: '4px',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: `${(uploadProgress.current / uploadProgress.total) * 100}%`,
                    height: '100%',
                    backgroundColor: '#007bff',
                    transition: 'width 0.3s ease'
                  }}></div>
                </div>
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>
                📁
              </div>
              <h3 style={{ margin: '0 0 1rem 0', color: '#333' }}>
                Загрузить файлы
              </h3>
              <p style={{ margin: '0', color: '#666', fontSize: '0.9rem' }}>
                Кликните для выбора файлов или перетащите их сюда
              </p>
            </>
          )}
        </div>
      </div>

      {/* Список файлов */}
      <div style={{ marginBottom: '2rem', padding: '1rem', border: '1px solid #ddd', borderRadius: '8px' }}>
        <h3>Загруженные файлы ({files.length})</h3>
        {loadingFiles && <p>📥 Загрузка списка файлов...</p>}
        {filesError && <p style={{ color: 'red' }}>⚠️ {filesError}</p>}
        {/* Кнопки управления */}
        {files.length > 0 && (
          <div style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <button
              onClick={() => handleDeleteAllFiles()}
              style={{
                background: '#ff4444',
                color: 'white',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
            >
              🗑️ Удалить все файлы
            </button>
          </div>
        )}
        
        {files.length === 0 ? (
          <p>Файлы ещё не загружены.</p>
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
        <h3>Задать вопрос</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="checkbox"
                checked={answerMode === 'combined'}
                onChange={(e) => setAnswerMode(e.target.checked ? 'combined' : 'vector')}
              />
              Продвинутый поиск
            </label>
          </div>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Задайте вопрос..."
            rows="3"
            style={{ width: '99%', padding: '0.5rem', marginBottom: '1rem' }}
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
              cursor: files.length === 0 ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            {loading ? (
              <>
                <RingLoader size={20} color="white" />
                <span> Ассистент думает...</span>
              </>
            ) : (
              '🧠 Спросить'
            )}
          </button>
          {files.length === 0 && (
            <p style={{ color: '#666', marginTop: '0.5rem' }}>
              Пожалуйста, загрузите хотя бы один файл.
            </p>
          )}
        </form>
        {answer && (
          <div style={{ marginTop: '2rem', padding: '1rem', background: '#f0f0f0', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0 }}>Ответ ассистента:</h3>
            </div>
            <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;