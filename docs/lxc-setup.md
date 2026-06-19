# Развёртывание шлюза в LXC (Proxmox)

Шлюз — критическая инфраструктура (от него зависят все агенты), поэтому он живёт в отдельном LXC: изоляция, автоперезапуск, простой бэкап.

## 1. Создать LXC на Proxmox

- Шаблон: **Debian 12** (или Ubuntu 22.04/24.04).
- Ресурсы: **2 vCPU, 2 ГБ RAM, 8 ГБ диск** (LiteLLM ~0.85 ГБ + Postgres + Redis ≈ 1 ГБ, остальное — запас).
- Сеть: статический IP в LAN (напр. `192.168.3.x`), без проброса наружу.
- **Включить nesting** (для Docker внутри LXC): в Proxmox → Options → Features → отметить `nesting=1` (и `keyctl=1`). Без этого Docker в LXC не запустится.

## 2. Поставить Docker внутри LXC

```bash
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh
docker compose version   # проверка, что плагин compose на месте
```

## 3. Развернуть проект

```bash
mkdir -p /opt && cd /opt
git clone <твой-репозиторий> LLM-gateway   # или rsync с рабочей машины
cd LLM-gateway
cp .env.example .env
nano .env                                  # заполнить ключи провайдеров, пароли, master key
docker compose up -d
docker compose ps                          # все healthy?
```

## 4. Проверка

```bash
curl http://localhost:4000/health/liveliness          # "I'm alive!"
# с master key — список моделей каталога:
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```
UI: с любой машины в LAN → `http://<lxc-ip>:4000/ui` (логин `admin`, пароль = `LITELLM_MASTER_KEY`).

## 5. Бэкап и автозапуск

- Бэкап БД: повесить `scripts/backup_db.sh` на cron (см. комментарий в скрипте).
- Автозапуск контейнеров обеспечивает `restart: unless-stopped`; сам LXC поставить на автозапуск в Proxmox.

## 6. LAN-only и доступ

- Порт 4000 доступен только во внутренней сети (у LXC нет публичного IP).
- Для устойчивых адресов клиентов задай шлюзу DNS-имя (запись в роутере/Pi-hole), напр. `llm.home → 192.168.3.x`.
- Если когда-нибудь понадобится доступ извне — только через существующий reverse-proxy (nginx) с TLS и IP-allowlist, НЕ публикуя 4000 напрямую.
