# 部署与 HTTPS

## 本地开发

```powershell
.\run.ps1 -Setup
.\run.ps1 -Web
# http://127.0.0.1:8766
```

## 局域网访问

`config.yaml`:

```yaml
web:
  host: 0.0.0.0
  port: 8766
  auth_token: "your-strong-token"   # 强烈建议
```

防火墙放行 8766 端口。

## Nginx 反向代理 + HTTPS

```nginx
server {
    listen 443 ssl http2;
    server_name video.example.com;

    ssl_certificate     /etc/letsencrypt/live/video.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/video.example.com/privkey.pem;

    client_max_body_size 2048m;

    location / {
        proxy_pass http://127.0.0.1:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8766;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

WebSocket 路径：`/ws/progress?token=YOUR_AUTH_TOKEN`

## Caddy（更简单）

```caddy
video.example.com {
    reverse_proxy 127.0.0.1:8766
}
```

Caddy 自动申请 Let's Encrypt 证书。

## Docker

```bash
docker compose up -d
# GPU: docker compose -f docker-compose.gpu.yml up -d
```

挂载 `config.yaml`、`output/`、`watch_in/` 卷以持久化数据。
