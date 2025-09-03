
## Kurulum ve Çalıştırma

### Gereksinimler

- Python 3.11 veya üstü
- Node.js 18 veya üstü
- pip (Python paket yöneticisi)
- npm (Node.js paket yöneticisi)

### Backend Kurulumu

1.  `backend` dizinine gidin:
    ```bash
    cd backend
    ```

2.  Gerekli Python paketlerini kurun:
    ```bash
    pip install -r requirements.txt
    ```

3.  Backend sunucusunu başlatın:
    ```bash
    uvicorn main:app --reload
    ```
    Sunucu `http://127.0.0.1:8000` adresinde çalışmaya başlayacaktır.

### Frontend Kurulumu

1.  `frontend` dizinine gidin:
    ```bash
    cd frontend
    ```

2.  Gerekli Node.js paketlerini kurun:
    ```bash
    npm install
    ```

3.  Frontend geliştirme sunucusunu başlatın:
    ```bash
    npm start
    ```
    Uygulama `http://localhost:3000` adresinde açılacaktır.
