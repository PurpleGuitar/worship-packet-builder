# Start with a Python environment
FROM python:3.12.3-slim

# Install make
RUN apt-get update && apt-get install -y make

# Clean up apt cache
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Set up venv
COPY makefile /app
COPY requirements.txt /app
RUN make .venv

# Copy the rest of the application code
COPY tests/ /app/tests/
COPY *.py /app
