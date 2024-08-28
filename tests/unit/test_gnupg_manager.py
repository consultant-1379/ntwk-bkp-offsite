##############################################################################
# COPYRIGHT Ericsson AB 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For the snake_case comments, no member, unable to import module, too many arguments and too
# many locals, respectively.
# pylint: disable=C0103,E1101,E0401,R0913,R0914

"""Module for testing backup/gnupg_manager.py script."""

import logging
import os
import unittest

from network_backup_offsite.gnupg_manager import GnupgManager
from network_backup_offsite.utils import get_home_dir

import mock

logging.disable(logging.CRITICAL)

MOCK_PACKAGE = 'network_backup_offsite.gnupg_manager.'
GPG_KEY_PATH = os.path.join(get_home_dir(), ".gnupg")

MOCK_SOURCE_DIR = 'mock_path'
MOCK_EMAIL = 'mock_user_email'
MOCK_USER_NAME = 'mock_user_name'
MOCK_FILE_PATH = 'mock_file_path'
MOCK_OUTPUT_PATH = 'mock_output_path'
MOCK_DECRYPTED_FILE = 'mock_encrypted_file'
MOCK_ENCRYPTED_FILE = 'mock_encrypted_file.gpg'
MOCK_COMPRESSED_FILE = 'mock_encrypted_file.gz'
MOCK_COMPRESSED_ENCRYPTED_FILE = 'mock_encrypted_file.gz.gpg'


def get_gnupg_manager():
    """
    Get an instance of gnupg_manager to perform tests.

    :return: gnupg_manager instance.
    """
    with mock.patch(MOCK_PACKAGE + 'CustomLogger') as mock_logger:
        with mock.patch(MOCK_PACKAGE + 'GPG') as mock_gpg_handler:
            with mock.patch(MOCK_PACKAGE + 'Popen') as mock_popen:
                mock_popen.return_value.wait.return_value = 0
                gnupg_manager = GnupgManager(MOCK_USER_NAME, MOCK_EMAIL, mock_logger)
                gnupg_manager.gpg_handler = mock_gpg_handler

    return gnupg_manager


class GnupgManagerValidateEncryptionKeyTestCase(unittest.TestCase):
    """Class for testing validate_encryption_key() method from GnupgManager class."""

    def setUp(self):
        """Setting up the test variables."""
        self.gnupg_manager = get_gnupg_manager()

    @mock.patch(MOCK_PACKAGE + 'Popen')
    def test_validate_encryption_key_already_exists(self, mock_popen):
        """Test to check when the key already exists."""
        mock_popen.return_value.wait.return_value = 0

        calls = [mock.call("Validating GPG encryption settings."),
                 mock.call("Backup key already exists.")]

        validation_result = self.gnupg_manager.validate_encryption_key()

        self.assertTrue(validation_result, "Should have returned true.")

        self.gnupg_manager.logger.info.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'Popen')
    def test_validate_encryption_key_creation_key_failure_exception(self, mock_popen):
        """Test to check the log values if the key generation has started."""
        mock_popen.return_value.wait.return_value = 1
        self.gnupg_manager.gpg_handler = None

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.validate_encryption_key()

        self.assertEqual(cex.exception.message, "GPG program not installed properly in this "
                                                "system.")

    @mock.patch(MOCK_PACKAGE + 'Popen')
    def test_validate_encryption_key_generate_key(self, mock_popen):
        """Test to check if generation of key is being triggered."""
        mock_popen.return_value.wait.return_value = 1

        logger_calls = [mock.call("Backup key does not exist yet. Creating a new one.")]

        gen_key_call = [mock.call.gen_key_input(key_length=1024, key_type='RSA',
                                                name_email=MOCK_EMAIL,
                                                name_real=MOCK_USER_NAME)]

        validation_result = self.gnupg_manager.validate_encryption_key()

        self.assertTrue(validation_result, "Should have returned true.")

        self.gnupg_manager.logger.info.assert_has_calls(logger_calls)

        self.gnupg_manager.gpg_handler.assert_has_calls(gen_key_call)


class GnupgManagerEncryptFileTestCase(unittest.TestCase):
    """Class for testing encrypt_file() method from GnupgManager class."""

    def setUp(self):
        """Setting up the test variables."""
        self.gnupg_manager = get_gnupg_manager()

    def test_encrypt_file_empty_file_path(self):
        """Test to check the raise of exception if file_path is empty."""
        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.encrypt_file('', MOCK_OUTPUT_PATH)

        self.assertEqual(cex.exception.message, "An empty file path or output file path was "
                                                "provided.")

    def test_encrypt_file_empty_output_path(self):
        """Test to check the raise of exception if output_path is empty."""
        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.encrypt_file(MOCK_FILE_PATH, '')

        self.assertEqual(cex.exception.message, "An empty file path or output file path was "
                                                "provided.")

    @mock.patch(MOCK_PACKAGE + 'os')
    def test_encrypt_file_input_file_does_not_exists(self, mock_os):
        """Test to check the raise of exception if file_path does not exist."""
        mock_os.path.exists.return_value = False

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.encrypt_file(MOCK_FILE_PATH, MOCK_OUTPUT_PATH)

        self.assertEqual(cex.exception.message, "Informed file does not exist '{}'.".format(
            MOCK_FILE_PATH))

    @mock.patch(MOCK_PACKAGE + 'Popen')
    @mock.patch(MOCK_PACKAGE + 'open')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_encrypt_file_encryption_failure(self, mock_os, mock_open, mock_popen):
        """Test to check the raise of exception if encryption could not be completed."""
        mock_os.path.exists.return_value = True
        mock_os.path.join.return_value = ''
        mock_os.path.basename.return_value = ''
        mock_open.return_value = mock.MagicMock(spec=file)
        mock_popen.return_value.wait.return_value = 1

        calls = [mock.call("Encrypting file '{}'".format(MOCK_FILE_PATH))]

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.encrypt_file(MOCK_FILE_PATH, MOCK_OUTPUT_PATH)

        self.assertEqual(cex.exception.message, "Encryption of file {} could not be completed.".
                         format(MOCK_FILE_PATH))

        self.gnupg_manager.logger.info.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'Popen')
    @mock.patch(MOCK_PACKAGE + 'open')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_encrypt_file_return_value(self, mock_os, mock_open, mock_popen):
        """Test to check the return value if encryption was successful."""
        mock_file_input = '/path/to/mock_input'
        mock_output_path = '/path/to/output'
        mock_result_path = '/path/to/output/mock_input'

        mock_os.path.exists.return_value = True
        mock_os.path.join.return_value = mock_result_path

        mock_open.return_value = mock.MagicMock(spec=file)
        mock_popen.return_value.wait.return_value = 0

        calls = [mock.call("Encrypting file '{}'".format(mock_file_input))]

        encrypt_result = self.gnupg_manager.encrypt_file(mock_file_input, mock_output_path)

        self.assertEqual(encrypt_result, '/path/to/output/mock_input.gpg')

        self.gnupg_manager.logger.info.assert_has_calls(calls)


class GnupgManagerDecryptFileTestCase(unittest.TestCase):
    """Class for testing decrypt_file() method from GnupgManager class."""

    def setUp(self):
        """Setting up the test variables."""
        self.gnupg_manager = get_gnupg_manager()

    def test_decrypt_file_empty_file_path(self):
        """Test when the provided path is empty."""
        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.decrypt_file('')

        self.assertEqual(cex.exception.message, "An empty file path was provided.")

    def test_decrypt_file_invalid_file_extension(self):
        """Test when the provided path has an extension other than .gpg."""
        mock_input_file = 'file.dat'

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.decrypt_file(mock_input_file)

        self.assertEqual(cex.exception.message, "Not a valid GPG encrypted file '{}'.".format(
            mock_input_file))

    @mock.patch(MOCK_PACKAGE + 'os')
    def test_decrypt_file_path_does_not_exist(self, mock_os):
        """Test when the provided path has does not exist."""
        mock_input_file = 'file.gpg'
        mock_os.path.exists.return_value = False

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.decrypt_file(mock_input_file)

        self.assertEqual(cex.exception.message, "Informed file does not exist '{}'.".format(
            mock_input_file))

    @mock.patch(MOCK_PACKAGE + 'os')
    def test_decrypt_file_input_path_is_dir(self, mock_os):
        """Test when the provided path is not a file."""
        mock_input_file = 'file.gpg'
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = True

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.decrypt_file(mock_input_file)

        self.assertEqual(cex.exception.message, "Informed path is a directory '{}'.".format(
            mock_input_file))

    @mock.patch(MOCK_PACKAGE + 'open')
    @mock.patch(MOCK_PACKAGE + 'Popen')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_decrypt_file_decryption_failure_exception(self, mock_os, mock_popen, mock_open):
        """Test when an error happens when trying to decrypt the file."""
        mock_input_file = 'file.gpg'
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = False
        mock_popen.return_value.wait.return_value = 1
        mock_open.return_value = mock.MagicMock(spec=file)

        with self.assertRaises(Exception) as cex:
            self.gnupg_manager.decrypt_file(mock_input_file)

        self.assertEqual(cex.exception.message, "Decryption of file '{}' could not be "
                                                "completed.".format(mock_input_file))

    @mock.patch(MOCK_PACKAGE + 'open')
    @mock.patch(MOCK_PACKAGE + 'Popen')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_decrypt_file_decryption_success_case(self, mock_os, mock_popen, mock_open):
        """Test when the file is decrypted successfully."""
        mock_input_file = 'file.gpg'
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = False
        mock_popen.return_value.wait.return_value = 0
        mock_open.return_value = mock.MagicMock(spec=file)

        decrypt_file_result = self.gnupg_manager.decrypt_file(mock_input_file)
        self.assertEqual(decrypt_file_result, 'file')

    @mock.patch(MOCK_PACKAGE + 'remove_path')
    @mock.patch(MOCK_PACKAGE + 'open')
    @mock.patch(MOCK_PACKAGE + 'Popen')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_decrypt_file_decryption_success_case_remove_flag(
            self, mock_os, mock_popen, mock_open, mock_remove_path):
        """Test when the file is decrypted successfully and the original file is removed."""
        mock_input_file = 'file.gpg'
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = False
        mock_popen.return_value.wait.return_value = 0
        mock_open.return_value = mock.MagicMock(spec=file)
        mock_remove_path.return_value = True

        decrypt_file_result = self.gnupg_manager.decrypt_file(mock_input_file, True)
        self.assertEqual(decrypt_file_result, 'file')

        self.gnupg_manager.logger.info.assert_called_with("Removing file '{}'.".format(
            mock_input_file))
