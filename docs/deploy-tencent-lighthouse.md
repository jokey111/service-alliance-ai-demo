# 腾讯云轻量应用服务器部署（Ubuntu，暂时无域名）

本指南先用公网 IP 联调，再切换到域名和 HTTPS。项目使用合成数据。公网 IP 阶段是明文 HTTP，只用于部署验收，不作为最终面试链接。

## 1. 检查云主机

在腾讯云控制台打开“轻量应用服务器 → 服务器”，选择中国香港地域，确认实例状态为“运行中”，记录**公网 IP**。进入实例详情页的“防火墙”，放行入站 TCP 80；购买域名后再放行 TCP 443。如需从本机通过 SSH 登录，放行 TCP 22，并尽量将来源限制为自己的公网 IP。数据库、API 和 MCP 的端口不需要向公网开放。

可点击实例卡片上的“登录”，使用腾讯云浏览器终端操作 Ubuntu；无需在聊天中分享服务器密码或 SSH 私钥。Ubuntu 的默认登录用户名通常是 `ubuntu`。

## 2. 安装基础软件

在服务器终端检查：

```bash
cat /etc/os-release
git --version
docker --version
docker compose version
```

没有 Git 时运行 `sudo apt update`、`sudo apt install -y git`。没有 Docker Engine 或 Compose 插件时，按 [Docker 官方 Ubuntu 安装文档](https://docs.docker.com/engine/install/ubuntu/) 安装；完成后重新运行 `sudo docker compose version` 核对。不要把本地 Windows 的 `.venv` 或 `node_modules` 复制到服务器。

## 3. 拉取代码并配置密钥

```bash
git clone https://github.com/jokey111/service-alliance-ai-demo.git
cd service-alliance-ai-demo
cp .env.example .env
openssl rand -hex 24
nano .env
```

将刚生成的随机字符串填入 `.env` 的 `POSTGRES_PASSWORD=` 后面。暂时没有域名时保留 `SITE_ADDRESS=:80`。`ZHIPU_API_KEY` 应使用**标准 API Key**；还没有标准 Key 时可暂时留空，业务 Skill 与 MCP 仍可联调，模型生成会回退。不要将 `.env` 提交到 GitHub，也不要把 Key 发到聊天里。

## 4. 启动并验收

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
curl -fsS http://127.0.0.1/api/health
```

确认四个服务正常运行，再从个人电脑访问 `http://公网IP/` 与 `http://公网IP/api/health`。若页面打不开，先检查实例状态、腾讯云防火墙中的 80 端口，以及 `sudo docker compose logs --tail=100 web api mcp db`。若需要更新代码，先 `git pull`，再运行 `sudo docker compose up -d --build`。

## 5. 域名准备好后

将域名 A 记录解析到服务器公网 IP，在腾讯云防火墙放行入站 TCP 80 和 443；把 `.env` 中的 `SITE_ADDRESS` 改为域名，然后运行：

```bash
sudo docker compose up -d --force-recreate web
sudo docker compose logs --tail=100 web
```

Caddy 会按域名申请并续期 HTTPS 证书。验证 `https://你的域名/` 和 `https://你的域名/api/health` 后，再把链接放进简历。
