FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 doce
COPY --chown=doce:doce . /app
RUN mkdir -p /data/dados /data/midia && chown -R doce:doce /data
USER doce
ENV CONFEITARIA_DATA_DIR=/data/dados CONFEITARIA_MEDIA_DIR=/data/midia
EXPOSE 8080
CMD ["python", "mobile.py", "--endereco", "0.0.0.0", "--porta", "8080"]
