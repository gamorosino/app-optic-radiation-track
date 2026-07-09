FROM continuumio/miniconda3:24.1.2-0

# System libraries needed by nilearn, fury, OpenGL
RUN apt-get update && apt-get install -y --no-install-recommends \
        git wget curl ca-certificates \
        libgl1-mesa-glx libglib2.0-0 libgomp1 \
        && rm -rf /var/lib/apt/lists/*

# MRtrix3 via its own conda channel
RUN conda install -y mrtrix3::mrtrix3 && \
    conda clean -afy

# Python packages
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt

# App
WORKDIR /app
COPY . /app

RUN chmod +x main

ENTRYPOINT ["bash", "main"]
