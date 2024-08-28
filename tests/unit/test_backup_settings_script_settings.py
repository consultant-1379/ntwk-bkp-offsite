##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For unable to import
# For the snake_case comments (invalid test names)
# For access a protected member
# pylint: disable=C0103,E0401,W0212

""" Module for unit testing the class ScriptSettings from backup_settings.py script. """

from ConfigParser import ConfigParser, ParsingError, MissingSectionHeaderError
from StringIO import StringIO
import logging
import unittest

from network_backup_offsite.backup_settings import ScriptSettings
import mock

MOCK_OS_ACCESS = 'network_backup_offsite.backup_settings.os.access'
MOCK_CONFIG_PARSER = 'network_backup_offsite.backup_settings.ConfigParser.readfp'
MOCK_LOGGER = 'network_backup_offsite.logger.CustomLogger'
MOCK_OPEN = 'network_backup_offsite.backup_settings.open'
MOCK_SCRIPT_SETTINGS = 'network_backup_offsite.backup_settings.ScriptSettings'

CONFIG_FILE_NAME = 'fake_config_file'


class ScriptSettingsGetConfigDetails(unittest.TestCase):
    """ Class for unit testing the get_config_details from ScriptSetting class. """

    def setUp(self):
        """ Setting up the test variables. """

        with mock.patch(MOCK_LOGGER) as logger:
            self.mock_logger = logger
            self.mock_logger.log_root_path = ""
            self.mock_logger.log_file_name = ""
            self.mock_logger.log_level = logging.INFO

        with mock.patch(MOCK_SCRIPT_SETTINGS + '._get_config_details') as mock_get_config:
            mock_get_config.return_value = ConfigParser()
            self.script_settings = ScriptSettings(CONFIG_FILE_NAME, self.mock_logger)
            self.script_settings.config_file_path = CONFIG_FILE_NAME

    @mock.patch(MOCK_CONFIG_PARSER)
    @mock.patch(MOCK_OPEN)
    @mock.patch(MOCK_OS_ACCESS)
    def test_get_config_details(self, mock_os_access, mock_open, mock_parser):
        """
        Asserts if the methods returns an object when the file is valid and has valid information.
        :param mock_os_access: mocking if the file exists.
        :param mock_open: mocking opening a file.
        :param mock_parser: mocking reading and creating a configuration object.
        """
        mock_os_access.return_value = True
        mock_parser.return_value = None
        mock_open.return_value = StringIO(CONFIG_FILE_NAME)

        result = self.script_settings._get_config_details()
        self.assertIsNotNone(result)

    def test_get_config_file_cant_access_file(self):
        """
        Asserts if raises an exception when the file isn't valid or readable.
        """
        error_msg = "Configuration file is not accessible 'fake_config_file'"

        with self.assertRaises(Exception) as cex:
            self.script_settings._get_config_details()

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_OS_ACCESS)
    def test_get_config_details_basic_exception(self, mock_os_access):
        """
        Asserts if raises an exception when cannot read the file
        :param mock_os_access: mocking if the file exists
        """
        mock_os_access.return_value = True

        error_msg = "Configuration file error: "

        with self.assertRaises(Exception) as cex:
            self.script_settings._get_config_details()

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_OPEN)
    @mock.patch(MOCK_OS_ACCESS)
    def test_get_config_details_io_error_exception(self, mock_os_access, mock_open):
        """
        Asserts if raises an exception when cannot read the file.
        :param mock_os_access: mocking if the file exists.
        """
        mock_os_access.return_value = True
        mock_open.side_effect = IOError

        error_msg = "Configuration file error: "

        with self.assertRaises(Exception) as cex:
            self.script_settings._get_config_details()

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_CONFIG_PARSER)
    @mock.patch(MOCK_OPEN)
    @mock.patch(MOCK_OS_ACCESS)
    def test_get_config_details_parser_exception(self, mock_os_access, mock_open, mock_parser):
        """
        Asserts if raises an exception and said exception is caught in the correct except.
        :param mock_os_access: mocking if the file exists.
        :param mock_open: mocking opening a file.
        :param mock_parser: mocking reading and creating a configuration object.
        """
        mock_os_access.return_value = True
        mock_open.return_value = StringIO(CONFIG_FILE_NAME)
        mock_parser.side_effect = AttributeError("Test exception")

        error_msg = "Parsing configuration file error: Test exception"

        with self.assertRaises(Exception) as cex:
            self.script_settings._get_config_details()

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_CONFIG_PARSER)
    @mock.patch(MOCK_OPEN)
    @mock.patch(MOCK_OS_ACCESS)
    def test_get_config_details_parsing_error_exception(self, mock_open, mock_os_access,
                                                        mock_parser):
        """
        Asserts if raises an exception and said exception is caught in the correct except.
        :param mock_os_access: mocking if the file exists.
        :param mock_open: mocking opening a file.
        :param mock_parser: mocking reading and creating a configuration object.
        """
        mock_os_access.return_value = True
        mock_open.return_value = StringIO(CONFIG_FILE_NAME)
        mock_parser.side_effect = ParsingError(CONFIG_FILE_NAME)

        error_msg = "Parsing configuration file error: " \
                    "File contains parsing errors: fake_config_file"

        with self.assertRaises(Exception) as cex:
            self.script_settings._get_config_details()

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_CONFIG_PARSER)
    @mock.patch(MOCK_OPEN)
    @mock.patch(MOCK_OS_ACCESS)
    def test_get_config_details_missing_section_exception(self, mock_open, mock_os_access,
                                                          mock_parser):
        """
        Asserts if raises an exception and said exception is caught in the correct except.
        :param mock_os_access: mocking if the file exists.
        :param mock_open: mocking opening a file.
        :param mock_parser: mocking reading and creating a configuration object.
        """
        mock_os_access.return_value = True
        mock_open.return_value = StringIO(CONFIG_FILE_NAME)
        mock_parser.side_effect = MissingSectionHeaderError(CONFIG_FILE_NAME, 1, 1)

        error_msg = "Parsing configuration file error: " \
                    "File contains no section headers.\n" \
                    "file: fake_config_file, line: 1\n1"

        with self.assertRaises(Exception) as cex:
            self.script_settings._get_config_details()

        self.assertEqual(error_msg, cex.exception.message)
