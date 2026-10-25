######## BASE IMAGE ########
FROM python:3.11-slim-bookworm AS python-base
FROM node:24-bookworm-slim AS img-base

# Arguments
ARG USER=audio2score
ARG USER_HOME=/home/$USER
ARG VOLUME=/app
ARG SHELL=/bin/bash

COPY --from=python-base /usr/local/ /usr/local/
RUN ldconfig
RUN pip3 install --upgrade pip

RUN apt-get update
RUN npm install -g npm

# Inital OS configuration
RUN apt-get install -y locales \
    && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen
RUN apt-get install -y sudo lsb-release git git-lfs curl zip unzip jq

# Install VSCode extensions dependencies
RUN pip3 install cfn-lint cfn-lint-serverless
RUN npm install -g @anthropic-ai/claude-code \
    && node "$(npm root -g)/@anthropic-ai/claude-code/install.cjs" \
    && claude --version

# Install CLI utilities
RUN case "$(dpkg --print-architecture)" in \
        "amd64") AWSCLI_ARCH="x86_64" ;; \
        "arm64"|"aarch64") AWSCLI_ARCH="aarch64" ;; \
        *) echo "Unsupported architecture" && exit 1 ;; \
    esac; \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-${AWSCLI_ARCH}.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && apt-get install -y less

# Install Serverless framework
RUN npm install -g serverless

# Set up non root user
RUN echo "$USER ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
RUN useradd -ms $SHELL $USER
RUN mkdir -p $VOLUME \
    && chown -R $USER:$USER $VOLUME

# Preserve bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && echo $SNIPPET >> "/root/.bashrc" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R $USER /commandhistory \
    && echo $SNIPPET >> "$USER_HOME/.bashrc"

# Let non-root user self-update global npm packages (serverless, claude-code) at runtime
RUN chown -R $USER:$USER /usr/local/lib/node_modules /usr/local/bin


######## AUDIO2SCORE IMAGE ########
# Development image: the same pinned ML runtime as the worker image
# (container/requirements.txt), audio tools, MuseScore for PDFs, the Docker
# CLI (builds/pushes the worker image through the host's Docker daemon) and
# test/lint tooling.
FROM img-base AS img-audio2score

# Install Docker CLI + buildx (Docker's official Debian repository)
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli docker-buildx-plugin

# Install OS utilities (audio decoding, MusicXML → PDF, coverage)
RUN apt-get install -y ffmpeg libsndfile1 musescore3 fonts-freefont-ttf libsqlite3-0
ENV QT_QPA_PLATFORM=offscreen

# Same pinned ML runtime as the worker image, in two layers so the heavy
# wheels (torch, TensorFlow) stay cached: everything but demucs first.
COPY container/requirements.txt /tmp/audio2score-requirements.txt
RUN grep -v '^demucs' /tmp/audio2score-requirements.txt > /tmp/audio2score-base.txt \
    && pip3 install -r /tmp/audio2score-base.txt

# demucs depends on sphn, which only ships x86_64 wheels: on arm64 hosts
# (Apple Silicon) it's compiled with Rust, a C toolchain and the system
# libopus (audiopus_sys would otherwise build opus with a CMake it rejects).
RUN if [ "$(dpkg --print-architecture)" = "arm64" ]; then \
        apt-get install -y build-essential cmake pkg-config libopus-dev \
        && curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal; \
    fi \
    && PATH="$HOME/.cargo/bin:$PATH" CMAKE_POLICY_VERSION_MINIMUM=3.5 \
        pip3 install -r /tmp/audio2score-requirements.txt

# Install VSCode extensions dependencies
RUN pip3 install pylint yapf isort

# Install Dev utilities
RUN pip3 install jupyterlab matplotlib ipywidgets

# Install Test utilities
RUN pip3 install pytest pytest-cov pytest-env pytest-mock moto

# Model weights and numba's JIT cache (librosa) live in ~/.cache, mounted as
# a volume: created here so the volume inherits the user's ownership.
ARG USER=audio2score
RUN mkdir -p /home/$USER/.cache && chown -R $USER:$USER /home/$USER/.cache
ENV NUMBA_CACHE_DIR=/home/$USER/.cache/numba

USER $USER
