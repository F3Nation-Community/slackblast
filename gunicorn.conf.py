# Azure App Service automatically runs following command for Flask Apps
# - https://docs.microsoft.com/en-us/azure/app-service/configure-language-python#flask-app
#
# If app.py
# gunicorn --bind=0.0.0.0 --timeout 600 app:app

# Further configure important settings such as worker_class, e.g. for async handlers
worker_class="uvicorn.workers.UvicornWorker"
loglevel="debug"
