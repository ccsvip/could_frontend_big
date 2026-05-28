FROM python:3.13

ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG APT_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Linux 服务器构建时优先使用国内 Debian 镜像，避免官方源下载过慢。
RUN set -eux; \
    for source_file in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
        if [ -f "$source_file" ]; then \
            sed -i \
                -e "s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|https://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|http://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|https://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|http://deb.debian.org/debian|${APT_MIRROR}|g" \
                -e "s|https://deb.debian.org/debian|${APT_MIRROR}|g" \
                "$source_file"; \
        fi; \
    done; \
    apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# Python 依赖同样走可配置镜像源，避免服务器构建时卡在 PyPI 下载。
RUN pip install --no-cache-dir -i "${PIP_INDEX_URL}" -r requirements.txt

COPY . .

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
