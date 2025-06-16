# 使用官方 Python 基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app
# ENV TZ=Asia/Shanghai

# 切换APT源，安装依赖，清理缓存
# RUN echo 'Types: deb' > /etc/apt/sources.list.d/debian.sources && \
#     echo 'URIs: https://mirror.iscas.ac.cn/debian' >> /etc/apt/sources.list.d/debian.sources && \
#     echo 'Suites: bookworm bookworm-updates bookworm-backports' >> /etc/apt/sources.list.d/debian.sources && \
#     echo 'Components: main contrib non-free non-free-firmware' >> /etc/apt/sources.list.d/debian.sources && \
#     echo 'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' >> /etc/apt/sources.list.d/debian.sources && \
#     apt-get update && \
#     apt-get install -y gcc libffi-dev libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev && \
#     apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "deb https://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list

# 拷贝依赖文件
COPY requirements.txt .

# 使用国内pip镜像源安装依赖
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1


# 暴露端口
EXPOSE 8000

# 运行 FastAPI 服务器
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]