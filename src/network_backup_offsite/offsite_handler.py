##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

"""Module to handle network backup download and related sub-procedures."""

# For the snake_case comments (invalid test names)
# pylint: disable=C0103

import os
import time

from network_backup_offsite.logger import CustomLogger
from network_backup_offsite.azcopy_manager import AzCopyManager
from network_backup_offsite.utils import create_path, decompress_file, popen_communicate, \
    PROCESSED_BACKUP_ENDS_WITH, remove_remote_dir, TIMEOUT

SCRIPT_FILE = os.path.basename(__file__).split('.')[0]


class OffsiteHandler:
    """Class to encapsulate the components related to backup upload feature."""

    def __init__(self, gpg_manager, offsite_config, onsite_deployment_config_dict, logger,
                 rsync_ssh=True):
        """
        Initialize Offsite Backup Handler object.

        :param gpg_manager: gpg manager object to handle decrypt/encrypt tasks.
        :param offsite_config: information about the remote server.
        :param onsite_deployment_config_dict: information list about deployments.
        :param logger: logger object.
        :param rsync_ssh: boolean to determine whether to use rsync over ssh or rsync daemon,
        default value is true, which means use rsync ssh by default.
        """
        self.gpg_manager = gpg_manager
        self.offsite_config = offsite_config
        self.onsite_deployment_config_dict = onsite_deployment_config_dict
        self.remote_root_container_path = self.offsite_config.full_container_path
        self.rsync_ssh = rsync_ssh
        self.logger = CustomLogger(SCRIPT_FILE, logger.log_root_path, logger.log_file_name,
                                   logger.log_level)

        self.root_backup_path_offsite = os.path.join(self.offsite_config.path,
                                                     self.offsite_config.folder)
        self.backup_output_dict = {}

    def get_offsite_backups_list(self, timeout=TIMEOUT):
        """
        Return the list of backups from offsite sorted by date (most recent first).
        :return: a list of backup folders that can be downloaded and processed from offsite.
        """
        self.logger.info("Looking for network device backups on offsite.")

        ls_command = "ls -t -1 {}" \
            .format(self.root_backup_path_offsite)

        stdout, _ = popen_communicate(self.offsite_config.host, ls_command, timeout)
        ls_result_offsite = stdout.split("\n")
        offsite_backups_list = filter(lambda x: x.endswith(".gpg"), ls_result_offsite)

        return offsite_backups_list

    def prepare_and_download_certain_bkp_tag(self, deployment_label, backup_tag,
                                             backup_destination):
        """
        Validate and prepare the backup tag of the backup to be downloaded, then do the download.

        Check if the passed backup tag is empty. If so, then raise an exception.
        Check if the passed backup tag if it exists on offsite. Otherwise raise an exception.

        :param deployment_label: for which deployment the backup will be downloaded.
        :param backup_tag: backup tag to be downloaded from the offsite.
        :param backup_destination: path where the backup will be downloaded.

        :return: true if successful.
        """
        if not backup_tag.strip():
            raise Exception("Empty backup tag was informed.")

        backups_list_offsite = self.get_offsite_backups_list()

        backup_tag = backup_tag + PROCESSED_BACKUP_ENDS_WITH

        if backup_tag not in backups_list_offsite:
            raise Exception("No backup with tag {} was found on offsite.".format(backup_tag))

        self.validate_download_and_process_bkp(deployment_label, backup_tag, backup_destination)

        return True

    def prepare_and_download_newest_bkp_offsite(self, deployment_label,
                                                backup_destination):
        """
        Get the backup tag of the most recent backup available on offsite, then do the download.

        :param deployment_label: for which deployment the backup will be downloaded.
        :param backup_destination: path where the backup will be downloaded.

        :return: tuple: true, backup_tag if successful.
        """
        backups_list_offsite = self.get_offsite_backups_list()

        backup_tag = backups_list_offsite[0]

        self.validate_download_and_process_bkp(deployment_label, backup_tag, backup_destination)

        return True, backup_tag

    def validate_download_and_process_bkp(self, deployment_label, backup_tag, backup_destination):
        """
        Validate and check the download destination and backup tag to be downloaded, then download.

        Check if the desired customer exists before calling the restore function.

        An exception is raised in case of error during the process.

        :param deployment_label: for which deployment the backup will be downloaded.
        :param backup_tag: backup tag to be downloaded from the offsite.
        :param backup_destination: path where the backup will be downloaded.

        :return: true if successful.
        """
        full_bkp_path_to_be_downloaded = os.path.join(self.root_backup_path_offsite, backup_tag)

        try:
            backup_destination = self.validate_bkp_download_destination(deployment_label,
                                                                        backup_destination)

            self.check_backups_in_download_destination(backup_destination, backup_tag)

            self.download_and_process_backup(deployment_label, backup_tag,
                                             full_bkp_path_to_be_downloaded,
                                             backup_destination)

        except Exception as download_exception:
            raise Exception("Failed to download backup '{}' due to '{}'."
                            .format(backup_tag, download_exception.message))

        self.logger.info("Backup '{}' downloaded and processed successfully, "
                         "to destination '{}'.".format(backup_tag, backup_destination))

        return True

    def validate_bkp_download_destination(self, deployment_label, bkp_download_destination=""):
        """
        Validate the informed backup download destination and try to create it.

        If no backup destination was informed through the CLI, then the defaule location will be
        user, which is the deployment's path, found in config.cfg.

        In case of an error, an exception will be raised.

        :param deployment_label: for which deployment the backup will be downloaded.
        :param bkp_download_destination: path where the backup will be downloaded.

        :return: validated backup destination or default value.
        """
        if not bkp_download_destination.strip():
            bkp_download_destination = self.onsite_deployment_config_dict[
                deployment_label].backup_path

            self.logger.warning("Backup download destination was not informed. "
                                "Default location '{}' will be used"
                                .format(bkp_download_destination))

        if not create_path(bkp_download_destination):
            raise Exception("Download destination folder '{}' could not be created onsite."
                            .format(bkp_download_destination))

        return bkp_download_destination

    def check_backups_in_download_destination(self, backup_download_destination, backup_tag):
        """
        Check if onsite has a backup with the same tag as the backup to be downloaded from offsite.

        If the backup is already onsite, log a warning message.
        Try to create the destination folder, where the backup will be downloaded

        In case of an error, a detailed exception will be raised.

        :param backup_download_destination: folder where the backup will be downloaded.
        :param backup_tag: the backup tag, with full extension (e.g: backup.tar.gpg).

        :return: true, if successful.
        """
        backup_name = backup_tag.split(PROCESSED_BACKUP_ENDS_WITH)[0]
        full_destination_to_check = os.path.join(backup_download_destination, backup_name)

        if os.path.exists(full_destination_to_check):
            warning_msg = "The backup with tag {} already exists onsite, under: '{}'. " \
                          "it will be overridden.".format(backup_name, backup_download_destination)
            self.logger.warning(warning_msg)

        if not create_path(backup_download_destination):
            raise Exception("Backup destination folder '{}' could not be created onsite."
                            .format(backup_download_destination))

        return True

    def download_and_process_backup(self, deployment_label, backup_tag, backup_path_to_retrieve,
                                    backup_destination_path):
        """
        Download the backup to the destination directory and process it.

        1. Download the backup defined by backup_path_to_retrieve to the backup_destination_path.
        2. Process the downloaded backup.

        Raise exception if an error occurs during the process.

        :param deployment_label: for which deployment the backup will be downloaded.
        :param backup_tag: backup tag to be downloaded and processed.
        :param backup_path_to_retrieve: backup path on remote location to be downloaded.
        :param backup_destination_path: folder to store the downloaded backup.

        :return: tuple (backup tag, backup output, total time)
        """
        time_start = time.time()


        self.download_backup_from_offsite(backup_tag, self.remote_root_container_path,
                                          backup_destination_path, self.rsync_ssh)

        full_backup_path = os.path.join(backup_destination_path, backup_tag)

        self.process_downloaded_backup(backup_tag, full_backup_path)

        time_end = time.time()

        # it is not possible collect the performance data with timeit in this case.
        total_backup_download_time = time_end - time_start

        bur_id = "download_{}".format(backup_tag)

        return bur_id, self.backup_output_dict, total_backup_download_time

    def download_backup_from_offsite(self, backup_tag, backup_path_offsite,
                                     backup_destination_path, rsync_ssh=True):
        """
        Download the backup from offsite.

        :param backup_tag: backup tag to be downloaded and processed.
        :param backup_path_offsite: remote location of the volume on offsite.
        :param backup_destination_path: folder to store the downloaded backup.
        :param rsync_ssh: rsync mode used (true for ssh/false for daemon).

        :return: tuple (volume name, archived volume name, output dictionary, destination path).
        """
        try:
            transfer_time = []
            full_path = os.path.join( self.remote_root_container_path, backup_tag)

            self.logger.info("Downloading backup {} from {} to {}"
                             .format(backup_tag, full_path, backup_destination_path))

            AzCopyManager.transfer_file(full_path, backup_destination_path)

        except Exception as transfer_exp:
            error_message = "Error while downloading backup {} from offsite path '{}' to '{}' due to {}." \
                .format(backup_tag, full_path, backup_destination_path,transfer_exp.message)
            raise Exception(error_message)

        self.logger.info("Backup {} downloaded successfully to '{}'."
                         .format(backup_tag, backup_destination_path))

    def process_downloaded_backup(self, backup_name, downloaded_backup_path):
        """
        Start processing the downloaded backup.

        Decrypt the backup file, outcome: backup.tar.
        Extract the backup, outcome: backup directory which contains at least 3 files.
        In case of an error during decryption or extraction, a detailed exception will be raised.

        :param backup_name: processed backup name(e.g: backup.tar.gpg).
        :param downloaded_backup_path: full path where the backup was downloaded.

        :return: true, if the backup was processed successfully.
        """
        self.logger.info("Processing the downloaded backup {}.".format(backup_name))

        self.logger.info("Decrypting the backup '{}'.".format(downloaded_backup_path))

        try:
            decrypted_file_name = self.gpg_manager.decrypt_file(downloaded_backup_path, True)
        except Exception as backup_decryption_exp:
            raise Exception(backup_decryption_exp.message)

        self.logger.info("Backup '{}' decrypted successfully, output: '{}'."
                         .format(downloaded_backup_path, decrypted_file_name))

        self.logger.info("Extracting the backup '{}'.".format(decrypted_file_name))

        try:
            extracted_file_path = decompress_file(decrypted_file_name, os.path.dirname(
                decrypted_file_name), True)
        except Exception as backup_extraction_exp:
            raise Exception(backup_extraction_exp.message)

        self.logger.info("Backup '{}' extracted successfully, output: '{}'."
                         .format(decrypted_file_name, extracted_file_path))

        return True

    def list_backups_on_offsite(self):
        """
        Show the backups available on offsite, which are ready to be downloaded.

        In case of an error, a detailed bkp_list_exception will be raised.

        :return: true if the listing finished successfully.
        """
        try:
            backups_list_offsite = self.get_offsite_backups_list()

            self.logger.info("{} backups available on offsite: {}"
                             .format(len(backups_list_offsite), backups_list_offsite))

        except Exception as bkp_list_exception:
            err_msg = "An error occurred while trying to list backups on offsite, cause: {}"\
                .format(bkp_list_exception.message)
            raise Exception(err_msg)

        self.logger.info("Backups listing from offsite finished successfully.")

        return True

    def get_offsite_bkps_dirs_list_to_cleanup(self, offsite_retention):
        """
        Get the list of oldest backups on offsite, in preparation to execute offsite retention.

        :param offsite_retention: how many backups should be kept on offside.

        :return: a list of backup directories to be deleted on offsite if any, empty list otherwise.
        """
        offsite_backups_dirs = self.get_offsite_backups_list()

        dir_to_be_removed_list = []

        offsite_backup_list_size = len(offsite_backups_dirs)

        log_message = "{} backup(s) found on offsite. Retention is {}." \
            .format(offsite_backup_list_size, offsite_retention)

        if offsite_backup_list_size > offsite_retention:
            dir_to_be_removed_list.extend(offsite_backups_dirs[offsite_retention:])

            self.logger.info("{} {} backups should be removed."
                             .format(log_message, offsite_backup_list_size - offsite_retention))
        else:
            self.logger.warning("{} Nothing to do.".format(log_message))

        return dir_to_be_removed_list

    def clean_offsite_backup(self, number_retention):
        """
        Execute the retention policy on offsite according to the specified number_retention.

        1. prepare the list of backup directories to be deleted from offsite.
        2. Try to delete the backups from offsite according to the prepared list.
        3. If the backup was successfully deleted from offsite, then add it to
        validated_removed_list. Otherwise, add it to not_removed_list.

        :return tuple (true, success message, list of removed directories), if no problem happened
                during the process,
                tuple (false, error message, list of removed directories) otherwise.
        """
        self.logger.log_info("Performing clean up on offsite.")

        remove_dir_list = self.get_offsite_bkps_dirs_list_to_cleanup(number_retention)

        if not remove_dir_list:
            return True, "Offsite clean up finished successfully with no backups removed.", []

        try:
            paths_to_remove = []
            for backup_name in remove_dir_list:
                paths_to_remove.append(os.path.join(self.root_backup_path_offsite, backup_name))

            not_removed_list, validated_removed_list = remove_remote_dir(self.offsite_config.host,
                                                                         paths_to_remove)
        except Exception as cleanup_exp:
            return False, cleanup_exp.message, []

        if not_removed_list:
            log_message = "Following backups were not removed: {}".format(not_removed_list)
            return False, log_message, validated_removed_list

        succees_msg = "Offsite backups clean up finished successfully, removed backups: "
        return True, succees_msg, validated_removed_list

