FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir /data && chown nobody:nogroup /data
ENV DB_PATH=/data/messages.db PORT=8000
VOLUME /data
EXPOSE 8000
USER nobody
CMD ["python", "-m", "app.server"]