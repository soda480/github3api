#
# Copyright (c) 2020 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-slim AS build-image
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /code
COPY . /code/
RUN pip install --upgrade pip && pip install pybuilder
RUN pyb -X && pyb install

FROM python:${PYTHON_VERSION}-slim
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /opt/github3api
COPY --from=build-image /code/target/dist/github3api-*/dist/github3api-*.tar.gz /opt/github3api
RUN pip install github3api-*.tar.gz