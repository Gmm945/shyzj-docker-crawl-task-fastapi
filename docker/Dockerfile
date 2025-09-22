ARG PYTHON_BASE=3.12-slim
# build stage
FROM python:$PYTHON_BASE AS builder
RUN apt-get update && \
    apt-get install -y gcc build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# install PDM
RUN pip install -U pdm
# disable update check
ENV PDM_CHECK_UPDATE=false
# copy files
COPY pyproject.toml pdm.lock README.md /project/
COPY src/ /project/src

# install dependencies and project into the local packages directory
WORKDIR /project
RUN pdm install --check --prod --no-editable

# run stage
FROM python:$PYTHON_BASE

RUN apt-get update \
  && apt-get install -y gcc libffi-dev libssl-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
# retrieve packages from build stage
COPY --from=builder /project/.venv/ /project/.venv
ENV PATH="/project/.venv/bin:$PATH"
# set command/entrypoint, adapt to fit your needs
COPY src /project/src
WORKDIR /project

# 创建日志目录
RUN mkdir -p /project/logs

# 暴露端口（web和flower需要）
EXPOSE 8000 5555

# 默认启动命令（可通过docker-compose的command覆盖）
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]