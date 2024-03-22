# github3api
[![GitHub Workflow Status](https://github.com/soda480/github3api/workflows/build/badge.svg)](https://github.com/soda480/github3api/actions)
[![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://pybuilder.io/)
[![complexity](https://img.shields.io/badge/complexity-A-brightgreen)](https://radon.readthedocs.io/en/latest/api.html#module-radon.complexity)
[![vulnerabilities](https://img.shields.io/badge/vulnerabilities-None-brightgreen)](https://pypi.org/project/bandit/)
[![PyPI version](https://badge.fury.io/py/github3api.svg)](https://app.codiga.io/public/project/13337/github3api/dashboard)
[![python](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9%20%7C%203.10-teal)](https://www.python.org/downloads/)

An advanced REST client for the GitHub API. It is a subclass of [rest3client](https://pypi.org/project/rest3client/) tailored for the GitHub API with special optional directives for GET requests that can return all pages from an endpoint or return a generator that can be iterated over (for paged requests). By default all requests will be retried if ratelimit request limit is reached.

Support for executing Graphql queries including paging; Graphql queries are also retried if Graphql rate limiting occurs.


### Installation
```bash
pip install github3api
```

### Example Usage

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

>>> client.post('/repos/soda480/test-repo1/labels', json={'name': 'label1'})['url']
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
for repo in client.get('/orgs/edgexfoundry/repos', _get='all', _attributes=['full_name']):
    print(repo['full_name'])
```

`GET page` directive - Yield a page from endpoint
```python
for page in client.get('/user/repos', _get='page'):
    for repo in page:
        print(repo['full_name'])
```

`total` - Get total number of resources at given endpoint
```python
print(client.total('/user/repos'))
```

`graphql` - execute graphql query
```python
query = """
  query($query:String!, $page_size:Int!) {
    search(query: $query, type: REPOSITORY, first: $page_size) {
      repositoryCount
      edges {
        node {
          ... on Repository {
            nameWithOwner
          }
        }
      }
    }
  }
"""
variables = {"query": "org:edgexfoundry", "page_size":100}
client.graphql(query, variables)
```

`graphql paging` - execute paged graphql query
```python
query = """
  query ($query: String!, $page_size: Int!, $cursor: String!) {
    search(query: $query, type: REPOSITORY, first: $page_size, after: $cursor) {
      repositoryCount
      pageInfo {
        endCursor
        hasNextPage
      }
      edges {
        cursor
        node {
          ... on Repository {
            nameWithOwner
          }
        }
      }
    }
  }
"""
variables = {"query": "org:edgexfoundry", "page_size":100}
for page in client.graphql(query, variables, page=True, keys='data.search'):
    for repo in page:
        print(repo['node']['nameWithOwner'])
```

For Graphql paged queries:
- the query should include the necessary pageInfo and cursor attributes
- the keys method argument is a dot annotated string that is used to access the resulting dictionary response object
- the query is retried every 60 seconds (for up to an hour) if a ratelimit occur

### Projects using `github3api`

* [edgexfoundry/sync-github-labels](https://github.com/edgexfoundry/cd-management/tree/git-label-sync) A script that synchronizes GitHub labels and milestones

* [edgexfoundry/prune-github-tags](https://github.com/edgexfoundry/cd-management/tree/prune-github-tags) A script that prunes GitHub pre-release tags

* [edgexfoundry/create-github-release](https://github.com/edgexfoundry/cd-management/tree/create-github-release) A script to facilitate creation of GitHub releases

* [soda480/prepbadge](https://github.com/soda480/prepbadge) A script that creates multiple pull request workflows to update a target organization repos with badges

* [soda480/github-contributions](https://github.com/soda480/github-contributions) A script to get contribution metrics for all members of a GitHub organization using the GitHub GraphQL API

* [edgexfoundry/edgex-dev-badge](https://github.com/edgexfoundry/edgex-dev-badge) Rules based GitHub badge scanner

### Development

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
-v $PWD:/code \
github3api:latest \
bash
```

Execute the build:
```sh
pyb -X
```

NOTE: commands above assume working behind a proxy, if not then the proxy arguments to both the docker build and run commands can be removed.
