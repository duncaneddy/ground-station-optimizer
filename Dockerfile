# Use the official Python image from the Docker Hub
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Update PIP
RUN pip install --upgrade pip

# Create a directory for the app
RUN mkdir -p /app/

# Copy the current directory contents into the container
COPY ./.streamlit/ /app/.streamlit/
COPY ./gsopt/ /app/gsopt/
COPY ./data/ /app/data/
COPY pyproject.toml /app/

# Set the working directory in the container
WORKDIR /app

# Install any dependencies
RUN pip install --no-cache-dir .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Enture the Streamlit app is healthy
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health

# Run Streamlit when the container launches
ENTRYPOINT ["streamlit", "run", "gsopt/app.py", "--server.port=8080", "--server.address=0.0.0.0"]