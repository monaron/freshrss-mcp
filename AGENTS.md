# freshrss-mcp

> FreshRSS MCP Server — FastMCP 包装 FreshRSS Google Reader API。
> 端口 8770，部署于 relay 命名空间。

## 仓库

```
freshrss-mcp/
├── AGENTS.md                 # AI agent 指令
├── LOGBOOK.md                # 运维日志
├── README.md                 # 项目文档
├── .gitignore
├── Dockerfile                # CI 构建
├── server.py                 # FastMCP 服务入口
├── requirements.txt          # fastmcp + uvicorn (零第三方)
└── .github/
    └── workflows/deploy.yml  # CI/CD → ghcr.io
```

## 架构

```
unmixable7464 → freshrss-mcp.relay.svc:8770/mcp → rss.edge.svc/p/api/greader.php
```

## 约定

- 提交信息：中文，动词开头
- 不提交 .env、backup 文件、临时 zip、.DS_Store
- 凭据由调用方传入，不绑定 Pod
