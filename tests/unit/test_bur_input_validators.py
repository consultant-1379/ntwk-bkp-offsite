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
# pylint: disable=C0103,E0401

"""
Module for unit testing the bur_input_validators.py script
"""

import unittest
import mock

import network_backup_offsite.bur_input_validators as validators
from network_backup_offsite.exceptions import BackupSettingsException
from network_backup_offsite.utils import DEFAULT_NUM_PROCESSORS
from network_backup_offsite.main import SCRIPT_OPERATIONS

MOCK_BUR_INPUT_VALIDATORS = 'network_backup_offsite.bur_input_validators'
MOCK_BACKUP_SETTINGS = 'network_backup_offsite.backup_settings'
MOCK_LOGGER = 'network_backup_offsite.logger.CustomLogger'
MOCK_CPU_COUNT = 'network_backup_offsite.bur_input_validators.multiprocessing.cpu_count'

SCRIPT_UPLOAD = 1
SCRIPT_DOWNLOAD = 2
SCRIPT_RETENTION = 3
SCRIPT_INVALID_OPTION = -1
CUSTOMER_NAME = "fake_customer"
BACKUP_TAG = "fake_tag"
#NO_CUSTOMER = ""
NO_BACKUP_TAG = ""
CONFIG_FILE_NAME = 'fake_config_file'


class BurInputValidatorsPrepareLogFileName(unittest.TestCase):
    """Class for unit testing the prepare_log_file_name function."""

    def test_prepare_log_file_name_upload_no_backup_tag(self):
        """
        Asserts if an all_customers_upload.log is returned when there is no customer or
        backup_tag informed.
        """
        correct_log_name = "network_device_backup_upload.log"
        result = validators.prepare_log_file_name(SCRIPT_UPLOAD, SCRIPT_OPERATIONS, NO_BACKUP_TAG)

        self.assertEqual(result, correct_log_name)

    def test_prepare_log_file_name_upload_with_backup_tag(self):
        """
        Asserts if a customer_upload.log is returned when there is a customer_name informed.
        """
        correct_log_name = "network_device_backup_upload.log"
        result = validators.prepare_log_file_name(SCRIPT_UPLOAD, SCRIPT_OPERATIONS, BACKUP_TAG)

        self.assertEqual(result, correct_log_name)

    def test_prepare_log_file_name_download(self):
        """
        Asserts if an error_download.log is returned when there is no customer or
        backup_tag informed.
        """
        correct_log_name = "error_download.log"
        result = validators.prepare_log_file_name(SCRIPT_DOWNLOAD, SCRIPT_OPERATIONS, NO_BACKUP_TAG)

        self.assertEqual(result, correct_log_name)

    def test_prepare_log_file_name_retention(self):
        """
        Asserts if an all_customers_retention.log is returned when
        there is no customer_name informed.
        """
        correct_log_name = "list_network_device_backups.log"
        result = validators.prepare_log_file_name(SCRIPT_RETENTION, SCRIPT_OPERATIONS,
                                                  NO_BACKUP_TAG)

        self.assertEqual(result, correct_log_name)

    def test_prepare_log_file_name_exception(self):
        """Asserts if an Exception is raised when an invalid script operation is informed."""
        with self.assertRaises(Exception) as cex:
            validators.prepare_log_file_name(SCRIPT_INVALID_OPTION, SCRIPT_OPERATIONS,
                                             NO_BACKUP_TAG)
            error = "Operation -1 not supported."
            self.assertEqual(error, cex.exception.message)


class BurInputValidatorsValidateScriptSettings(unittest.TestCase):
    """ Class for unit testing the validate_script_settings function."""

    def setUp(self):
        """
        Setting up test constants/variables.
        """
        with mock.patch(MOCK_BACKUP_SETTINGS + '.NotificationHandler') as nh:
            self.mock_notification_handler = nh

        with mock.patch('network_backup_offsite.gnupg_manager.GnupgManager') as gnupg:
            self.mock_gnupg_manager = gnupg

        with mock.patch(MOCK_BACKUP_SETTINGS + '.OffsiteConfig') as offsite_config:
            self.mock_offsite_config = offsite_config

        with mock.patch(MOCK_BACKUP_SETTINGS + '.EnmConfig') as enm_config:
            self.mock_customer_config_dict = dict({'customer_0': enm_config})

        with mock.patch(MOCK_BACKUP_SETTINGS + '.DelayConfig') as delay_config:
            self.mock_delay_config = delay_config

        with mock.patch(MOCK_LOGGER) as logger:
            self.mock_logger = logger

    @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.ScriptSettings.get_customer_config_dict')
    @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.ScriptSettings')
    def test_validate_script_settings(self, mock_script_settings, mock_customer_config):
        """
        Asserts if returns a dictionary with the four objects if ScriptSettings object was
        created correctly with config_file.
        :param mock_script_settings: mock of ScriptSettings object.
        :param mock_customer_config: ScriptSettings.get_customer_config_dict method.
        """
        mock_script_settings.return_value.get_notification_handler = self.mock_notification_handler
        mock_script_settings.return_value.get_gnupg_manager = self.mock_gnupg_manager
        mock_script_settings.return_value.get_offsite_config = self.mock_offsite_config
        mock_script_settings.return_value.get_delay_config = self.mock_delay_config
        mock_customer_config.return_value = self.mock_customer_config_dict

        result = validators.validate_script_settings(CONFIG_FILE_NAME, {}, self.mock_logger)

        self.assertIsNotNone(result)
        self.assertIs(validators.SCRIPT_OBJECTS.SIZE.value - 1, len(result))

    @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.ScriptSettings')
    def test_validate_script_settings_notification_handler_error(self, mock_script_settings):
        """
        Asserts if raises an Exception when trying to get NotificationHandler from ScriptSetting.
        :param mock_script_settings: mock of ScriptSettings object.
        """
        error_msg = "Error validating ScriptSettings object due to: Error: 50. No NH available."

        mock_script_settings.return_value.get_notification_handler.side_effect = \
            BackupSettingsException("No NH available")

        with self.assertRaises(Exception) as cex:
            validators.validate_script_settings(CONFIG_FILE_NAME, {}, self.mock_logger)

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.ScriptSettings')
    def test_validate_script_settings_gnupg_manager_error(self, mock_script_settings):
        """
        Asserts if raises an Exception when trying to get Gnupg_Manager from ScriptSetting.
        :param mock_script_settings: mock of ScriptSettings object.
        """
        error_msg = "Error validating ScriptSettings object due to: Error: 50. No GNUPG available."

        mock_script_settings.return_value.get_gnupg_manager.side_effect = \
            BackupSettingsException("No GNUPG available")

        with self.assertRaises(Exception) as cex:
            validators.validate_script_settings(CONFIG_FILE_NAME, {}, self.mock_logger)

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.ScriptSettings')
    def test_validate_script_settings_offsite_config_error(self, mock_script_settings):
        """
        Asserts if raises an Exception when trying to get OffsiteConfig from ScriptSetting.
        :param mock_script_settings: mock of ScriptSettings object.
        """
        error_msg = "Error validating ScriptSettings object due to: " \
                    "Error: 50. No offsite_config available."

        mock_script_settings.return_value.get_offsite_config.side_effect = \
            BackupSettingsException("No offsite_config available")

        with self.assertRaises(Exception) as cex:
            validators.validate_script_settings(CONFIG_FILE_NAME, {}, self.mock_logger)

        self.assertEqual(error_msg, cex.exception.message)

    @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.ScriptSettings')
    def test_validate_script_settings_enmaas_config_dic_error(self, mock_script_settings):
        """
        Asserts if raises an Exception when trying to get enmaas_config_dict from ScriptSetting.
        :param mock_script_settings: mock of ScriptSettings object.
        """
        error_msg = "Error validating ScriptSettings object due to: " \
                    "Error: 50. No customer configuration available."

        mock_script_settings.return_value.get_deployment_config_dict.side_effect = \
            BackupSettingsException("No customer configuration available")

        with self.assertRaises(Exception) as cex:
            validators.validate_script_settings(CONFIG_FILE_NAME, {}, self.mock_logger)

        self.assertEqual(error_msg, cex.exception.message)


# class BurInputValidatorsValidateOnsiteOffsiteLocations(unittest.TestCase):
#     """ Class for unit testing the validate_onsite_offsite_locations function."""
#
#     def setUp(self):
#         """ Setting up the test constants."""
#         with mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.validate_script_settings') as script_objects:
#             self.mock_script_objects = script_objects
#             self.mock_script_objects.return_value = {
#                 validators.SCRIPT_OBJECTS.OFFSITE_CONFIG.name: 'offsite_config',
#                 validators.SCRIPT_OBJECTS.CUSTOMER_CONFIG_DICT.name: 'customer_config'}
#
#         with mock.patch(MOCK_LOGGER) as logger:
#             self.mock_logger = logger
#
#     @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.validate_onsite_backup_locations')
#     @mock.patch(MOCK_BUR_INPUT_VALIDATORS + '.validate_offsite_backup_server')
#     def test_validate_onsite_offsite_locations(self, mock_validate_offsite, mock_validate_onsite):
#         """
#         Asserts if returns True when all validations inside have been done successfully
#
#         :param mock_validate_offsite: mocking the validate_offsite_backup_server function
#         :param mock_validate_onsite: mocking the validate_onsite_backup_locations function
#         """
#         mock_validate_onsite.return_value = True
#         mock_validate_offsite.return_value = True
#
#         result = validators.validate_onsite_offsite_locations(CONFIG_FILE_NAME,
#                                                               self.mock_script_objects,
#                                                               self.mock_logger)
#         self.assertTrue(result)
