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

FROM python:3.9-slim AS build-image
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /code
COPY . /code/
RUN pip install pybuilder
RUN pyb install_dependencies
RUN pyb install


FROM python:3.9-alpine
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /opt/github3api
COPY --from=build-image /code/target/dist/github3api-*/dist/github3api-*.tar.gz /opt/github3api
RUN pip install github3api-*.tar.gz