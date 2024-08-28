##############################################################################
# COPYRIGHT Ericsson AB 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For C0302(too-many-lines)
# For C0103(invalid-name)
# For E1101(no-member)
# For E0401(import-error)
# For R0913(too-many-arguments)
# pylint: disable=C0302,C0103,E1101,E0401,R0913

"""Module for testing network_backup_offsite/offsite_handler.py script."""

import unittest

from network_backup_offsite.offsite_handler import OffsiteHandler
from network_backup_offsite.backup_settings import EnmConfig

import mock

MOCK_PACKAGE = 'network_backup_offsite.offsite_handler.'

MOCK_DEPLOYMENT_NAME = 'mock_deployment.gpg'
MOCK_BKP_DESTINATION = 'mock_bkp_dest'
MOCK_BKP_TAG = 'mock_bkp_tag'
MOCK_BKP_TAG_ENCRYPTED = 'mock_bkp_tag.tar.gpg'
MOCK_BKP_TAG_COMPRESSED = 'mock_bkp_tag.tar'
MOCK_BKP_PATH = 'mock_bkp_path'
MOCK_ONSITE_RETENTION_VALUE = 10


def create_offsite_object():
    """Function to create OffsiteHandler object."""
    with mock.patch('network_backup_offsite.gnupg_manager.GnupgManager') as mock_gnupg_manager:
        with mock.patch('network_backup_offsite.gnupg_manager.GPG') as mock_gpg:
            mock_gnupg_manager.gpg_handler.side_effect = mock_gpg

    with mock.patch('network_backup_offsite.backup_settings.EnmConfig') as enm_config:
        deployment_config_dict = {MOCK_DEPLOYMENT_NAME, enm_config}

    with mock.patch('network_backup_offsite.backup_settings.OffsiteConfig') as mock_offsite_config:
        offsite_config = mock_offsite_config

    with mock.patch(MOCK_PACKAGE + 'CustomLogger') as logger:
        offsite_handler = OffsiteHandler(mock_gnupg_manager, offsite_config, deployment_config_dict,
                                         logger)
    return offsite_handler


class OffsiteHandlerGetOffsiteBkpsTestCase(unittest.TestCase):
    """Class to test get_offsite_backups_list() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'popen_communicate')
    def test_get_offsite_bkps_list_success(self, mock_popen_communicate):
        """Test to check the raise of exception if backup tag is empty."""
        mock_popen_communicate.return_value = MOCK_DEPLOYMENT_NAME, ""
        self.offsite_handler.root_backup_path_offsite = MOCK_BKP_PATH
        calls = [mock.call("Looking for network device backups on offsite.")]
        self.assertEqual(self.offsite_handler.get_offsite_backups_list(), [MOCK_DEPLOYMENT_NAME])
        self.offsite_handler.logger.info.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'popen_communicate')
    def test_get_offsite_bkps_list_empty(self, mock_popen_communicate):
        """Test to check the raise of exception if backup tag is empty."""
        mock_popen_communicate.return_value = "", ""
        self.offsite_handler.root_backup_path_offsite = MOCK_BKP_PATH
        self.assertEqual(self.offsite_handler.get_offsite_backups_list(), [])


class OffsiteHandlerPrepareAndDownloadCertainBkpTagTestCase(unittest.TestCase):
    "Class to test prepare_and_download_certain_bkp_tag() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    def test_prepare_and_download_certain_bkp_tag_empty_tag(self):
        with self.assertRaises(Exception) as cex:
            self.offsite_handler.prepare_and_download_certain_bkp_tag(MOCK_DEPLOYMENT_NAME, "",
                                                                      MOCK_BKP_DESTINATION)

        self.assertEqual(cex.exception.message, "Empty backup tag was informed.")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_prepare_and_download_certain_bkp_tag_bkp_tag_not_found(self,
                                                                    mock_get_offsite_bkp_list):
        mock_get_offsite_bkp_list.return_value = []
        self.offsite_handler.root_backup_path_offsite = MOCK_BKP_PATH
        with self.assertRaises(Exception) as cex:
            self.offsite_handler.prepare_and_download_certain_bkp_tag(MOCK_DEPLOYMENT_NAME,
                                                                      MOCK_BKP_TAG,
                                                                      MOCK_BKP_DESTINATION)

        self.assertEqual(cex.exception.message, "No backup with tag mock_bkp_tag.tar.gpg was found "
                                                "on offsite.")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_download_and_process_bkp')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_prepare_and_download_certain_bkp_tag_success(self, mock_get_offsite_bkp_list,
                                                          mock_validate_download_process_bkp):
        self.offsite_handler.root_backup_path_offsite = MOCK_BKP_PATH
        mock_get_offsite_bkp_list.return_value = [MOCK_BKP_TAG_ENCRYPTED]
        mock_validate_download_process_bkp.return_value = True

        self.assertTrue(self.offsite_handler.prepare_and_download_certain_bkp_tag(
           MOCK_DEPLOYMENT_NAME, MOCK_BKP_TAG, MOCK_BKP_DESTINATION))


class OffsiteHandlerPrepareAndDownloadNewestBkpTagTestCase(unittest.TestCase):
    "Class to test prepare_and_download_certain_bkp_tag() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_download_and_process_bkp')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_prepare_and_download_newest_bkp_offsite_empty_backup_tag(self,
                                                                      mock_get_offsite_bkp_list,
                                                                      mock_validate_backup):
        self.offsite_handler.root_backup_path_offsite = MOCK_BKP_PATH
        mock_get_offsite_bkp_list.return_value = [""]
        mock_validate_backup.return_value = True
        self.assertTrue(self.offsite_handler.prepare_and_download_newest_bkp_offsite(
            MOCK_DEPLOYMENT_NAME, MOCK_BKP_DESTINATION)[0], True)
        self.assertEqual(self.offsite_handler.prepare_and_download_newest_bkp_offsite(
            MOCK_DEPLOYMENT_NAME, MOCK_BKP_DESTINATION)[1], "")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_download_and_process_bkp')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_prepare_and_download_newest_bkp_offsite_filled_backup_tag(self,
                                                                      mock_get_offsite_bkp_list,
                                                                      mock_validate_backup):
        self.offsite_handler.root_backup_path_offsite = MOCK_BKP_PATH
        mock_get_offsite_bkp_list.return_value = [MOCK_BKP_TAG]
        mock_validate_backup.return_value = True
        self.assertTrue(self.offsite_handler.prepare_and_download_newest_bkp_offsite(
            MOCK_DEPLOYMENT_NAME, MOCK_BKP_DESTINATION)[0], True)
        self.assertEqual(self.offsite_handler.prepare_and_download_newest_bkp_offsite(
            MOCK_DEPLOYMENT_NAME, MOCK_BKP_DESTINATION)[1], MOCK_BKP_TAG)


class OffsiteHandlerValidateAndProcessBkpTestCase(unittest.TestCase):
    "Class to test validate_bkp_download_destination() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_bkp_download_destination')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_validate_and_process_bkp_validation_exception(self, mock_os,
                                                           mock_validate_bkp_destination):
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_validate_bkp_destination.side_effect = Exception("Destination validation failed")

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.validate_download_and_process_bkp(MOCK_DEPLOYMENT_NAME,
                                                                   MOCK_BKP_TAG,
                                                                   MOCK_BKP_DESTINATION)
        self.assertEqual(cex.exception.message, "Failed to download backup 'mock_bkp_tag' due to "
                                                "'Destination validation failed'.")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.check_backups_in_download_destination')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_bkp_download_destination')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_validate_and_process_bkp_check_exception(self, mock_os, mock_validate_bkp_destination,
                                                      mock_check_bkps):
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_validate_bkp_destination.return_value = MOCK_BKP_DESTINATION
        mock_check_bkps.side_effect = Exception("Backup check failed")

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.validate_download_and_process_bkp(MOCK_DEPLOYMENT_NAME,
                                                                   MOCK_BKP_TAG,
                                                                   MOCK_BKP_DESTINATION)
        self.assertEqual(cex.exception.message, "Failed to download backup 'mock_bkp_tag' due to "
                                                "'Backup check failed'.")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.download_and_process_backup')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.check_backups_in_download_destination')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_bkp_download_destination')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_validate_and_process_bkp_process_exception(self, mock_os,
                                                        mock_validate_bkp_destination,
                                                        mock_check_bkps,
                                                        mock_download_bkp):
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_validate_bkp_destination.return_value = MOCK_BKP_DESTINATION
        mock_check_bkps.return_value = True
        mock_download_bkp.side_effect = Exception("Backup download failed")

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.validate_download_and_process_bkp(MOCK_DEPLOYMENT_NAME,
                                                                   MOCK_BKP_TAG,
                                                                   MOCK_BKP_DESTINATION)
        self.assertEqual(cex.exception.message, "Failed to download backup 'mock_bkp_tag' due to "
                                                "'Backup download failed'.")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.download_and_process_backup')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.check_backups_in_download_destination')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.validate_bkp_download_destination')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_validate_and_process_bkp_process_success(self, mock_os, mock_validate_bkp_destination,
                                                      mock_check_bkps, mock_download_bkp):
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_validate_bkp_destination.return_value = MOCK_BKP_DESTINATION
        mock_check_bkps.return_value = True
        mock_download_bkp.return_value = True
        calls = [mock.call("Backup 'mock_bkp_tag' downloaded and processed successfully, "
                           "to destination 'mock_bkp_dest'.")]

        self.assertTrue(self.offsite_handler.validate_download_and_process_bkp
                        (MOCK_DEPLOYMENT_NAME, MOCK_BKP_TAG, MOCK_BKP_DESTINATION), True)
        self.offsite_handler.logger.info.assert_has_calls(calls)


class OffsiteHandlerValidateBkpDownloadDestinationTestCase(unittest.TestCase):
    "Class to test validate_bkp_download_destination() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'create_path')
    def test_validate_bkp_download_destination_no_destination_exception(self, mock_create_path):
        enm_config = EnmConfig(MOCK_DEPLOYMENT_NAME, MOCK_BKP_DESTINATION,
                               MOCK_ONSITE_RETENTION_VALUE)
        self.offsite_handler.onsite_deployment_config_dict = {MOCK_DEPLOYMENT_NAME: enm_config}
        mock_create_path.return_value = False
        calls = [mock.call("Backup download destination was not informed. "
                           "Default location 'mock_bkp_dest' will be used")]

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.validate_bkp_download_destination(MOCK_DEPLOYMENT_NAME)
        self.assertEqual(cex.exception.message, "Download destination folder 'mock_bkp_dest' could "
                                                "not be created onsite.")
        self.offsite_handler.logger.warning.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'create_path')
    def test_validate_bkp_download_destination_no_destination_success(self, mock_create_path):
        enm_config = EnmConfig(MOCK_DEPLOYMENT_NAME, MOCK_BKP_DESTINATION,
                               MOCK_ONSITE_RETENTION_VALUE)
        self.offsite_handler.onsite_deployment_config_dict = {MOCK_DEPLOYMENT_NAME: enm_config}
        mock_create_path.return_value = True

        self.assertEqual(
            self.offsite_handler.validate_bkp_download_destination(MOCK_DEPLOYMENT_NAME),
            MOCK_BKP_DESTINATION)


class OffsiteHandlerValidateCheckBkpsInDownloadDestinationTestCase(unittest.TestCase):
    "Class to test check_backups_in_download_destination() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_check_backups_in_download_destination_exception(self, mock_os, mock_create_path):
        mock_os.path.join.return_value = MOCK_BKP_DESTINATION
        mock_os.path.exists.return_value = True
        mock_create_path.return_value = False
        calls = [mock.call("The backup with tag mock_bkp_tag already exists onsite, "
                           "under: 'mock_bkp_dest'. it will be overridden.")]

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.check_backups_in_download_destination(MOCK_BKP_DESTINATION,
                                                                       MOCK_BKP_TAG)

        self.assertEqual(cex.exception.message, "Backup destination folder 'mock_bkp_dest' "
                                                "could not be created onsite.")

        self.offsite_handler.logger.warning.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_check_backups_in_download_destination_success(self, mock_os, mock_create_path):
        mock_os.path.join.return_value = MOCK_BKP_DESTINATION
        mock_os.path.exists.return_value = False
        mock_create_path.return_value = True

        self.assertTrue(
            self.offsite_handler.check_backups_in_download_destination(MOCK_BKP_DESTINATION,
                                                                       MOCK_BKP_TAG))


class OffsiteHandlerDownloadBackupFromOffsiteTestCase(unittest.TestCase):
    "Class to test download_backup_from_offsite() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'RsyncManager')
    def test_download_backup_from_offsite_exception(self, mock_rsync_manager):
        mock_rsync_manager.transfer_file.side_effect = Exception("Rsync error")
        with self.assertRaises(Exception) as cex:
            self.offsite_handler.download_backup_from_offsite(MOCK_BKP_TAG, MOCK_BKP_PATH,
                                                              MOCK_BKP_DESTINATION)

        self.assertEqual(cex.exception.message, "Error while downloading backup mock_bkp_tag "
                                                "from offsite path 'mock_bkp_path' due to Rsync "
                                                "error.")

    @mock.patch(MOCK_PACKAGE + 'RsyncManager')
    def test_download_backup_from_offsite_success(self, mock_rsync_manager):
        mock_rsync_manager.transfer_file.return_value = True

        calls = [mock.call("Downloading backup mock_bkp_tag from mock_bkp_path to "
                           "'mock_bkp_dest'."),
                 mock.call("Backup mock_bkp_tag downloaded successfully to 'mock_bkp_dest'.")]

        self.assertIsNone(self.offsite_handler.download_backup_from_offsite(MOCK_BKP_TAG,
                                                                            MOCK_BKP_PATH,
                                                                            MOCK_BKP_DESTINATION))

        self.offsite_handler.logger.info.assert_has_calls(calls)


class OffsiteHandlerProcessDownloadedBackupTestCase(unittest.TestCase):
    "Class to test process_downloaded_backup() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch('network_backup_offsite.gnupg_manager.GnupgManager.decrypt_file')
    def test_process_downloaded_backup_bkp_decryption_exception(self, mock_gnupg_manager):
        mock_gnupg_manager.decrypt_file.side_effect = Exception("Decryption error")
        self.offsite_handler.gpg_manager = mock_gnupg_manager

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.process_downloaded_backup(MOCK_BKP_TAG, MOCK_BKP_DESTINATION)

        self.assertEqual(cex.exception.message, "Decryption error")

    @mock.patch(MOCK_PACKAGE + 'decompress_file')
    @mock.patch('network_backup_offsite.gnupg_manager.GnupgManager.decrypt_file')
    def test_process_downloaded_backup_bkp_decryption_extraction_exception(self, mock_gnupg_manager,
                                                                           mock_decompress_file):
        mock_gnupg_manager.decrypt_file.side_effect = Exception("Decompression error")
        self.offsite_handler.gpg_manager = mock_gnupg_manager
        mock_decompress_file.return_value = MOCK_BKP_TAG

        with self.assertRaises(Exception) as cex:
            self.offsite_handler.process_downloaded_backup(MOCK_BKP_TAG, MOCK_BKP_DESTINATION)

        self.assertEqual(cex.exception.message, "Decompression error")

    @mock.patch(MOCK_PACKAGE + 'decompress_file')
    @mock.patch('network_backup_offsite.gnupg_manager.GnupgManager.decrypt_file')
    def test_process_downloaded_backup_bkp_decryption_success(self, mock_gnupg_manager,
                                                              mock_decompress_file):
        mock_gnupg_manager.decrypt_file.return_value = MOCK_BKP_TAG_COMPRESSED
        mock_decompress_file.return_value = MOCK_BKP_TAG

        self.offsite_handler.gpg_manager = mock_gnupg_manager

        calls = [mock.call("Processing the downloaded backup mock_bkp_tag.tar.gpg."),
                 mock.call("Decrypting the backup 'mock_bkp_path'."),
                 mock.call("Backup 'mock_bkp_path' decrypted successfully, output: "
                           "'mock_bkp_tag.tar'."),
                 mock.call("Extracting the backup 'mock_bkp_tag.tar'."),
                 mock.call("Backup 'mock_bkp_tag.tar' extracted successfully, output: "
                           "'mock_bkp_tag'.")]

        self.assertTrue(self.offsite_handler.process_downloaded_backup(MOCK_BKP_TAG_ENCRYPTED,
                                                                       MOCK_BKP_PATH))
        self.offsite_handler.logger.info.assert_has_calls(calls)


class OffsiteHandlerListBackupsOnOffsiteTestCase(unittest.TestCase):
    "Class to test list_backups_on_offsite() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_list_backups_on_offsite_bkp_list_exception(self, mock_get_bkp_list):
        mock_get_bkp_list.side_effect = Exception("Backup list error")
        with self.assertRaises(Exception) as cex:
            self.offsite_handler.list_backups_on_offsite()

        self.assertEqual(cex.exception.message, "An error occurred while trying to list backups "
                                                "on offsite, cause: Backup list error")

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_list_backups_on_offsite_success(self, mock_get_bkp_list):
        mock_get_bkp_list.return_value = [MOCK_BKP_TAG]

        calls = [mock.call("Backups listing from offsite finished successfully.")]

        self.assertTrue(self.offsite_handler.list_backups_on_offsite())
        self.offsite_handler.logger.info.assert_has_calls(calls)


class OffsiteHandlerGetOffsiteBkpsDirsToCleanupTestCase(unittest.TestCase):
    "Class to test get_offsite_bkps_dirs_list_to_cleanup() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_get_offsite_bkps_dirs_list_to_cleanup_warning(self, mock_get_offsite_bkps):
        mock_get_offsite_bkps.return_value = [MOCK_BKP_TAG]

        calls = [mock.call("1 backup(s) found on offsite. Retention is 2. Nothing to do.")]

        self.assertEqual(self.offsite_handler.get_offsite_bkps_dirs_list_to_cleanup(2), [])
        self.offsite_handler.logger.warning.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_backups_list')
    def test_get_offsite_bkps_dirs_list_to_cleanup_success(self, mock_get_offsite_bkps):
        mock_get_offsite_bkps.return_value = [MOCK_BKP_TAG]

        calls = [mock.call("1 backup(s) found on offsite. Retention is 0. "
                           "1 backups should be removed.")]

        self.assertEqual(self.offsite_handler.get_offsite_bkps_dirs_list_to_cleanup(0),
                         [MOCK_BKP_TAG])
        self.offsite_handler.logger.info.assert_has_calls(calls)


class OffsiteHandlerCleanOffsiteBackupTestCase(unittest.TestCase):
    "Class to test clean_offsite_backup() method from OffsiteHandler class."""

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.offsite_handler = create_offsite_object()

    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_bkps_dirs_list_to_cleanup')
    def test_clean_offsite_backup_empty_remove_list(self, mock_get_bkp_dirs):
        mock_get_bkp_dirs.return_value = []
        result, result_message, result_array = self.offsite_handler.clean_offsite_backup(0)
        self.assertTrue(result)
        self.assertEqual(result_message, "Offsite clean up finished successfully with no "
                                         "backups removed.")
        self.assertEqual(result_array, [])

    @mock.patch(MOCK_PACKAGE + 'remove_remote_dir')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_bkps_dirs_list_to_cleanup')
    def test_clean_offsite_backup_cleanup_exception(self, mock_get_bkp_dirs,
                                                    mock_remove_remote_dir):
        mock_get_bkp_dirs.return_value = [MOCK_BKP_PATH]
        mock_remove_remote_dir.side_effect = Exception("Cleanup exception")

        result, result_message, result_array = self.offsite_handler.clean_offsite_backup(0)
        self.assertFalse(result)
        self.assertEqual(result_message, "Cleanup exception")
        self.assertEqual(result_array, [])

    @mock.patch(MOCK_PACKAGE + 'remove_remote_dir')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_bkps_dirs_list_to_cleanup')
    def test_clean_offsite_backup_dirs_not_removed(self, mock_get_bkp_dirs,
                                                    mock_remove_remote_dir):
        mock_get_bkp_dirs.return_value = [MOCK_BKP_PATH]
        mock_remove_remote_dir.return_value = MOCK_BKP_PATH, ""

        result, result_message, result_array = self.offsite_handler.clean_offsite_backup(0)
        self.assertFalse(result)
        self.assertEqual(result_message, "Following backups were not removed: mock_bkp_path")
        self.assertEqual(result_array, "")

    @mock.patch(MOCK_PACKAGE + 'remove_remote_dir')
    @mock.patch(MOCK_PACKAGE + 'OffsiteHandler.get_offsite_bkps_dirs_list_to_cleanup')
    def test_clean_offsite_backup_dirs_success(self, mock_get_bkp_dirs,
                                                   mock_remove_remote_dir):
        mock_get_bkp_dirs.return_value = [MOCK_BKP_PATH]
        mock_remove_remote_dir.return_value = "", MOCK_BKP_PATH

        result, result_message, result_array = self.offsite_handler.clean_offsite_backup(0)
        self.assertTrue(result)
        self.assertEqual(result_message, "Offsite backups clean up finished successfully, "
                                         "removed backups: ")
        self.assertEqual(result_array, MOCK_BKP_PATH)

