"""容器启动前等待 PostgreSQL 完全就绪。

`pg_isready` 只验证端口监听，不验证能执行查询；`docker compose restart`
不等待 healthcheck，导致 celery_beat 的 DatabaseScheduler 在 db 关闭
期间查询被 AdminShutdown 终止。本脚本在 celery 启动前轮询 SELECT 1，
确保数据库连接真正可用后才放行。
"""
import os
import sys
import time

import psycopg


def main() -> None:
    url = os.environ.get('DATABASE_URL')
    if not url:
        print('DATABASE_URL not set, skip wait', flush=True)
        return

    max_attempts = 60
    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(url, connect_timeout=3) as conn:
                conn.execute('SELECT 1')
            print(f'Database ready (attempt {attempt}/{max_attempts})', flush=True)
            return
        except Exception as exc:
            print(f'Waiting for database ({attempt}/{max_attempts}): {exc}', flush=True)
            time.sleep(1)

    print(f'Database not ready after {max_attempts}s', file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == '__main__':
    main()
