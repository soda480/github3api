
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

logger = logging.getLogger(__name__)

logging.getLogger('urllib3.connectionpool').setLevel(logging.CRITICAL)

HOSTNAME = 'api.github.com'
WAIT_FIXED = 60000
MAX_ATTEMPTS = 60


class GitHubAPI(RESTclient):
    """ An advanced REST client for the GitHub API
    """

    def __init__(self, hostname, **kwargs):
        logger.debug('executing GitHubAPI constructor')
        retries = GitHubAPI.get_retries(kwargs)
        super(GitHubAPI, self).__init__(hostname, retries=retries, **kwargs)

    def get_response(self, response, **kwargs):
        """ subclass override to including logging of ratelimits
        """
        GitHubAPI.log_ratelimit(response.headers)
        return super(GitHubAPI, self).get_response(response, **kwargs)

    def get_headers(self, **kwargs):
        """ return headers to pass to requests method
        """
        headers = super(GitHubAPI, self).get_headers(**kwargs)
        headers['Accept'] = 'application/vnd.github.v3+json'
        return headers

    def _get_next_endpoint(self, link_header):
        """ return next endpoint from link header
        """
        if not link_header:
            logger.debug('link header is empty')
            return
        regex = fr".*<https://{self.hostname}(?P<endpoint>/.*?)>; rel=\"next\".*"
        match = re.match(regex, link_header)
        if match:
            endpoint = match.group('endpoint')
            logger.debug(f'found next endpoint in link header: {endpoint}')
            return endpoint
        logger.debug('next endpoints not found in link header')

    def _get_all(self, endpoint, **kwargs):
        """ return all pages from endpoint
        """
        logger.debug(f'get items from: {endpoint}')
        items = []
        while True:
            link_header = None
            response = super(GitHubAPI, self).get(endpoint, raw_response=True, **kwargs)
            if response:
                data = response.json()
                if isinstance(data, list):
                    items.extend(response.json())
                else:
                    items.append(data)
                link_header = response.headers.get('Link')

            endpoint = self._get_next_endpoint(link_header)
            if not endpoint:
                logger.debug('no more pages to retrieve')
                break

        return items

    def _get_page(self, endpoint, **kwargs):
        """ return generator that yields pages from endpoint
        """
        while True:
            response = super(GitHubAPI, self).get(endpoint, raw_response=True, **kwargs)
            for page in response.json():
                yield page
            endpoint = self._get_next_endpoint(response.headers.get('Link'))
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

    @classmethod
    def log_ratelimit(cls, headers):
        """ convert and log rate limit data
        """
        reset = headers.get('X-RateLimit-Reset')
        if not reset:
            return
        remaining = headers.get('X-RateLimit-Remaining')
        limit = headers.get('X-RateLimit-Limit')
        delta = datetime.fromtimestamp(int(reset)) - datetime.now()
        minutes = str(delta.total_seconds() / 60).split('.')[0]
        logger.debug(f'{remaining}/{limit} resets in {minutes} min')

    @classmethod
    def get_client(cls):
        """ return instance of GitHubAPI
        """
        return GitHubAPI(
            getenv('GH_BASE_URL', HOSTNAME),
            bearer_token=getenv('GH_TOKEN_PSW'))

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
    def is_ratelimit_error(exception):
        """ return True if exception is 403 HTTPError, False otherwise
        """
        logger.debug(f'checking exception for retry candidacy: {type(exception).__name__}')
        if isinstance(exception, HTTPError):
            if exception.response.status_code == 403:
                logger.info('ratelimit error - retrying request in 10 seconds')
                return True
        return False

    @staticmethod
    def get_retries(kwargs):
        """ return retries
        """
        retries = []
        wait_fixed = kwargs.pop('wait_fixed', WAIT_FIXED)
        max_attempts = kwargs.pop('max_attempts', MAX_ATTEMPTS)
        retries.append({
            'retry_on_exception': GitHubAPI.is_ratelimit_error,
            'wait_fixed': wait_fixed,
            'stop_max_attempt_number': max_attempts
        })
        retries.extend(kwargs.pop('retries', []))
        return retries
