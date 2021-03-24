[![GitHub Workflow Status](https://github.com/soda480/github3api/workflows/build/badge.svg)](https://github.com/soda480/github3api/actions)
[![Code Coverage](https://codecov.io/gh/soda480/github3api/branch/master/graph/badge.svg)](https://codecov.io/gh/soda480/github3api)
[![Code Grade](https://www.code-inspector.com/project/13337/status/svg)](https://frontend.code-inspector.com/project/13337/dashboard)
[![PyPI version](https://badge.fury.io/py/github3api.svg)](https://badge.fury.io/py/github3api)

# github3api #
An advanced REST client for the GitHub API. It is a subclass of [rest3client](https://pypi.org/project/rest3client/) tailored for the GitHub API with special optional directives for GET requests that can return all pages from an endpoint or return a generator that can be iterated over. By default all requests will be retried if ratelimit request limit is reached.


### Installation ###
```bash
pip install github3api
```

### Example Usage ###

```python
>>> from github3api import GitHubAPI
```

`GitHubAPI` instantiation
```python
# instantiate using no-auth
>>> client = GitHubAPI()

# instantiate using a token
>>> client = GitHubAPI(bearer_token='****************')
```

`GET` request
```python
# GET request - return JSON response
>>> client.get('/rate_limit')['resources']['core']
{'limit': 60, 'remaining': 37, 'reset': 1588898701}

# GET request - return raw resonse
>>> client.get('/rate_limit', raw_response=True)
<Response [200]>
```

`POST` request
```python
>>> client.post('/user/repos', json={'name': 'test-repo1'})['full_name']
'soda480/test-repo1'

>>> client.post('/repos/soda480/test-repo1/labels', json={'name': 'label1', 'color': '#006b75'})['url']
'https://api.github.com/repos/soda480/test-repo1/labels/label1'
```

`PATCH` request
```python
>>> client.patch('/repos/soda480/test-repo1/labels/label1', json={'description': 'my label'})['url']
'https://api.github.com/repos/soda480/test-repo1/labels/label1'
```

`DELETE` request
```python 
>>> client.delete('/repos/soda480/test-repo1')
```

`GET all` directive - Get all pages from an endpoint and return list containing only matching attributes
```python
for repo in client.get('/user/repos', _get='all', _attributes=['full_name']):
    print(repo['full_name'])
```

`GET page` directive - Yield a page from endpoint
```python
for repo in client.get('/user/repos', _get='page'):
    print(repo['full_name'])
```

### Projects using `github3api` ###

* [edgexfoundry/sync-github-labels](https://github.com/edgexfoundry/cd-management/tree/git-label-sync) A script that synchronizes GitHub labels and milestones

* [edgexfoundry/prune-github-tags](https://github.com/edgexfoundry/cd-management/tree/prune-github-tags) A script that prunes GitHub pre-release tags

* [edgexfoundry/create-github-release](https://github.com/edgexfoundry/cd-management/tree/create-github-release) A script to facilitate creation of GitHub releases


### Development ###

Ensure the latest version of Docker is installed on your development server. Fork and clone the repository.

Build the Docker image:
```sh
docker image build \
--target build-image \
--build-arg http_proxy \
--build-arg https_proxy \
-t \
github3api:latest .
```

Run the Docker container:
```sh
docker container run \
--rm \
-it \
-e http_proxy \
-e https_proxy \
-v $PWD:/github3api \
github3api:latest \
/bin/sh
```

Execute the build:
```sh
pyb -X
```

NOTE: commands above assume working behind a proxy, if not then the proxy arguments to both the docker build and run commands can be removed.
