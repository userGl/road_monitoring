"""
Файл для запуска REST API сервера
"""
import uvicorn
from api.rest_api import app

if __name__ == "__main__":
    uvicorn.run(
        app,thon 
        host="0.0.0.0",
        port=8085,
        log_level="info"
    )
