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

from network_backup_offsite.onsite_handler import OnsiteHandler
from network_backup_offsite.backup_settings import EnmConfig

import mock

MOCK_PACKAGE = 'network_backup_offsite.onsite_handler.'

CONF_FILE_NAME = 'config.cfg'

MOCK_DEPLOYMENT_NAME = 'mock_deployment'
MOCK_BKP_DESTINATION = 'mock_bkp_dest'
MOCK_BKP_TAG = 'mock_bkp_tag'
MOCK_BKP_TAG_COMPRESSED = 'mock_bkp_tag.tar'
MOCK_BKP_TAG_ENCRYPTED = 'mock_bkp_tag.tar.gpg'
MOCK_BKP_PATH = 'mock_bkp_path'
MOCK_HOST = 'root@127.0.0.1'
MOCK_ONSITE_RETENTION_VALUE = 10


def create_onsite_object():
    """Function to create OnsiteHandler object."""
    with mock.patch('network_backup_offsite.gnupg_manager.GnupgManager') as mock_gnupg_manager:
        with mock.patch('network_backup_offsite.gnupg_manager.GPG') as mock_gpg:
            mock_gnupg_manager.gpg_handler.side_effect = mock_gpg

    with mock.patch('network_backup_offsite.backup_settings.EnmConfig') as enm_config:
        onsite_deployment_config = enm_config

    with mock.patch('network_backup_offsite.backup_settings.OffsiteConfig') as mock_offsite_config:
        offsite_config = mock_offsite_config

    with mock.patch(MOCK_PACKAGE + 'CustomLogger') as logger:
        onsite_handler = OnsiteHandler(offsite_config, onsite_deployment_config,
                                       mock_gnupg_manager, logger)
    return onsite_handler


class OnsiteHandlerGetOnsiteBackupsListTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'os')
    def test_get_onsite_backups_list_path_not_exist(self, mock_os):
        self.onsite_handler.onsite_deployment_config = EnmConfig(MOCK_DEPLOYMENT_NAME,
                                                                 MOCK_BKP_DESTINATION)

        calls = [mock.call("Invalid backup source path 'mock_bkp_dest'.")]

        mock_os.path.exists.return_value = False
        self.assertIsNone(self.onsite_handler.get_onsite_backups_list())
        self.onsite_handler.logger.error.assert_has_calls(calls)

    @mock.patch('__builtin__.next')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_get_onsite_backups_list_no_bkp_dir_exception(self, mock_os, mock_next):
        self.onsite_handler.onsite_deployment_config = EnmConfig(MOCK_DEPLOYMENT_NAME,
                                                                 MOCK_BKP_DESTINATION)

        calls = [mock.call("No backup directories were found for the provided path: "
                           "'mock_bkp_dest'.")]

        mock_os.path.exists.return_value = True
        mock_next.return_value = "", "", ""

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.get_onsite_backups_list()

        self.assertEqual(cex.exception.message, "No backup directories were found for the provided "
                                                "path: 'mock_bkp_dest'.")

        self.onsite_handler.logger.error.assert_has_calls(calls)

    @mock.patch('__builtin__.next')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_get_onsite_backups_list_success(self, mock_os, mock_next):
        self.onsite_handler.onsite_deployment_config = EnmConfig(MOCK_DEPLOYMENT_NAME,
                                                                 MOCK_BKP_DESTINATION)

        calls = [mock.call("Getting the list of valid backups from 'mock_bkp_dest'."),
                 mock.call("Added the backup 'mock_bkp_path' to list of valid backups.")]

        mock_os.path.exists.return_value = True
        mock_next.return_value = MOCK_BKP_PATH, [MOCK_BKP_PATH],\
                                 MOCK_BKP_TAG
        mock_os.path.join.return_value = MOCK_BKP_PATH

        self.assertEqual(self.onsite_handler.get_onsite_backups_list(), [MOCK_BKP_PATH])

        self.onsite_handler.logger.info.assert_has_calls(calls)


class OnsiteHandlerProcessBackupListTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backups_list')
    def test_process_backup_list_no_onsite_bkps(self, mock_get_onsite_bkp):
        mock_get_onsite_bkp.return_value = []

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.process_backup_list()

        self.assertEqual(cex.exception.message, "No valid network device backups found.")

    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.create_onsite_offsite_backup_paths')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.backup_already_on_offsite')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.prepare_offsite_onsite_main_paths')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backups_list')
    def test_process_backup_list_backup_exception(self, mock_get_onsite_bkp,
                                                  mock_prepare_paths,
                                                  mock_already_on_offsite, mock_create_paths):
        mock_get_onsite_bkp.return_value = [MOCK_BKP_PATH]
        mock_prepare_paths.return_value = True
        mock_already_on_offsite.return_value = False
        mock_create_paths.side_effect = Exception("Backup exception")

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.process_backup_list()

        self.assertEqual(cex.exception.message, ["Backup exception"])

    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.delete_tmp_bkp_folder')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.transfer_backup_to_offsite')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.process_backup')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.create_onsite_offsite_backup_paths')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.backup_already_on_offsite')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.prepare_offsite_onsite_main_paths')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backups_list')
    def test_process_backup_list_backup_success(self, mock_get_onsite_bkp,
                                                mock_prepare_paths, mock_already_on_offsite,
                                                mock_create_paths, mock_process_bkp,
                                                mock_transfer_bkp, mock_delete_folder):
        mock_get_onsite_bkp.return_value = [MOCK_BKP_PATH]
        mock_prepare_paths.return_value = True
        mock_already_on_offsite.return_value = False
        mock_create_paths.return_value = True
        mock_process_bkp.return_value = MOCK_BKP_TAG_ENCRYPTED
        mock_transfer_bkp.return_value = True
        mock_delete_folder.return_value = None

        calls = [mock.call("Doing backup of: ['mock_bkp_path']")]

        result, result_list = self.onsite_handler.process_backup_list()
        self.assertTrue(result)
        self.assertEqual(result_list, [MOCK_BKP_PATH])
        self.onsite_handler.logger.log_info.assert_has_calls(calls)


class OnsiteHandlerPrepareOffsiteOnsiteMainPathsTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'create_remote_dir')
    @mock.patch(MOCK_PACKAGE + 'check_remote_path_exists')
    def test_prepare_offsite_onsite_main_paths_create_dir_exception(self, mock_check_remote,
                                                                    mock_create_dir):
        mock_check_remote.return_value = False
        mock_create_dir.return_value = False

        self.onsite_handler.onsite_deployment_config = EnmConfig(MOCK_DEPLOYMENT_NAME,
                                                                 MOCK_BKP_DESTINATION)
        self.onsite_handler.remote_root_path = MOCK_BKP_DESTINATION

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.prepare_offsite_onsite_main_paths()

        self.assertEqual(cex.exception.message, "Remote directory 'mock_bkp_dest' could not "
                                                "be created for customer mock_deployment.")

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'check_remote_path_exists')
    def test_prepare_offsite_onsite_main_paths_create_path_exception(self, mock_check_remote,
                                                                     mock_create_path):
        mock_check_remote.return_value = True
        mock_create_path.return_value = False

        self.onsite_handler.offsite_config.temp_path = MOCK_BKP_PATH

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.prepare_offsite_onsite_main_paths()

        self.assertEqual(cex.exception.message, "Local temporary root path 'mock_bkp_path' could "
                                                "not be created.")

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'check_remote_path_exists')
    def test_prepare_offsite_onsite_main_paths_create_customer_path_exception(self,
                                                                              mock_check_remote,
                                                                              mock_create_path):
        mock_check_remote.return_value = True
        mock_create_path.side_effect = [True, False]
        self.onsite_handler.bkp_temp_folder = MOCK_BKP_PATH

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.prepare_offsite_onsite_main_paths()

        self.assertEqual(cex.exception.message, "Local temporary customer path 'mock_bkp_path' "
                                                "could not be created")

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'check_remote_path_exists')
    def test_prepare_offsite_onsite_main_paths_success(self, mock_check_remote, mock_create_path):
        mock_check_remote.return_value = True
        mock_create_path.return_value = True
        self.onsite_handler.bkp_temp_folder = MOCK_BKP_PATH

        self.assertTrue(self.onsite_handler.prepare_offsite_onsite_main_paths())


class OnsiteHandlerBackupAlreadyOnOffsiteTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'os')
    def test_backup_already_on_offsite_check_bkp_exception(self, mock_os):
        mock_os.path.join.side_effect = Exception("Backup check exception")

        with self.assertRaises(Exception):
            self.onsite_handler.backup_already_on_offsite(MOCK_BKP_TAG, MOCK_BKP_PATH,
                                                          MOCK_HOST)

    @mock.patch(MOCK_PACKAGE + 'check_remote_path_exists')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_backup_already_on_offsite_remote_path_exist(self, mock_os, mock_check_remote):
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_check_remote.return_value = True

        calls = [mock.call("Offsite has a backup with the same name. The backup mock_bkp_tag will "
                           "not be uploaded.")]

        self.assertTrue(self.onsite_handler.backup_already_on_offsite(MOCK_BKP_TAG, MOCK_BKP_PATH,
                                                                      MOCK_HOST))
        self.onsite_handler.logger.warning.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'check_remote_path_exists')
    @mock.patch(MOCK_PACKAGE + 'os')
    def test_backup_already_on_offsite_no_remote_path(self, mock_os, mock_check_remote):
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_check_remote.return_value = False

        self.assertFalse(self.onsite_handler.backup_already_on_offsite(MOCK_BKP_TAG, MOCK_BKP_PATH,
                                                                      MOCK_HOST))


class OnsiteHandlerCreateOnsiteOffsiteBackupPathTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'create_remote_dir')
    def test_create_onsite_offsite_backup_paths_create_dir_exception(self, mock_create_remote):
        mock_create_remote.return_value = False

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.create_onsite_offsite_backup_paths(MOCK_BKP_DESTINATION,
                                                                   MOCK_BKP_PATH)

        self.assertEqual(cex.exception.message, "Folder 'mock_bkp_dest' could not be "
                                                "created on offsite.")

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'create_remote_dir')
    def test_create_onsite_offsite_backup_paths_create_path_exception(self, mock_create_remote,
                                                                      mock_create_path):
        mock_create_remote.return_value = True
        mock_create_path.return_value = False

        self.onsite_handler.onsite_deployment_config.name = MOCK_DEPLOYMENT_NAME

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.create_onsite_offsite_backup_paths(MOCK_BKP_DESTINATION,
                                                                   MOCK_BKP_PATH)

        self.assertEqual(cex.exception.message, "Temporary folder 'mock_bkp_path' could not "
                                                "be created for customer mock_deployment.")

    @mock.patch(MOCK_PACKAGE + 'create_path')
    @mock.patch(MOCK_PACKAGE + 'create_remote_dir')
    def test_create_onsite_offsite_backup_paths_create_path_exception(self, mock_create_remote,
                                                                      mock_create_path):
        mock_create_remote.return_value = True
        mock_create_path.return_value = True

        self.onsite_handler.onsite_deployment_config.name = MOCK_DEPLOYMENT_NAME

        self.assertTrue(self.onsite_handler.create_onsite_offsite_backup_paths(MOCK_BKP_DESTINATION,
                                                                               MOCK_BKP_PATH))


class OnsiteHandlerProcessBackupTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'compress_file')
    def test_process_backup_processing_exception(self, mock_compress_file):
        mock_compress_file.side_effect = Exception("Processing exception")
        with mock.patch(MOCK_PACKAGE + 'mp'):
            with self.assertRaises(Exception):
                self.onsite_handler.process_backup(MOCK_BKP_PATH, MOCK_BKP_DESTINATION)

    @mock.patch('network_backup_offsite.gnupg_manager.GnupgManager.encrypt_file')
    @mock.patch(MOCK_PACKAGE + 'os')
    @mock.patch(MOCK_PACKAGE + 'compress_file')
    def test_process_backup_success(self, mock_compress_file, mock_os, mock_gnupg_manager):
        mock_compress_file.return_value = MOCK_BKP_TAG_COMPRESSED
        mock_os.path.dirname.return_value = MOCK_BKP_TAG_COMPRESSED
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_gnupg_manager.encrypt_file.return_value = MOCK_BKP_TAG_ENCRYPTED
        self.onsite_handler.gpg_manager = mock_gnupg_manager

        calls = [mock.call("Archiving backup directory 'mock_bkp_path'."),
                 mock.call("The backup 'mock_bkp_tag.tar' archived successfully."),
                 mock.call("Encrypting the backup 'mock_bkp_tag.tar'."),
                 mock.call("Backup 'mock_bkp_tag.tar.gpg' encrypted successfully.")]

        with mock.patch(MOCK_PACKAGE + 'mp'):
            self.assertEqual(self.onsite_handler.process_backup(MOCK_BKP_PATH,
                                                                MOCK_BKP_DESTINATION),
                             MOCK_BKP_TAG_ENCRYPTED)

        self.onsite_handler.logger.info.assert_has_calls(calls)


class OnsiteHandlerTransferBackupToOffsiteTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'RsyncManager')
    def test_transfer_backup_to_offsite_transfer_exception(self, mock_rsync_manager):
        self.onsite_handler.offsite_config.host = MOCK_HOST
        mock_rsync_manager.transfer_file.side_effect = Exception("Transfer exception")

        calls = [mock.call("Error while transferring backup mock_bkp_tag to offsite, "
                           "Cause: Transfer exception")]

        self.assertFalse(self.onsite_handler.transfer_backup_to_offsite(MOCK_BKP_TAG,
                                                                        MOCK_BKP_PATH,
                                                                        MOCK_BKP_DESTINATION))
        self.onsite_handler.logger.error.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'RsyncManager')
    def test_transfer_backup_to_offsite_success(self, mock_rsync_manager):
        self.onsite_handler.offsite_config.host = MOCK_HOST
        mock_rsync_manager.transfer_file.return_value = ""

        calls = [mock.call("Transferring backup 'mock_bkp_path' to 'root@127.0.0.1:mock_bkp_dest'"),
                 mock.call("The backup 'mock_bkp_path' was successfully transferred to offsite.")]

        self.assertTrue(self.onsite_handler.transfer_backup_to_offsite(MOCK_BKP_TAG,
                                                                       MOCK_BKP_PATH,
                                                                       MOCK_BKP_DESTINATION))
        self.onsite_handler.logger.info.assert_has_calls(calls)


class OnsiteHandlerDeleteTmpBkpFolderTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'remove_path')
    def test_delete_tmp_bkp_folder_path_removal_exception(self, mock_remove_path):
        mock_remove_path.side_effect = Exception("Removal exception")
        self.onsite_handler.bkp_temp_folder = MOCK_BKP_PATH

        with self.assertRaises(Exception) as cex:
            self.onsite_handler.delete_tmp_bkp_folder()

        self.assertEqual(cex.exception.message, "Removal exception")

    @mock.patch(MOCK_PACKAGE + 'remove_path')
    def test_delete_tmp_bkp_folder_success(self, mock_remove_path):
        mock_remove_path.return_value = True
        self.onsite_handler.bkp_temp_folder = MOCK_BKP_PATH

        calls = [mock.call("Deleting the temporary folder: 'mock_bkp_path'."),
                 mock.call("Temporary folder: 'mock_bkp_path' deleted successfully.")]

        self.assertIsNone(self.onsite_handler.delete_tmp_bkp_folder())

        self.onsite_handler.logger.log_info.assert_has_calls(calls)


class OnsiteHandlerPerformOnsiteRetentionTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backup_dirs_list_to_cleanup')
    def test_perform_onsite_retention_no_remove_list(self, mock_get_cleanup_list):
        mock_get_cleanup_list.return_value = []

        result, message, result_list = self.onsite_handler.perform_onsite_retention(0)

        self.assertTrue(result)
        self.assertEqual(message, "Onsite clean up finished successfully with no backups removed.")
        self.assertEqual(result_list, [])

    @mock.patch(MOCK_PACKAGE + 'get_values_from_dict')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backup_dirs_list_to_cleanup')
    def test_perform_onsite_retention_cleanup_exception(self, mock_get_cleanup_list,
                                                     mock_get_values):
        mock_get_cleanup_list.return_value = [MOCK_BKP_PATH]
        mock_get_values.side_effect = Exception("Retention exception")
        self.onsite_handler.onsite_deployment_config = EnmConfig(MOCK_BKP_TAG, MOCK_BKP_PATH)

        result, message, result_list = self.onsite_handler.perform_onsite_retention(0)

        self.assertFalse(result)
        self.assertEqual(message, "Retention exception")
        self.assertEqual(result_list, [])

    @mock.patch(MOCK_PACKAGE + 'remove_path')
    @mock.patch(MOCK_PACKAGE + 'os')
    @mock.patch(MOCK_PACKAGE + 'get_values_from_dict')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backup_dirs_list_to_cleanup')
    def test_perform_onsite_retention_directory_not_removed(self, mock_get_cleanup_list,
                                                            mock_get_values, mock_os,
                                                            mock_remove_path):
        mock_get_cleanup_list.return_value = [MOCK_BKP_PATH]
        mock_get_values.return_value = [EnmConfig(MOCK_BKP_TAG, MOCK_BKP_PATH)]
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_remove_path.return_value = False

        result, message, result_list = self.onsite_handler.perform_onsite_retention(0)

        self.assertFalse(result)
        self.assertEqual(message, "Following backups were not removed: ['mock_bkp_path']")
        self.assertEqual(result_list, [])

    @mock.patch(MOCK_PACKAGE + 'remove_path')
    @mock.patch(MOCK_PACKAGE + 'os')
    @mock.patch(MOCK_PACKAGE + 'get_values_from_dict')
    @mock.patch(MOCK_PACKAGE + 'OnsiteHandler.get_onsite_backup_dirs_list_to_cleanup')
    def test_perform_onsite_retention_success(self, mock_get_cleanup_list,mock_get_values,
                                              mock_os, mock_remove_path):
        mock_get_cleanup_list.return_value = [MOCK_BKP_PATH]
        mock_get_values.return_value = [EnmConfig(MOCK_BKP_TAG, MOCK_BKP_PATH)]
        mock_os.path.join.return_value = MOCK_BKP_PATH
        mock_remove_path.return_value = True

        calls = [mock.call("Performing clean up on onsite.")]

        result, message, result_list = self.onsite_handler.perform_onsite_retention(0)

        self.assertTrue(result)
        self.assertEqual(message, "Onsite backups clean up finished successfully, removed "
                                  "backups: ")
        self.assertEqual(result_list, [MOCK_BKP_PATH])

        self.onsite_handler.logger.log_info.assert_has_calls(calls)


class OnsiteHandlerGetOnsiteBackupDirsListToCleanupTestCase(unittest.TestCase):

    @classmethod
    def setUp(cls):
        """Set up the test constants."""
        cls.onsite_handler = create_onsite_object()

    @mock.patch(MOCK_PACKAGE + 'os')
    @mock.patch('__builtin__.next')
    @mock.patch(MOCK_PACKAGE + 'get_values_from_dict')
    def test_get_onsite_backup_dirs_list_to_cleanup_warning(self, mock_get_values, mock_next,
                                                            mock_os):
        mock_get_values.return_value = [EnmConfig(MOCK_BKP_TAG, MOCK_BKP_PATH)]
        mock_next.return_value = MOCK_BKP_DESTINATION, [MOCK_BKP_TAG_ENCRYPTED], MOCK_BKP_TAG
        mock_os.path.join.return_value = MOCK_BKP_PATH

        calls = [mock.call("1 backup(s) found onsite. Retention is 2. Nothing to do.")]

        self.assertEqual(self.onsite_handler.get_onsite_backup_dirs_list_to_cleanup(2), [])

        self.onsite_handler.logger.warning.assert_has_calls(calls)

    @mock.patch(MOCK_PACKAGE + 'os')
    @mock.patch('__builtin__.next')
    @mock.patch(MOCK_PACKAGE + 'get_values_from_dict')
    def test_get_onsite_backup_dirs_list_to_cleanup_success(self, mock_get_values, mock_next,
                                                            mock_os):
        mock_get_values.return_value = [EnmConfig(MOCK_BKP_TAG, MOCK_BKP_PATH,
                                                  MOCK_ONSITE_RETENTION_VALUE)]
        mock_next.return_value = MOCK_BKP_DESTINATION, [MOCK_BKP_TAG_ENCRYPTED], MOCK_BKP_TAG
        mock_os.path.join.return_value = MOCK_BKP_PATH

        calls = [mock.call("Checking the path 'mock_bkp_path' to prepare onsite cleanup.")]

        self.assertEqual([], self.onsite_handler.get_onsite_backup_dirs_list_to_cleanup(
            MOCK_ONSITE_RETENTION_VALUE, MOCK_BKP_PATH))

        self.onsite_handler.logger.info.assert_has_calls(calls)









