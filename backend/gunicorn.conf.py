import os

# Usa gevent para suportar requisições concorrentes sem threads pesadas
worker_class = "gevent"
workers      = 1
worker_connections = 100

bind    = f"0.0.0.0:{os.getenv('PORT', '8080')}"
timeout = 120
loglevel = "info"
