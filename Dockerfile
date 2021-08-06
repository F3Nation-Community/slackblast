# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.9-slim

# gunicorn is required to run this.  But Azure (where this was written to run) provides it already so i didn't want to add it to the requirements.txt file
RUN pip install gunicorn

# Copy local code to the container image.
WORKDIR /app
COPY . .

# Install production dependencies.
RUN pip install -r ./requirements.txt

CMD exec gunicorn -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:8000" --log-level debug app:app
