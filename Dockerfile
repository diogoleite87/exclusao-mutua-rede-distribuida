FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY /src /src

COPY requirements.txt ./requirements.txt

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . /src

CMD ["python3", "server.py"]
