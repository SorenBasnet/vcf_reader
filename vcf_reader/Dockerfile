FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        python3 \
        python3-pip \
        bcftools \
        samtools \
        tabix \
        && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip3 install --break-system-packages -r requirements.txt

ENTRYPOINT ["python3", "-m", "vcf_reader.cli"]
