FROM ubuntu:22.04 AS anova_server

WORKDIR /anova
COPY / /anova
# Update package lists and install necessary packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    software-properties-common \
        gpg-agent
ENV TZ=Europe/Amsterdam
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN add-apt-repository ppa:deadsnakes/ppa -y
RUN apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3.11-distutils \
    python3-pip
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
RUN update-alternatives --config python3
RUN python3.11 -m pip install --upgrade pip
RUN pip install pyproject.toml bleak uvicorn fastapi pydantic-settings httpx
CMD ["uvicorn", "app.main:app", "--reload", "--app-dir", "/anova/python", "--port", "8000", "--host", "0.0.0.0"]
