
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

import unittest
from mock import patch
from mock import mock_open
from mock import call
from mock import Mock

from github3api import GitHubAPI
from github3api.githubapi import DEFAULT_PAGE_SIZE
from github3api.githubapi import GraphqlRateLimitError
from github3api.githubapi import GraphqlError

from datetime import datetime

from requests.exceptions import HTTPError
from requests.exceptions import ChunkedEncodingError

import sys
import logging
logger = logging.getLogger(__name__)

consoleHandler = logging.StreamHandler(sys.stdout)
logFormatter = logging.Formatter("%(asctime)s %(threadName)s %(name)s [%(funcName)s] %(levelname)s %(message)s")
consoleHandler.setFormatter(logFormatter)
rootLogger = logging.getLogger()
rootLogger.addHandler(consoleHandler)
rootLogger.setLevel(logging.DEBUG)


class TestGitHubAPI(unittest.TestCase):

    def setUp(self):

        self.items = [
            {
                'name': 'name1-mid-last1',
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3'
            }, {
                'name': 'name2-mid-last2',
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3.2'
            }, {
                'name': 'name3-med-last3',
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3'
            }, {
                'name': 'name4-mid-last4',
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3'
            }
        ]

    def tearDown(self):

        pass

    def test__get_ratelimit_Should_ReturnExpected_When_NoHeader(self, *patches):
        result = GitHubAPI.get_ratelimit({})
        expected_result = {}
        self.assertEqual(result, expected_result)

    @patch('github3api.githubapi.datetime')
    def test__get_ratelimit_Should_ReturnExpected_When_Header(self, datetime_patch, *patches):
        datetime_patch.now.return_value = datetime(2020, 5, 6, 18, 22, 45, 12065)
        datetime_patch.fromtimestamp.return_value = datetime(2020, 5, 6, 19, 20, 51)
        header = {
            'X-RateLimit-Reset': '1588792851',
            'X-RateLimit-Remaining': '4999',
            'X-RateLimit-Limit': '5000'
        }
        result = GitHubAPI.get_ratelimit(header)
        expected_result = {
            'remaining': '4999',
            'limit': '5000',
            'minutes': '58'
        }
        self.assertEqual(result, expected_result)

    @patch('github3api.githubapi.logger')
    def test__log_ratelimit_Should_CallExpected_When_Called(self, logger_patch, *patches):
        ratelimit = {
            'remaining': '4999',
            'limit': '5000',
            'minutes': '58'
        }
        GitHubAPI.log_ratelimit(ratelimit)
        logger_patch.debug.assert_called_with('4999/5000 resets in 58 min')

    def test__retry_ratelimit_error_Should_Return_False_When_NotHttpError(self, *patches):

        self.assertFalse(GitHubAPI.retry_ratelimit_error(Exception('test')))

    def test__retry_ratelimit_error_Should_Return_False_When_HttpErrorNoStatusCodeMatch(self, *patches):
        response_mock = Mock(status_code=404)
        http_error_mock = HTTPError(Mock())
        http_error_mock.response = response_mock
        self.assertFalse(GitHubAPI.retry_ratelimit_error(http_error_mock))

    def test__retry_ratelimit_error_Should_Return_True_When_Match(self, *patches):
        response_mock = Mock(status_code=403, reason='API Rate Limit Exceeded')
        http_error_mock = HTTPError(Mock())
        http_error_mock.response = response_mock
        self.assertTrue(GitHubAPI.retry_ratelimit_error(http_error_mock))

    def test__retry_ratelimit_error_Should_Return_False_When_403NotRateLimit(self, *patches):
        response_mock = Mock(status_code=403, reason='Forbidden')
        http_error_mock = HTTPError(Mock())
        http_error_mock.response = response_mock
        self.assertFalse(GitHubAPI.retry_ratelimit_error(http_error_mock))

    @patch('github3api.githubapi.GitHubAPI.log_ratelimit')
    @patch('github3api.githubapi.GitHubAPI.get_ratelimit')
    def test__get_response_Should_CallExpected_When_RateLimit(self, get_ratelimit_patch, log_ratelimit_patch, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        response_mock = Mock(headers={'key': 'value'})
        client.get_response(response_mock)
        get_ratelimit_patch.assert_called_once_with(response_mock.headers)
        log_ratelimit_patch.assert_called_once_with(get_ratelimit_patch.return_value)

    @patch('github3api.githubapi.GitHubAPI.log_ratelimit')
    @patch('github3api.githubapi.GitHubAPI.get_ratelimit')
    def test__get_response_Should_CallExpected_When_NoRateLimit(self, get_ratelimit_patch, log_ratelimit_patch, *patches):
        get_ratelimit_patch.return_value = {}
        client = GitHubAPI(bearer_token='bearer-token')
        response_mock = Mock(headers={'key': 'value'})
        client.get_response(response_mock)
        get_ratelimit_patch.assert_called_once_with(response_mock.headers)
        log_ratelimit_patch.assert_not_called()

    def test__get_headers_Should_SetAcceptHeader_When_Called(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        result = client.get_headers()
        self.assertEqual(result['Accept'], 'application/vnd.github.v3+json')

    def test__get_headers_Should_SetAcceptHeader_When_Version(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token', version='v2')
        result = client.get_headers()
        self.assertEqual(result['Accept'], 'application/vnd.github.v2+json')

    def test__get_next_endpoint_Should_ReturnNone_When_NoLinkHeader(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        self.assertIsNone(client._get_next_endpoint(None))

    def test__get_next_endpoint_Should_ReturnExpected_When_CalledWithNextEndpoint(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        link_header = 'https://api.github.com/organizations/27781926/repos?page=4'
        result = client._get_next_endpoint(link_header)
        expected_result = '/organizations/27781926/repos?page=4'
        self.assertEqual(result, expected_result)

    @patch('github3api.githubapi.getenv', return_value='token')
    @patch('github3api.githubapi.GitHubAPI')
    def test__get_client_Should_CallAndReturnExpected_When_Called(self, githubapi_patch, getenv_patch, *patches):
        getenv_patch.side_effect = [
            'url',
            'token'
        ]
        result = GitHubAPI.get_client()
        githubapi_patch.assert_called_once_with(hostname='url', bearer_token='token')
        self.assertEqual(result, githubapi_patch.return_value)

    def test__get_retries_Should_ReturnExpected_When_Called(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        expected_retries = [
            # {
            #     'retry_on_exception': client.retry_chunkedencodingerror_error,
            #     'stop_max_attempt_number': 120,
            #     'wait_fixed': 10000
            # },
            {
                'retry_on_exception': client.retry_ratelimit_error,
                'stop_max_attempt_number': 60,
                'wait_fixed': 60000
            }

        ]
        self.assertEqual(client.retries, expected_retries)

    def test__get_page_from_url_Should_ReturnExpected_When_Match(self, *patches):
        result = GitHubAPI.get_page_from_url('https://api.github.com/user/repos?page=213')
        expected_result = 213
        self.assertEqual(result, expected_result)

    def test__get_page_from_url_Should_ReturnExpected_When_NoMatch(self, *patches):
        result = GitHubAPI.get_page_from_url('https://api.github.com/user/repos')
        self.assertIsNone(result)

    def test__get_per_page_from_url_Should_Return_Expected_When_Match(self, *patches):
        result = GitHubAPI.get_per_page_from_url('https://api.github.com/user/repos?page=213&per_page=75')
        expected_result = 75
        self.assertEqual(result, expected_result)

    def test__get_per_page_from_url_Should_Return_Expected_When_NoMatch(self, *patches):
        result = GitHubAPI.get_per_page_from_url('https://api.github.com/user/repos?page=213')
        expected_result = DEFAULT_PAGE_SIZE
        self.assertEqual(result, expected_result)

    @patch('github3api.GitHubAPI.get')
    def test__get_total_Should_ReturnExpected_When_NoLinks(self, get_patch, *patches):
        response_mock = Mock()
        response_mock.links = {}
        response_mock.json.return_value = ['', '', '']
        get_patch.return_value = response_mock
        client = GitHubAPI(bearer_token='bearer-token')
        result = client.total('/user/repos')
        expected_result = len(response_mock.json.return_value)
        self.assertEqual(result, expected_result)

    @patch('github3api.GitHubAPI.get')
    def test__get_total_Should_ReturnExpected_When_Links(self, get_patch, *patches):
        response1_mock = Mock()
        response1_mock.links = {'next': {'url': 'https://api.github.com/user/repos?page=2', 'rel': 'next'}, 'last': {'url': 'https://api.github.com/user/repos?page=208', 'rel': 'last'}}
        get_patch.side_effect = [response1_mock, ['', '', '']]
        client = GitHubAPI(bearer_token='bearer-token')
        result = client.total('/user/repos')
        expected_result = DEFAULT_PAGE_SIZE * 207 + 3
        self.assertEqual(result, expected_result)

    def test__get_total_Should_RaiseValueError_When_EndpointHasPerPageParameter(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        with self.assertRaises(ValueError):
            client.total('/user/repos?per_page=100')

    @patch('github3api.GitHubAPI.get_per_page_from_url')
    @patch('github3api.GitHubAPI.get_page_from_url')
    @patch('github3api.GitHubAPI.get')
    def test__get_total_Should_CallExpected_When_EndpointHasQueryArguments(self, get_patch, *patches):
        response_mock = Mock()
        response_mock.links = {}
        response_mock.json.return_value = ['', '', '']
        get_patch.return_value = response_mock
        client = GitHubAPI(bearer_token='bearer-token')
        client.total('/user/repos?type=private&direction=asc')
        self.assertTrue(call('/user/repos?type=private&direction=asc&per_page=1', raw_response=True) in get_patch.mock_calls)

    def test__clear_cursor_Should_ReturnExpected_When_NoCursor(self, *patches):
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
        result = GitHubAPI.clear_cursor(query, '')
        expected_result = """
          query ($query: String!, $page_size: Int!, ) {
            search(query: $query, type: REPOSITORY, first: $page_size, ) {
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
        self.assertEqual(result, expected_result)

    def test__clear_cursor_Should_ReturnExpected_When_Cursor(self, *patches):
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
        result = GitHubAPI.clear_cursor(query, '--cursor--')
        self.assertEqual(result, query)

    def test__sanitize_query_Should_ReturnExpected_When_Called(self, *patches):
        query = """
        one
        two
        three
        """
        result = GitHubAPI.sanitize_query(query)
        expected_result = 'one two three'
        self.assertEqual(result, expected_result)

    def test__raise_if_error_Should_RaiseGraphqlRateLimitError_When_Expected(self, *patches):
        response = {
            'errors': [{'type': 'RATE_LIMITED', 'message': 'ratelimit error'}]
        }
        with self.assertRaises(GraphqlRateLimitError):
            GitHubAPI.raise_if_error(response)

    def test__raise_if_error_Should_RaiseGraphqlError_When_Expected(self, *patches):
        response = {
            'errors': [{'type': 'other', 'message': 'other error'}]
        }
        with self.assertRaises(GraphqlError):
            GitHubAPI.raise_if_error(response)

    def test__raise_if_error_Should_DoNothing_When_NoError(self, *patches):
        response = {
            'data': {}
        }
        GitHubAPI.raise_if_error(response)

    def test__get_value_Should_ReturnExpected_When_Called(self, *patches):
        data = {
            'python': {
                'is': {
                    'cool': 'yep'
                }
            }
        }
        keys = 'python.is.cool'
        result = GitHubAPI.get_value(data, keys)
        expected_result = 'yep'
        self.assertEqual(result, expected_result)

    def test__get_value_Should_ReturnKeyError_When_Expected(self, *patches):
        data = {
            'python': {
                'is': {
                    'cool': 'yep'
                }
            }
        }
        keys = 'x.y.z'
        with self.assertRaises(KeyError):
            GitHubAPI.get_value(data, keys)

    def test__get_value_Should_ReturnExpected_When_NoDot(self, *patches):
        data = {
            'cool': 'yep'
        }
        keys = 'cool'
        result = GitHubAPI.get_value(data, keys)
        expected_result = 'yep'
        self.assertEqual(result, expected_result)

    @patch('github3api.GitHubAPI.clear_cursor')
    @patch('github3api.GitHubAPI.raise_if_error')
    @patch('github3api.GitHubAPI.post')
    @patch('github3api.GitHubAPI.get_value')
    def test__get_graphql_page_Should_YieldExpected_When_Called(self, get_value_patch, *patches):
        get_value_patch.side_effect = [
            ['page1', 'page2'],
            {'hasNextPage': True, 'endCursor': 'cursor1'},
            ['page3', 'page4'],
            {'hasNextPage': False}
        ]
        client = GitHubAPI(bearer_token='bearer-token')
        query = '--query--'
        variables = {'key1': 'value1'}
        keys = 'some.keys'
        result = client._get_graphql_page(query, variables, keys)
        self.assertEqual(next(result), ['page1', 'page2'])
        self.assertEqual(next(result), ['page3', 'page4'])
        with self.assertRaises(StopIteration):
            next(result)

    def test__check_graphqlratelimiterror_Should_ReturnTrue_When_Expected(self, *patches):

        self.assertTrue(GitHubAPI.check_graphqlratelimiterror(GraphqlRateLimitError('ratelimit error')))

    def test__check_graphqlratelimiterror_Should_ReturnFalse_When_Expected(self, *patches):

        self.assertFalse(GitHubAPI.check_graphqlratelimiterror(KeyError('key error')))

    @patch('github3api.GitHubAPI.sanitize_query')
    @patch('github3api.GitHubAPI._get_graphql_page')
    def test__graphql_Should_ReturnExpected_When_Page(self, get_graphql_page_patch, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        query = '--query--'
        variables = {'key1': 'value1'}
        keys = 'some.keys'
        result = client.graphql(query, variables, page=True, keys=keys)
        self.assertEqual(result, get_graphql_page_patch.return_value)

    @patch('github3api.GitHubAPI.sanitize_query')
    @patch('github3api.GitHubAPI.clear_cursor')
    @patch('github3api.GitHubAPI.raise_if_error')
    @patch('github3api.GitHubAPI.post')
    def test__graphql_Should_ReturnExpected_When_Called(self, post_patch, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        query = '--query--'
        variables = {'key1': 'value1'}
        result = client.graphql(query, variables)
        self.assertEqual(result, post_patch.return_value)
