# freshrss-mcp

> FreshRSS MCP Server — FastMCP 包装 FreshRSS Google Reader API。
> 零第三方依赖（仅 fastmcp + stdlib urllib）。
> 端口 8770。

## MCP Tools

| 工具 | 说明 |
|------|------|
| `list_feeds` | 列出所有订阅源 |
| `get_articles` | 获取指定源文章（含全文） |
| `search_articles` | 跨源关键词搜索 |
| `get_starred` | 获取收藏文章 |

## 环境变量

| 变量 | 说明 |
|------|------|
| `PORT` | 服务端口（默认 8770） |

凭据由调用方在每个 tool 调用中传入。

## 部署

CI push → `ghcr.io/monaron/freshrss-mcp:latest` + `:<sha>`
→ ArgoCD 同步 → 滚动更新
