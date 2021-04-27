
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

from rest3client import RESTclient
from requests.exceptions import HTTPError
from requests.exceptions import ChunkedEncodingError

logger = logging.getLogger(__name__)

logging.getLogger('urllib3.connectionpool').setLevel(logging.CRITICAL)

HOSTNAME = 'api.github.com'
VERSION = 'v3'
DEFAULT_PAGE_SIZE = 30


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
    def _retry_chunkedencodingerror_error(exception):
        """ return True if exception is ChunkedEncodingError, False otherwise
            retry:
                wait_fixed:10000
                stop_max_attempt_number:120
        """
        logger.debug(f"checking if '{type(exception).__name__}' exception is a ChunkedEncodingError error")
        if isinstance(exception, ChunkedEncodingError):
            logger.info('ratelimit error encountered - retrying request in 10 seconds')
            return True
        logger.debug(f'exception is not a ratelimit error: {exception}')
        return False
