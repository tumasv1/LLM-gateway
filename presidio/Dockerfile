# Учебный Analyzer: тот же Presidio 2.2.364 + Python-recognizers РФ.
# spaCy-ru не ставим: LiteLLM шлёт language=en, лишняя модель только жрёт RAM LXC.
FROM ghcr.io/data-privacy-stack/presidio-analyzer:2.2.364

USER root
COPY ru_pdn /app/ru_pdn
COPY entrypoint.sh /app/ru_pdn-entrypoint.sh
RUN chmod 755 /app/ru_pdn-entrypoint.sh

ENV PYTHONPATH=/app

USER 1001
ENTRYPOINT ["/app/ru_pdn-entrypoint.sh"]
