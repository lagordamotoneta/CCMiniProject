FROM python:3.7-alpine
WORKDIR /miniProject
COPY . /miniProject
RUN pip install -U -r requirements.txt
EXPOSE 8080
CMD ["python", "app.py"]
