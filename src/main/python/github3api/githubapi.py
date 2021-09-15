
# Copyright (c) 2020 Intel Corporation

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import logging
from os import getenv
from datetime import datetime

from retrying import retry
from rest3client import RESTclient
from requests.exceptions import HTTPError
from requests.exceptions import ChunkedEncodingError

logger = logging.getLogger(__name__)

logging.getLogger('urllib3.connectionpool').setLevel(logging.CRITICAL)

HOSTNAME = 'api.github.com'
VERSION = 'v3'
DEFAULT_PAGE_SIZE = 30
DEFAULT_GRAPHQL_PAGE_SIZE = 100


class GraphqlRateLimitError(Exception):
    """ GraphQL Rate Limit Error
    """
    pass


class GraphqlError(Exception):
    """ GraphQL Error
    """
    pass


class GitHubAPI(RESTclient):
    """ An advanced REST client for the GitHub API
    """

    def __init__(self, **kwargs):
        logger.debug('executing GitHubAPI constructor')
        hostname = kwargs.pop('hostname', HOSTNAME)
        self.version = kwargs.pop('version', VERSION)
        super(GitHubAPI, self).__init__(hostname, **kwargs)

    def get_response(self, response, **kwargs):
        """ subclass override to including logging of ratelimits
        """
        ratelimit = GitHubAPI.get_ratelimit(response.headers)
        if ratelimit:
            self.log_ratelimit(ratelimit)
        return super(GitHubAPI, self).get_response(response, **kwargs)

    def get_headers(self, **kwargs):
        """ return headers to pass to requests method
        """
        headers = super(GitHubAPI, self).get_headers(**kwargs)
        headers['Accept'] = f'application/vnd.github.{self.version}+json'
        return headers

    def _get_next_endpoint(self, url):
        """ return next endpoint
        """
        if not url:
            logger.debug('link header is empty')
            return
        endpoint = self.get_endpoint_from_url(url)
        logger.debug(f'next endpoint is: {endpoint}')
        return endpoint

    def _get_all(self, endpoint, **kwargs):
        """ return all pages from endpoint
        """
        logger.debug(f'get items from: {endpoint}')
        items = []
        while True:
            url = None
            response = super(GitHubAPI, self).get(endpoint, raw_response=True, **kwargs)
            if response:
                data = response.json()
                if isinstance(data, list):
                    items.extend(response.json())
                else:
                    items.append(data)
                url = response.links.get('next', {}).get('url')

            endpoint = self._get_next_endpoint(url)
            if not endpoint:
                logger.debug('no more pages to retrieve')
                break

        return items

    def _get_page(self, endpoint, **kwargs):
        """ return generator that yields pages from endpoint
        """
        while True:
            response = super(GitHubAPI, self).get(endpoint, raw_response=True, **kwargs)
            yield response.json()
            endpoint = self._get_next_endpoint(response.links.get('next', {}).get('url'))
            if not endpoint:
                logger.debug('no more pages')
                break

    def get(self, endpoint, **kwargs):
        """ ovverride get to provide paging support
        """
        directive = kwargs.pop('_get', None)
        attributes = kwargs.pop('_attributes', None)
        if directive == 'all':
            items = self._get_all(endpoint, **kwargs)
            return GitHubAPI.match_keys(items, attributes)
        elif directive == 'page':
            return self._get_page(endpoint, **kwargs)
        else:
            return super(GitHubAPI, self).get(endpoint, **kwargs)

    def total(self, endpoint):
        """ return total number of resources
        """
        # logger.debug(f'get total number of resources at endpoint {endpoint}')
        if 'per_page' in endpoint:
            raise ValueError(f'endpoint {endpoint} with per_page argument is not supported')
        if '?' in endpoint:
            endpoint = f'{endpoint}&per_page=1'
        else:
            endpoint = f'{endpoint}?per_page=1'
        response = self.get(endpoint, raw_response=True)
        if response.links:
            last_url = response.links['last']['url']
            endpoint = self.get_endpoint_from_url(last_url)
            items = self.get(endpoint)
            per_page = GitHubAPI.get_per_page_from_url(last_url)
            last_page = GitHubAPI.get_page_from_url(last_url)
            total = per_page * (last_page - 1) + len(items)
        else:
            items = response.json()
            total = len(items)
        return total

    def get_endpoint_from_url(self, url):
        """ return endpoint from url
        """
        return url.replace(f'https://{self.hostname}', '')

    @staticmethod
    def get_page_from_url(url):
        """ get page query parameter form url
        """
        regex = r'^.*page=(?P<value>\d+).*$'
        match = re.match(regex, url)
        if match:
            return int(match.group('value'))

    @staticmethod
    def get_per_page_from_url(url):
        """ get per_page query parameter from url
        """
        per_page = DEFAULT_PAGE_SIZE
        regex = r'^.*per_page=(?P<value>\d+).*$'
        match = re.match(regex, url)
        if match:
            per_page = int(match.group('value'))
        return per_page

    @classmethod
    def get_client(cls):
        """ return instance of GitHubAPI
        """
        return GitHubAPI(
            hostname=getenv('GH_BASE_URL', HOSTNAME),
            bearer_token=getenv('GH_TOKEN_PSW'))

    @staticmethod
    def get_ratelimit(headers):
        """ get rate limit data
        """
        reset = headers.get('X-RateLimit-Reset')
        if not reset:
            return {}
        remaining = headers.get('X-RateLimit-Remaining')
        limit = headers.get('X-RateLimit-Limit')
        delta = datetime.fromtimestamp(int(reset)) - datetime.now()
        minutes = str(delta.total_seconds() / 60).split('.')[0]
        return {
            'remaining': remaining,
            'limit': limit,
            'minutes': minutes
        }

    @staticmethod
    def log_ratelimit(ratelimit):
        """ log rate limit data
        """
        logger.debug(f"{ratelimit['remaining']}/{ratelimit['limit']} resets in {ratelimit['minutes']} min")

    @staticmethod
    def match_keys(items, attributes):
        """ return list of items with matching keys from list of attributes
        """
        if not attributes:
            return items
        matched_items = []
        for item in items:
            matched_items.append({
                key: item[key] for key in attributes if key in item
            })
        return matched_items

    @staticmethod
    def retry_ratelimit_error(exception):
        """ return True if exception is 403 HTTPError, False otherwise
            retry:
                wait_fixed:60000
                stop_max_attempt_number:60
        """
        logger.debug(f"checking if '{type(exception).__name__}' exception is a ratelimit error")
        if isinstance(exception, HTTPError):
            if exception.response.status_code == 403:
                logger.info('ratelimit error encountered - retrying request in 60 seconds')
                return True
        logger.debug(f'exception is not a ratelimit error: {exception}')
        return False

    @staticmethod
    def clear_cursor(query, cursor):
        """ return query with all cursor references removed if no cursor
        """
        if not cursor:
            query = query.replace('after: $cursor', '')
            query = query.replace('$cursor: String!', '')
        return query

    @staticmethod
    def sanitize_query(query):
        """ sanitize query
        """
        return query.replace('\n', ' ').replace('  ', '').strip()

    @staticmethod
    def raise_if_error(response):
        """ raise GraphqlRateLimitError if error exists in errors
        """
        if 'errors' in response:
            logger.debug(f'errors detected in graphql response: {response}')
            for error in response['errors']:
                if error.get('type', '') == 'RATE_LIMITED':
                    raise GraphqlRateLimitError(error.get('message', ''))
            raise GraphqlError(response['errors'][0]['message'])

    @staticmethod
    def get_value(data, keys):
        """ return value represented by keys dot notated string from data dictionary
        """
        if '.' in keys:
            key, rest = keys.split('.', 1)
            if key in data:
                return GitHubAPI.get_value(data[key], rest)
            raise KeyError(f'dictionary does not have key {key}')
        else:
            return data[keys]

    def _get_graphql_page(self, query, variables, keys):
        """ return generator that yields page from graphql response
        """
        variables['page_size'] = DEFAULT_GRAPHQL_PAGE_SIZE
        variables['cursor'] = ''
        while True:
            updated_query = GitHubAPI.clear_cursor(query, variables['cursor'])
            response = self.post('/graphql', json={'query': updated_query, 'variables': variables})
            GitHubAPI.raise_if_error(response)
            yield GitHubAPI.get_value(response, f'{keys}.edges')

            page_info = GitHubAPI.get_value(response, f'{keys}.pageInfo')
            has_next_page = page_info['hasNextPage']
            if not has_next_page:
                logger.debug('no more pages')
                break
            variables['cursor'] = page_info['endCursor']

    def check_graphqlratelimiterror(exception):
        """ return True if exception is GraphQL Rate Limit Error, False otherwise
        """
        logger.debug(f"checking if '{type(exception).__name__}' exception is a GraphqlRateLimitError")
        if isinstance(exception, (GraphqlRateLimitError, TypeError)):
            logger.debug('exception is a GraphqlRateLimitError - retrying request in 60 seconds')
            return True
        logger.debug(f'exception is not a GraphqlRateLimitError: {exception}')
        return False

    @retry(retry_on_exception=check_graphqlratelimiterror, wait_fixed=60000, stop_max_attempt_number=60)
    def graphql(self, query, variables, page=False, keys=None):
        """ execute graphql query and return response or paged response if page is True
        """
        query = GitHubAPI.sanitize_query(query)
        if page:
            response = self._get_graphql_page(query, variables, keys)
        else:
            updated_query = GitHubAPI.clear_cursor(query, variables.get('cursor'))
            response = self.post('/graphql', json={'query': updated_query, 'variables': variables})
            GitHubAPI.raise_if_error(response)
        return response

    check_graphqlratelimiterror = staticmethod(check_graphqlratelimiterror)
