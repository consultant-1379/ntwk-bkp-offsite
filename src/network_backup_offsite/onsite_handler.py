##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

"""Module to handle network backup upload and related sub-procedures."""

# For the snake_case comments (invalid names)
# pylint: disable=C0103

import multiprocessing as mp
import os


from network_backup_offsite.logger import CustomLogger
from network_backup_offsite.azcopy_manager import AzCopyManager
from network_backup_offsite.utils import check_remote_path_exists, compress_file, create_path, \
    create_remote_dir, get_values_from_dict, PROCESSED_BACKUP_ENDS_WITH, remove_path, timeit, \
    timer_delay

SCRIPT_FILE = os.path.basename(__file__).split('.')[0]


class OnsiteHandler:
    """Class to encapsulate the components related to backup upload feature."""

    def __init__(self, offsite_config, onsite_deployment_config, gpg_manager, logger,
                 rsync_ssh=True):
        """
        Initialize Local Backup Handler object.

        :param offsite_config: details of the offsite server.
        :param onsite_deployment_config: onsite deployment details.
        :param gpg_manager: gpg manager object to handle encryption and decryption.
        :param logger: logger object.
        :param rsync_ssh: boolean to determine whether to use rsync over ssh or rsync daemon,
        default value is true, which means use rsync ssh by default.
        """
        self.onsite_deployment_config = onsite_deployment_config
        self.offsite_config = offsite_config
        self.remote_root_path = self.offsite_config.full_path
        self.bkp_temp_folder = self.offsite_config.temp_path
        self.remote_root_container_path = self.offsite_config.full_container_path

        logger_script_reference = "{}_{}".format(SCRIPT_FILE, "network device backup")
        self.logger = CustomLogger(logger_script_reference, logger.log_root_path,
                                   logger.log_file_name, logger.log_level)

        self.gpg_manager = gpg_manager

        self.rsync_ssh = rsync_ssh

        self.backup_output_dict = None

        self.processed_backup_path = None

    def get_onsite_backups_list(self):
        """
        Return the list of valid network device backups sorted by date (most recent first).

        :return: a list of backup folders that can be processed and uploaded to offsite.
        """
        backups_path = self.onsite_deployment_config.backup_path

        if not os.path.exists(backups_path):
            self.logger.error("Invalid backup source path '{}'.".format(backups_path))
            return None

        self.logger.info("Getting the list of valid backups from '{}'.".format(backups_path))

        path, backup_dirs, files = next(os.walk(backups_path))
        if len(backup_dirs) <= 0:
            error_msg = "No backup directories were found for the provided path: '{}'."\
                .format(backups_path)

            self.logger.error(error_msg)
            raise Exception(error_msg)

        valid_dir_list = []
        for backup_dir in backup_dirs:
            full_backup_path = os.path.join(backups_path, backup_dir)

            files = next(os.walk(full_backup_path))
            # TODO should be more configurable than hardcoded "3".
            if len(files) < 3:
                self.logger.warning("Skipped the backup '{}', it has less than 3 files."
                                    .format(full_backup_path))
                continue

            valid_dir_list.append(backup_dir)
            self.logger.info("Added the backup '{}' to list of valid backups."
                             .format(full_backup_path))

        valid_dir_list.sort(key=lambda x: os.path.getmtime(os.path.join(backups_path, x)),
                            reverse=True)

        # refer to [NMAAS-1404] when uploading more than one backup
        valid_dir_list.reverse()

        return valid_dir_list

    @timer_delay
    @timeit
    def process_backup_list(self, **kwargs):
        """
        Process a list of valid backups.

        Validation phase: validate remote and local temporary paths before processing.
        Processing phase: tar, encrypt and upload the backup to offsite.
        A detailed exception will be raised as a list, in case of error(s).

        :param kwargs: for process timing purposes

        :return tuple true, successfully_uploaded_backups if backup list was processed successfully.
        """
        successfully_uploaded_backups = []

        onsite_backups_list = self.get_onsite_backups_list()

        if onsite_backups_list is None or not onsite_backups_list:
            raise Exception("No valid network device backups found.")

        self.prepare_offsite_onsite_main_paths()

        # upload only one backup, the most recent one.
        # onsite_backups_list = [onsite_backups_list[-1]]

        self.logger.log_info("Doing backup of: {}".format(onsite_backups_list))

        backup_error_list = []
        try:
            for current_backup_folder_name in onsite_backups_list:

                if not self.backup_already_on_offsite(current_backup_folder_name,
                                                      self.remote_root_path,
                                                      self.offsite_config.host):

                    self.create_onsite_offsite_backup_paths(self.remote_root_path,
                                                            self.bkp_temp_folder)

                    self.process_backup(current_backup_folder_name,
                                        self.bkp_temp_folder)

                    if self.transfer_backup_to_offsite(current_backup_folder_name,
                                                       self.processed_backup_path,
                                                       self.remote_root_container_path):

                        successfully_uploaded_backups.append(current_backup_folder_name)

            self.delete_tmp_bkp_folder()

        except Exception as backup_exception:
            backup_error_list.append(backup_exception.message)

        if backup_error_list:
            raise Exception(backup_error_list)

        return True, successfully_uploaded_backups

    def prepare_offsite_onsite_main_paths(self):
        """
        Prepare the main directories on onsite & offsite for backup processing.

        An exception will be raised in case of an error.

        :return: true, if completed successfully.
        """
        if not check_remote_path_exists(self.offsite_config.host, self.remote_root_path):
            if not create_remote_dir(self.offsite_config.host, self.remote_root_path):
                raise Exception("Remote directory '{}' could not be created for customer {}."
                                .format(self.remote_root_path, self.onsite_deployment_config.name))

        if not create_path(self.offsite_config.temp_path):
            raise Exception("Local temporary root path '{}' could not be created."
                            .format(self.offsite_config.temp_path))

        if not create_path(self.bkp_temp_folder):
            raise Exception("Local temporary customer path '{}' could not be created"
                            .format(self.bkp_temp_folder))

        return True

    def backup_already_on_offsite(self, backup_tag, backup_path_on_offsite, offsite_host):
        """
        Check a backup with a given tag if it exists with on offsite.

        Raise exception if an error happens during the process.

        :param backup_tag: the backup tag used to do checks on offsite.
        :param backup_path_on_offsite: path of the backup on offsite.
        :param offsite_host: offsite host address, e.g. user@host_ip.

        :return: True if the backup already exists on offsite, otherwise False.
        """
        try:
            processed_backup_name = backup_tag + PROCESSED_BACKUP_ENDS_WITH
            full_bkp_path_offsite = os.path.join(backup_path_on_offsite, processed_backup_name)

            if check_remote_path_exists(offsite_host, full_bkp_path_offsite):
                warning_message = "Offsite has a backup with the same name. The backup {} will " \
                                  "not be uploaded."\
                    .format(backup_tag)

                self.logger.warning(warning_message)
                return True
            else:
                return False
        except Exception as chk_bkp_on_offsite:
            raise chk_bkp_on_offsite.message

    def create_onsite_offsite_backup_paths(self, backup_path_on_offsite, tmp_backup_path_on_onsite):
        """
        Create the offsite and onsite backup paths needed for the processing.

        Raise exception if an error happens during the process.

        :param backup_path_on_offsite: path of the backup on offsite.
        :param tmp_backup_path_on_onsite: temporary path of the backup onsite.

        :return: true, if completed successfully.
        """
        if not create_remote_dir(self.offsite_config.host, backup_path_on_offsite):
            error_message = "Folder '{}' could not be created on offsite."\
                .format(backup_path_on_offsite)

            raise Exception(error_message)

        if not create_path(tmp_backup_path_on_onsite):
            error_message = "Temporary folder '{}' could not be created for customer {}."\
                .format(tmp_backup_path_on_onsite, self.onsite_deployment_config.name)

            raise Exception(error_message)

        return True

    def process_backup(self, backup_folder_name, temp_backup_path_onsite):
        """
        Tar and encrypt the backup.

        If any error happens, a detailed exception will be raised.

        :param backup_folder_name: backup directory name.
        :param temp_backup_path_onsite: backup temporary directory path, config:BKP_TEMP_FOLDER.

        :return: backup id, backup output dictionary. Used by annotated method.
        """
        self.backup_output_dict = mp.Manager().dict()

        orignial_backup_path = os.path.join(self.onsite_deployment_config.backup_path,
                                            backup_folder_name)

        try:

            self.logger.info("Archiving backup directory '{}'.".format(orignial_backup_path))

            archived_backup_path = compress_file(orignial_backup_path, temp_backup_path_onsite, "w")

            self.logger.info("The backup '{}' archived successfully.".format(archived_backup_path))

            self.logger.info("Encrypting the backup '{}'.".format(archived_backup_path))

            encryption_output_path = os.path.dirname(archived_backup_path)

            encrypted_backup_path = self.gpg_manager.encrypt_file(archived_backup_path,
                                                                  encryption_output_path)

            self.processed_backup_path = encrypted_backup_path

            self.logger.info("Backup '{}' encrypted successfully.".format(encrypted_backup_path))

        except Exception as processing_exception:
            raise processing_exception.message

        return encrypted_backup_path

    def transfer_backup_to_offsite(self, backup_name, tmp_backup_path_on_onsite,
                                   destination_on_offsite):
        """
        Transfer the processed backup to offsite.

        A detailed transfer_exception will be raised in case of an error.

        :param backup_name: name of the volume to be transferred.
        :param tmp_backup_path_on_onsite: a folder onsite, where the processed backup is stored.
        :param destination_on_offsite: where the processed backup will be transferred to.

        :return: true, if success; false otherwise.
        """
        try:


            self.logger.info("Transferring backup '{}' to '{}'"
                             .format(tmp_backup_path_on_onsite, destination_on_offsite))

            transfer_time = []
            AzCopyManager.transfer_file(tmp_backup_path_on_onsite, destination_on_offsite)

            if transfer_time:
                self.logger.log_time("Elapsed time to transfer backup '{}' to offsite: "
                                     .format(tmp_backup_path_on_onsite), transfer_time[0])

            self.logger.info("The backup '{}' was successfully transferred to offsite."
                             .format(tmp_backup_path_on_onsite))

        except Exception as transfer_exception:
            self.logger.error("Error while transferring backup {} to offsite, Cause: {}"
                              .format(backup_name, transfer_exception.message))

            return False

        return True

    def delete_tmp_bkp_folder(self):
        """
        Delete the temporary folder specified in config.cfg with BKP_TEMP_FOLDER.

        A detailed exception will be raised in case of an error.
        """
        self.logger.log_info("Deleting the temporary folder: '{}'.".format(self.bkp_temp_folder))

        try:
            if not remove_path(self.bkp_temp_folder):
                err_message = "Error while deleting the temporary backup processing folder '{}'."\
                    .format(self.bkp_temp_folder)
                self.logger.error(err_message)
                raise Exception(err_message)
            else:
                self.logger.log_info("Temporary folder: '{}' deleted successfully."
                                     .format(self.bkp_temp_folder))
        except Exception as bkp_temp_folder_del_exp:
            raise Exception(bkp_temp_folder_del_exp.message)

    def perform_onsite_retention(self, number_retention, backups_path):
        """
        Perform the backups retention policy on onsite, according to the passed retention value.

        A detailed cleanup_exp is raised in case of any error.

        :param number_retention: how many backups to keep onsite.
        :param backups_path: path to onsite backups.
        :return tuple (true, success message, list of removed directories) if no problem happened
                during the process.
                tuple (false, error message, empty list/list of removed directories) otherwise.
        """
        self.logger.log_info("Performing clean up on onsite.")

        onsite_bkp_dirs_to_remove_list = self.get_onsite_backup_dirs_list_to_cleanup(
            number_retention, backups_path)

        if not onsite_bkp_dirs_to_remove_list:
            return True, "Onsite clean up finished successfully with no backups removed.", []

        not_removed_list = []
        validated_removed_list = []

        try:
            for bkp_name_to_remove in onsite_bkp_dirs_to_remove_list:
                fullpath_to_rmv = os.path.join(backups_path, bkp_name_to_remove)

                if not remove_path(fullpath_to_rmv):
                    not_removed_list.append(bkp_name_to_remove)
                else:
                    validated_removed_list.append(bkp_name_to_remove)

            if not_removed_list:
                log_message = "Following backups were not removed: {}".format(not_removed_list)
                raise Exception(log_message)

        except Exception as cleanup_exp:
            if validated_removed_list:
                return False, cleanup_exp.message, validated_removed_list
            else:
                return False, cleanup_exp.message, []

        succees_msg = "Onsite backups clean up finished successfully, removed backups: "
        return True, succees_msg, validated_removed_list

    def get_onsite_backup_dirs_list_to_cleanup(self, onsite_retention, backups_path):
        """
        Get the list of oldest directories to be removed from the onsite.

        :param onsite_retention: how many backups should be kept on onsite.
        :param backups_path: path to onsite backups.
        :return: list of the directories to be removed from onsite.
        """
        onsite_dirs_to_remove_list = []

        self.logger.info("Checking the path '{}' to prepare onsite cleanup."
                         .format(backups_path))

        path, onsite_backups_list, files = next(os.walk(backups_path))
        onsite_backups_list.sort(key=lambda s: os.path.getmtime(os.path.join(backups_path, s)),
                                 reverse=True)

        onsite_backups_list_size = len(onsite_backups_list)

        log_message = "{} backup(s) found onsite. Retention is {}."\
            .format(onsite_backups_list_size, onsite_retention)

        if onsite_backups_list_size > onsite_retention:
            onsite_dirs_to_remove_list.extend(onsite_backups_list[onsite_retention:])

            self.logger.info("{} {} backups should be removed."
                             .format(log_message, onsite_backups_list_size - onsite_retention))
        else:
            self.logger.warning("{} Nothing to do.".format(log_message))

        onsite_dirs_to_remove_list.reverse()
        return onsite_dirs_to_remove_list

