FROM python:3-slim

COPY app /workspace/app/app
COPY setup.py /workspace/app/

WORKDIR /workspace/app
RUN pip install .

ENV FLASK_APP=app
CMD [ "flask", "run", "--host=0.0.0.0" ]
