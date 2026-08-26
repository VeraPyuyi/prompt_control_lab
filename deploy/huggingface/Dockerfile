FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PCL_DEPLOYMENT_MODE=hf_demo \
    PCL_UI_LANGUAGE=zh \
    PCL_UI_RUNS=/tmp/prompt_control_lab \
    PCL_UI_DEFAULT_VIEW=before \
    PCL_HF_DEMO_SOURCE=/app/demo_runs

WORKDIR /app

COPY wheels /tmp/pcl-wheels
RUN WHEEL="$(find /tmp/pcl-wheels -maxdepth 1 -name 'promptcontrollab-*.whl' -print -quit)" \
    && test -n "$WHEEL" \
    && python -m pip install --no-cache-dir "${WHEEL}[ui,research]" \
    && rm -rf /tmp/pcl-wheels

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /tmp/prompt_control_lab \
    && chown -R appuser:appuser /tmp/prompt_control_lab /app

COPY --chown=appuser:appuser app.py README.md space_manifest.json /app/
COPY --chown=appuser:appuser demo_runs /app/demo_runs

USER appuser
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/_stcore/health', timeout=3)"

CMD ["python", "-m", "streamlit", "run", "/app/app.py", "--server.address=0.0.0.0", "--server.port=7860", "--server.headless=true", "--server.maxUploadSize=5", "--browser.gatherUsageStats=false", "--client.toolbarMode=viewer"]
