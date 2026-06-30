"""
FreshRSS MCP Server — Read RSS feeds via Google Reader compatible API.
Credentials come from request headers (x-freshrss-url, x-freshrss-username, x-freshrss-password)
or from explicit tool parameters.
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("freshrss-mcp")

PORT = int(os.environ.get("PORT", "8770"))

mcp = FastMCP("freshrss-mcp")


def _resolve(url: str = "", username: str = "", password: str = ""):
    from fastmcp.server.dependencies import get_http_request
    try:
        hdrs = get_http_request().headers
        logger.info("headers: url=%s user=%s pass=%s",
                    hdrs.get("x-freshrss-url", "")[:40] or "(none)",
                    hdrs.get("x-freshrss-username", "") or "(none)",
                    "***" if hdrs.get("x-freshrss-password") else "(none)")
    except RuntimeError:
        hdrs = {}
        logger.warning("get_http_request() failed")
    u = url or hdrs.get("x-freshrss-url", "")
    un = username or hdrs.get("x-freshrss-username", "")
    pw = password or hdrs.get("x-freshrss-password", "")
    if not u or not un or not pw:
        raise ValueError("Credentials required (params or x-freshrss-* headers)")
    return u, un, pw


class FreshRSSClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth_token = None
        self._login(username, password)

    def _login(self, username: str, password: str) -> None:
        data = f"Email={urllib.parse.quote(username)}&Passwd={urllib.parse.quote(password)}"
        req = urllib.request.Request(
            f"{self.base_url}/accounts/ClientLogin",
            data=data.encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            for line in body.split("\n"):
                if line.startswith("Auth="):
                    self.auth_token = line.split("=", 1)[1].strip()
                    return
        raise RuntimeError("Login failed: no Auth token")

    def _api(self, path: str) -> Any:
        url = f"{self.base_url}/reader/api/0/{path}"
        req = urllib.request.Request(url, headers={"Authorization": f"GoogleLogin auth={self.auth_token}"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def list_feeds(self) -> List[Dict]:
        data = self._api("subscription/list?output=json")
        result = []
        for sub in data.get("subscriptions", []):
            result.append({
                "id": sub.get("id", ""),
                "title": sub.get("title", ""),
                "categories": [c["label"] for c in sub.get("categories", [])],
                "url": sub.get("url", ""),
            })
        return result

    def get_article_ids(self, feed_id: str, count: int = 20) -> List[str]:
        qs = f"s={urllib.parse.quote(feed_id)}&n={count}&output=json"
        data = self._api(f"stream/items/ids?{qs}")
        return [r.get("id", "") for r in data.get("itemRefs", [])]

    def get_articles(self, feed_id: str, count: int = 20) -> List[Dict]:
        ids = self.get_article_ids(feed_id, count)
        if not ids:
            return []
        body = json.dumps({"i": ids, "output": "json"}).encode()
        url = f"{self.base_url}/reader/api/0/stream/items/contents"
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"GoogleLogin auth={self.auth_token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        result = []
        for item in data.get("items", []):
            result.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "published": datetime.fromtimestamp(int(item.get("published", 0))).isoformat(),
                "summary": _strip_html(item.get("summary", {}).get("content", "")),
                "content": _strip_html(item.get("content", {}).get("content", "")),
                "url": _first(item.get("canonical", [])),
                "author": item.get("author", ""),
                "origin": _first(item.get("origin", {}).get("title", "")),
            })
        return result

    def get_starred(self, count: int = 50) -> List[Dict]:
        return self.get_articles("user/-/state/com.google/starred", count)

    def search_ids(self, query: str, count: int = 20) -> List[str]:
        qs = f"q={urllib.parse.quote(query)}&n={count}&output=json"
        data = self._api(f"search/items/ids?{qs}")
        return [r.get("id", "") for r in data.get("results", [])]

    def search_articles(self, query: str, count: int = 20) -> List[Dict]:
        qs = f"q={urllib.parse.quote(query)}&n={count}&output=json"
        data = self._api(f"search/items/ids?{qs}")
        item_ids = [r.get("id", "") for r in data.get("results", [])]
        if not item_ids:
            return []
        ids = item_ids[:count]
        body = json.dumps({"i": ids, "output": "json"}).encode()
        url = f"{self.base_url}/reader/api/0/stream/items/contents"
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"GoogleLogin auth={self.auth_token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        result = []
        for item in data.get("items", []):
            result.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "published": datetime.fromtimestamp(int(item.get("published", 0))).isoformat(),
                "summary": _strip_html(item.get("summary", {}).get("content", "")),
                "content": _strip_html(item.get("content", {}).get("content", "")),
                "url": _first(item.get("canonical", [])),
                "author": item.get("author", ""),
            })
        return result


def _strip_html(text: str) -> str:
    result = []
    skip = False
    for c in text:
        if c == "<":
            skip = True
        elif c == ">":
            skip = False
        elif not skip:
            result.append(c)
    return "".join(result)


def _first(val: Any) -> str:
    if isinstance(val, list) and val:
        v = val[0]
        return v.get("href", str(v)) if isinstance(v, dict) else str(v)
    if isinstance(val, dict):
        return val.get("href", str(val))
    return str(val) if val else ""


# -------------------------------- tools ---------------------------------

@mcp.tool()
def list_feeds(
    freshss_url: str = "",
    freshss_username: str = "",
    freshss_password: str = "",
) -> Dict[str, Any]:
    """List all subscribed RSS feeds. Credentials come from headers or params."""
    try:
        url, username, password = _resolve(freshss_url, freshss_username, freshss_password)
        client = FreshRSSClient(url, username, password)
        feeds = client.list_feeds()
        return {"count": len(feeds), "feeds": feeds}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_articles(
    freshss_url: str = "",
    freshss_username: str = "",
    freshss_password: str = "",
    feed_title: Optional[str] = None,
    feed_id: Optional[str] = None,
    count: int = 20,
) -> Dict[str, Any]:
    """Get articles with full text from a feed. Credentials from headers or params."""
    try:
        url, username, password = _resolve(freshss_url, freshss_username, freshss_password)
        client = FreshRSSClient(url, username, password)
        if feed_id:
            fid = feed_id
        elif feed_title:
            feeds = client.list_feeds()
            match = next((f for f in feeds if f["title"].lower() == feed_title.lower()), None)
            if not match:
                return {"error": f"Feed not found: {feed_title}"}
            fid = match["id"]
        else:
            return {"error": "feed_title or feed_id required"}
        articles = client.get_articles(fid, count)
        return {"feed": feed_title or feed_id, "count": len(articles), "articles": articles}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def search_articles(
    freshss_url: str = "",
    freshss_username: str = "",
    freshss_password: str = "",
    query: str = "",
    count: int = 20,
) -> Dict[str, Any]:
    """Search across all feeds. Credentials from headers or params."""
    try:
        url, username, password = _resolve(freshss_url, freshss_username, freshss_password)
        client = FreshRSSClient(url, username, password)
        articles = client.search_articles(query, count)
        return {"query": query, "count": len(articles), "articles": articles}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_starred(
    freshss_url: str = "",
    freshss_username: str = "",
    freshss_password: str = "",
    count: int = 50,
) -> Dict[str, Any]:
    """Get starred articles. Credentials from headers or params."""
    try:
        url, username, password = _resolve(freshss_url, freshss_username, freshss_password)
        client = FreshRSSClient(url, username, password)
        articles = client.get_starred(count)
        return {"count": len(articles), "articles": articles}
    except Exception as e:
        return {"error": str(e)}


def main():
    app = mcp.http_app(path="/mcp", stateless_http=True)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
