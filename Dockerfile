# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.9-slim

#RUN pip install gunicorn slack_bolt aiohttp python-decouple fastapi uvicorn uvloop httptools

# Copy local code to the container image.
WORKDIR /app
COPY . .

# Install production dependencies.
RUN pip install -r ./requirements.txt

#ENTRYPOINT ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind 0.0.0.0:8000", "app:app"]
CMD exec gunicorn -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:8000" --log-level debug app:app
