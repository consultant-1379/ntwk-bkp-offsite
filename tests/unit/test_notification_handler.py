#!/usr/bin/env python
##############################################################################
# COPYRIGHT Ericsson AB 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For import error, invalid name and protected access (testing private methods)
# pylint: disable=E0401,C0103,W0212

"""
This module is for unit testing NotificationHandler class from backup_settings.py script
"""

import unittest
import logging
import mock

from network_backup_offsite import __version__
from network_backup_offsite.exceptions import NotificationHandlerException
from network_backup_offsite.notification_handler import NotificationHandler
from requests import RequestException

MOCK_LOGGER = 'network_backup_offsite.notification_handler.CustomLogger'
MOCK_REQUEST_POST = 'network_backup_offsite.notification_handler.requests.post'
MOCK_GET_CLI_ARGUMENTS = 'network_backup_offsite.notification_handler.NotificationHandler.' \
                         '_get_cli_arguments_into_email_body'

CLI_ARGUMENTS = "network_bkp_offsite ran with the following arguments:<br>{}<br>" \
    .format(['--script_option', '1', '--customer_name', 'CUSTOMER_0'])

OUTPUT_LINE = "===================================================================================="

logging.disable(logging.CRITICAL)


class NotificationHandlerSendEmailTestCase(unittest.TestCase):
    """Class for testing send_mail function from backup.notification_handler.py script."""

    @classmethod
    def setUp(cls):
        """
        Setup for the tests
        """
        cls.email_to = 'mock@email'
        cls.email_url = 'http://mock'
        cls.from_name = 'mock'
        cls.email_from = cls.from_name + '@ericsson.com'
        cls.subject = 'mock_subject'
        cls.message = 'mock_message'

        with mock.patch(MOCK_LOGGER) as logger:
            cls.handler = NotificationHandler(cls.email_to, cls.email_url, logger)

    @mock.patch(MOCK_REQUEST_POST)
    def test_send_email_sending(self, mock_post):
        """Test to check the log to notify about the attempt to send the email is generated."""
        mock_post.return_value.status_code = 200

        result = self.handler.send_mail(self.from_name, self.subject, self.message)

        self.handler.logger.log_info.assert_called_with("Sending e-mail from mock@ericsson.com to "
                                                        "mock@email with subject 'mock_subject'.")
        self.handler.logger.info.assert_called_with("E-mail sent successfully to: 'mock@email'.")
        self.assertTrue(result)

    def test_send_email_empty_deployment_name(self):
        """Test to check if deployment name is not provided."""
        with self.assertRaises(Exception) as cex:
            self.handler.send_mail("", self.subject, self.message)

        self.assertEqual(cex.exception.message, "An empty sender was informed.")

    @mock.patch(MOCK_REQUEST_POST)
    def test_send_email_bad_response(self, mock_post):
        """Test to check the return value if the email was not sent due to bad response."""
        mock_post.return_value.raise_for_status.side_effect = RequestException

        with self.assertRaises(NotificationHandlerException) as cex:
            self.handler.send_mail(self.from_name, self.subject, self.message)

        self.assertRegexpMatches(cex.exception.message, "Failed to send e-mail to")

    @mock.patch(MOCK_REQUEST_POST)
    def test_send_email_sending_with_other_domain(self, mock_post):
        """Asserts if the domain is changed from default."""
        with mock.patch(MOCK_LOGGER) as logger:
            self.handler = NotificationHandler(self.email_to, self.email_url, logger, "mock_domain")

        mock_post.return_value.status_code = 200

        result = self.handler.send_mail(self.from_name, self.subject, self.message)

        self.handler.logger.log_info.assert_called_with("Sending e-mail from mock@mock_domain to "
                                                        "mock@email with subject 'mock_subject'.")
        self.handler.logger.info.assert_called_with("E-mail sent successfully to: 'mock@email'.")
        self.assertTrue(result)


class NotificationHandlerGetLinesFromListTestCase(unittest.TestCase):
    """Class for unit testing the _get_lines_from_list private method."""

    @classmethod
    def setUp(cls):
        """Setup for the tests."""
        cls.email_to = "test@email.com"
        cls.email_url = "http://fake_url"

        with mock.patch(MOCK_LOGGER) as logger:
            cls.handler = NotificationHandler(cls.email_to, cls.email_url, logger)

    def test_get_lines_from_list_one_level(self):
        """Asserts if a simple list returns as a text."""
        error_list = ["error 1", "error 2", "error 3"]

        expected_message = "error 1<br>" \
                           "error 2<br>" \
                           "error 3<br>"

        result_message = self.handler._get_lines_from_list(error_list)

        self.assertEqual(expected_message, result_message)

    def test_get_lines_from_list_two_levels(self):
        """Asserts if a list inside another list is added to the text."""
        error_list_level_two = ["error 1", "error 2", "error 3"]
        error_list_level_one = ["Exception 1", error_list_level_two, "Exception n"]

        expected_message = "Exception 1<br>" \
                           "error 1<br>" \
                           "error 2<br>" \
                           "error 3<br>" \
                           "Exception n<br>"

        result_message = self.handler._get_lines_from_list(error_list_level_one)

        self.assertEqual(expected_message, result_message)

    def test_get_lines_from_list_three_levels(self):
        """Asserts if a list inside another list is added to the text."""
        error_list_level_three = ["Error a", "Error b"]
        error_list_level_two = ["error 1", "error 2", "error 3", error_list_level_three]
        error_list_level_one = ["Exception 1", error_list_level_two, "Exception n"]

        expected_message = "Exception 1<br>" \
                           "error 1<br>" \
                           "error 2<br>" \
                           "error 3<br>" \
                           "Error a<br>" \
                           "Error b<br>" \
                           "Exception n<br>"

        result_message = self.handler._get_lines_from_list(error_list_level_one)

        self.assertEqual(expected_message, result_message)

    def test_get_lines_from_list_no_list(self):
        """Asserts that an empty text is returned when there is no elements within the list."""
        error_list = []

        expected_message = ""

        result_message = self.handler._get_lines_from_list(error_list)

        self.assertEqual(expected_message, result_message)

    def test_get_lines_from_list_no_list_as_none(self):
        """Asserts that an empty text is returned when a None object is informed as argument."""
        error_list = None

        expected_message = ""

        result_message = self.handler._get_lines_from_list(error_list)

        self.assertEqual(expected_message, result_message)


class NotificationHandlerPrepareEmailBodyTestCase(unittest.TestCase):
    """Class for unit testing the prepare_email_body method."""

    @classmethod
    def setUp(cls):
        """Setup for the tests."""
        cls.email_to = "test@email.com"
        cls.email_url = "http://fake_url"

        with mock.patch(MOCK_LOGGER) as logger:
            cls.handler = NotificationHandler(cls.email_to, cls.email_url, logger)

    @mock.patch(MOCK_GET_CLI_ARGUMENTS)
    def test_prepare_email_body_error_email(self, mock_cli_args):
        """
        Asserts if the formatted e-mail has the list errors and the message with code error.
        :param mock_cli_args: mocking the message with the CLI arguments.
        """
        mock_cli_args.return_value = CLI_ARGUMENTS
        error_list = ["error 1", "error 2", "error 3"]

        expected_message = "network_bkp_offsite ran with the following arguments:<br>" \
                           "['--script_option', '1', '--customer_name', 'CUSTOMER_0']<br>" \
                           "The following errors happened during this operation:<br>" \
                           "error 1<br>" \
                           "error 2<br>" \
                           "error 3<br>" \
                           "System stopped with error code: 1." \
                           "<br><br>ntwk_bkp_offsite Version: " + __version__

        result = self.handler._prepare_email_body(NotificationHandler.ERROR, error_list, 1)

        self.assertEqual(expected_message, result)

    @mock.patch(MOCK_GET_CLI_ARGUMENTS)
    def test_prepare_email_body_success_email(self, mock_cli_args):
        """
        Asserts if the formatted e-mail has the list errors and the message with code error.
        :param mock_cli_args: mocking the message with the CLI arguments.
        """
        mock_cli_args.return_value = CLI_ARGUMENTS
        message_list = ["Upload finished.", "Elapsed time: 2"]

        expected_message = "network_bkp_offsite ran with the following arguments:<br>" \
                           "['--script_option', '1', '--customer_name', 'CUSTOMER_0']<br>" \
                           "The following operations were successfully finished:<br>" \
                           "Upload finished.<br>" \
                           "Elapsed time: 2<br>" \
                           "<br><br>ntwk_bkp_offsite Version: " + __version__

        result = self.handler._prepare_email_body(NotificationHandler.SUCCESS, message_list)

        self.assertEqual(expected_message, result)

    @mock.patch(MOCK_GET_CLI_ARGUMENTS)
    def test_prepare_email_body_error_list_none(self, mock_cli_args):
        """
        Asserts if the formatted e-mail has no list errors and the message with code error.
        :param mock_cli_args: mocking the message with the CLI arguments.
        """
        mock_cli_args.return_value = CLI_ARGUMENTS
        error_list = None
        expected_message = "network_bkp_offsite ran with the following arguments:<br>" \
                           "['--script_option', '1', '--customer_name', 'CUSTOMER_0']<br>" \
                           "System stopped with error code: 1." \
                           "<br><br>ntwk_bkp_offsite Version: " + __version__

        result = self.handler._prepare_email_body(NotificationHandler.ERROR, error_list, 1)

        self.assertEqual(expected_message, result)

    @mock.patch(MOCK_GET_CLI_ARGUMENTS)
    def test_prepare_email_body_error_list_none_error_code_none(self, mock_cli_args):
        """
        Asserts if the formatted e-mail has no list errors and no message with code error.
        :param mock_cli_args: mocking the message with the CLI arguments.
        """
        mock_cli_args.return_value = CLI_ARGUMENTS
        error_list = None
        expected_message = "network_bkp_offsite ran with the following arguments:<br>" \
                           "['--script_option', '1', '--customer_name', 'CUSTOMER_0']<br>" \
                           "<br><br>ntwk_bkp_offsite Version: " + __version__

        result = self.handler._prepare_email_body(NotificationHandler.ERROR, error_list)

        self.assertEqual(expected_message, result)

    @mock.patch(MOCK_GET_CLI_ARGUMENTS)
    def test_prepare_email_body_message_list_none(self, mock_cli_args):
        """
        Asserts if the formatted e-mail has no list message and no code error, even though it is
        informed

        :param mock_cli_args: mocking the message with the CLI arguments
        """
        mock_cli_args.return_value = CLI_ARGUMENTS
        message_list = None
        expected_message = "network_bkp_offsite ran with the following arguments:<br>" \
                           "['--script_option', '1', '--customer_name', 'CUSTOMER_0']<br>" \
                           "<br><br>ntwk_bkp_offsite Version: " + __version__

        result = self.handler._prepare_email_body(NotificationHandler.SUCCESS,
                                                  message_list, 1)

        self.assertEqual(expected_message, result)
