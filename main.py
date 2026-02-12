"""
Файл для запуска REST API сервера
"""
import uvicorn
from api.rest_api import app

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
