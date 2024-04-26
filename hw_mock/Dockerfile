# Python runtime
FROM python:3.10

# Working dir
WORKDIR /code

# copy req libs
COPY ./requirements.txt /code/requirements.txt

# install req libs
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# copy all files
COPY . /code

# run .py script
CMD uvicorn conn_hw_mock_api:app --host 0.0.0.0 --port ${HW_MOCK_API_PORT}