ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest
ARG NODE_IMAGE=node:22-slim
ARG BASE_IMAGE=python:3.12-slim

FROM ${UV_IMAGE} as uv_source
FROM ${NODE_IMAGE} as node_source
FROM ${BASE_IMAGE}

ARG HTTP_PROXY
ARG http_proxy
ARG HTTPS_PROXY
ARG https_proxy
ARG NO_PROXY
ARG no_proxy

ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST
ARG UV_INDEX_URL
ARG UV_TRUSTED_HOST
ARG UV_SYSTEM_CERTS
ARG NODE_TLS_REJECT_UNAUTHORIZED

ENV HTTP_PROXY=$HTTP_PROXY
ENV http_proxy=$http_proxy
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV https_proxy=$https_proxy
ENV NO_PROXY=$NO_PROXY
ENV no_proxy=$no_proxy

ENV PIP_INDEX_URL=$PIP_INDEX_URL
ENV PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST
ENV UV_INDEX_URL=$UV_INDEX_URL
ENV UV_TRUSTED_HOST=$UV_TRUSTED_HOST
ENV UV_SYSTEM_CERTS=$UV_SYSTEM_CERTS
ENV NODE_TLS_REJECT_UNAUTHORIZED=$NODE_TLS_REJECT_UNAUTHORIZED

ARG DEBIAN_REPO
RUN if [ -n "$DEBIAN_REPO" ]; then \
        sed -i "s|deb.debian.org|$DEBIAN_REPO|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
        sed -i "s|deb.debian.org|$DEBIAN_REPO|g" /etc/apt/sources.list 2>/dev/null || true; \
    fi

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    make \
    build-essential \
    zsh \
    socat \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js from node_source
COPY --from=node_source /usr/local/bin/node /usr/local/bin/
COPY --from=node_source /usr/local/lib/node_modules/ /usr/local/lib/node_modules/
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack

# Install global npm packages
RUN npm install -g playwright-cli

# Install uv package manager
COPY --from=uv_source /uv /uvx /bin/

# Set zsh as default shell for the user
RUN chsh -s /bin/zsh $USERNAME

# Install additional CLI tools
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && curl -fsSL https://opencode.ai/install | bash \
    && curl -fsSL https://pi.dev/install.sh | sh

# Set working directory and user
USER $USERNAME
WORKDIR /workspace

# Install oh-my-zsh and plugins
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended \
    && git clone https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && git clone https://github.com/zsh-users/zsh-syntax-highlighting ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting \
    && sed -i 's/plugins=(git)/plugins=(git zsh-autosuggestions zsh-syntax-highlighting)/' ~/.zshrc

# Install playwright-cli skills
RUN playwright-cli install --skills
