
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

    def test__match_keys_Should_Return_Items_When_NoAttributes(self, *patches):
        result = GitHubAPI.match_keys(self.items, None)
        self.assertEqual(result, self.items)

    def test__match_keys_Should_ReturnExpected_When_Called(self, *patches):
        result = GitHubAPI.match_keys(self.items, ['name', 'key1'])
        expected_result = [
            {
                'name': 'name1-mid-last1',
                'key1': 'value1'
            }, {
                'name': 'name2-mid-last2',
                'key1': 'value1'
            }, {
                'name': 'name3-med-last3',
                'key1': 'value1'
            }, {
                'name': 'name4-mid-last4',
                'key1': 'value1'
            }
        ]
        self.assertEqual(result, expected_result)

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

    def test__retry_ratelimit_error_Should_Return_True_When_HttpErrorNoStatusCodeMatch(self, *patches):
        response_mock = Mock(status_code=404)
        http_error_mock = HTTPError(Mock())
        http_error_mock.response = response_mock
        self.assertFalse(GitHubAPI.retry_ratelimit_error(http_error_mock))

    def test__retry_ratelimit_error_Should_Return_True_When_Match(self, *patches):
        response_mock = Mock(status_code=403)
        http_error_mock = HTTPError(Mock())
        http_error_mock.response = response_mock
        self.assertTrue(GitHubAPI.retry_ratelimit_error(http_error_mock))

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

    @patch('github3api.GitHubAPI._get_next_endpoint')
    @patch('github3api.githubapi.RESTclient.get')
    def test__get_all_Should_ReturnExpected_When_GetReturnsList(self, get_patch, get_next_endpoint_patch, *patches):
        response_mock1 = Mock()
        response_mock1.json.return_value = ['item1', 'item2']
        response_mock2 = Mock()
        response_mock2.json.return_value = ['item3', 'item4']
        get_patch.side_effect = [
            response_mock1,
            response_mock2
        ]
        get_next_endpoint_patch.side_effect = [
            {'Link': 'link-header-value'},
            {}
        ]
        client = GitHubAPI(bearer_token='bearer-token')
        result = client._get_all('/repos/edgexfoundry/cd-management/milestones')
        expected_result = ['item1', 'item2', 'item3', 'item4']
        self.assertEqual(result, expected_result)

    @patch('github3api.GitHubAPI._get_next_endpoint')
    @patch('github3api.githubapi.RESTclient.get')
    def test__get_all_Should_ReturnExpected_When_GetReturnsDict(self, get_patch, get_next_endpoint_patch, *patches):
        response_mock1 = Mock()
        response_mock1.json.return_value = {'key1': 'value1'}
        response_mock2 = Mock()
        response_mock2.json.return_value = {'key2': 'value2'}
        get_patch.side_effect = [
            response_mock1,
            response_mock2
        ]
        get_next_endpoint_patch.side_effect = [
            {'Link': 'link-header-value'},
            {}
        ]
        client = GitHubAPI(bearer_token='bearer-token')
        result = client._get_all('/repos/edgexfoundry/cd-management/milestones')
        expected_result = [{'key1': 'value1'}, {'key2': 'value2'}]
        self.assertEqual(result, expected_result)

    @patch('github3api.GitHubAPI._get_next_endpoint')
    @patch('github3api.githubapi.RESTclient.get')
    def test__get_all_Should_ReturnEmptyList_When_NoResponse(self, get_patch, get_next_endpoint_patch, *patches):
        get_patch.side_effect = [
            None
        ]
        get_next_endpoint_patch.side_effect = [
            None
        ]
        client = GitHubAPI(bearer_token='bearer-token')
        result = client._get_all('/repos/edgexfoundry/cd-management/milestones')
        expected_result = []
        self.assertEqual(result, expected_result)

    @patch('github3api.GitHubAPI._get_next_endpoint')
    @patch('github3api.githubapi.RESTclient.get')
    def test__get_page_Should_ReturnExpected_When_Called(self, get_patch, get_next_endpoint_patch, *patches):
        response_mock1 = Mock()
        response_mock1.json.return_value = [
            'page1',
            'page2'
        ]
        response_mock2 = Mock()
        response_mock2.json.return_value = [
            'page3',
            'page4'
        ]
        get_patch.side_effect = [
            response_mock1,
            response_mock2
        ]
        get_next_endpoint_patch.return_value = [
            'next-endpoint',
            'next-endpoint'
        ]
        client = GitHubAPI(bearer_token='bearer-token')
        result = client._get_page('endpoint')
        self.assertEqual(next(result), ['page1', 'page2'])
        self.assertEqual(next(result), ['page3', 'page4'])
        with self.assertRaises(StopIteration):
            next(result)

    @patch('github3api.GitHubAPI._get_next_endpoint')
    @patch('github3api.githubapi.RESTclient.get')
    def test__get_page_Should_ReturnExpected_When_NoEndpoint(self, get_patch, get_next_endpoint_patch, *patches):
        response_mock1 = Mock()
        response_mock1.json.return_value = [
            'page1',
            'page2'
        ]
        get_patch.side_effect = [
            response_mock1
        ]
        get_next_endpoint_patch.side_effect = [
            None
        ]
        client = GitHubAPI(bearer_token='bearer-token')
        result = client._get_page('endpoint')
        self.assertEqual(next(result), ['page1', 'page2'])
        with self.assertRaises(StopIteration):
            next(result)

    @patch('github3api.GitHubAPI.match_keys')
    @patch('github3api.GitHubAPI._get_all')
    def test__get_Should_CallExpected_When_AllDirective(self, get_all_patch, match_keys_patch, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        endpoint = '/repos/edgexfoundry/cd-management/milestones'
        attributes = ['key1', 'key2']
        result = client.get(endpoint, _get='all', _attributes=attributes)
        get_all_patch.assert_called_once_with(endpoint)
        match_keys_patch.assert_called_once_with(get_all_patch.return_value, attributes)
        self.assertEqual(result, match_keys_patch.return_value)

    @patch('github3api.GitHubAPI._get_page')
    def test__get_Should_CallExpected_When_GenDirective(self, get_page_patch, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        endpoint = '/repos/edgexfoundry/cd-management/milestones'
        result = client.get(endpoint, _get='page')
        get_page_patch.assert_called_once_with(endpoint)
        self.assertEqual(result, get_page_patch.return_value)

    @patch('github3api.githubapi.RESTclient.get')
    def test__get_Should_CallExpected_When_NoDirective(self, get_patch, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        endpoint = '/repos/edgexfoundry/cd-management/milestones'
        result = client.get(endpoint, k1='v1', k2='v2')
        get_patch.assert_called_once_with(endpoint, k1='v1', k2='v2')
        self.assertEqual(result, get_patch.return_value)

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

    def test__retry_chunkedencodingerror_error_Should_Return_False_When_NotChunkEncodingError(self, *patches):

        self.assertFalse(GitHubAPI._retry_chunkedencodingerror_error(Exception('test')))

    def test__retry_chunkedencodingerror_error_Should_Return_True_When_ChunkEncodingError(self, *patches):

        self.assertTrue(GitHubAPI._retry_chunkedencodingerror_error(ChunkedEncodingError()))

    def test__get_endpoint_from_url_Should_ReturnExpected_When_Called(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        result = client.get_endpoint_from_url('https://api.github.com/user/repos?page=2')
        expected_result = '/user/repos?page=2'
        self.assertEqual(result, expected_result)

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

    def test__get_total_Should_RaiseValueError_When_EndpointHasQueryParameter(self, *patches):
        client = GitHubAPI(bearer_token='bearer-token')
        with self.assertRaises(ValueError):
            client.total('/user/repos?per_page=100')
