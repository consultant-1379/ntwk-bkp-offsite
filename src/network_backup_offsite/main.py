#!/usr/bin/env python

##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

"""Module for running network backup upload, download, list or retention."""

import argparse
import os
from enum import Enum
import sys


from network_backup_offsite import __version__
from network_backup_offsite.constants import SCRIPT_NAME
from network_backup_offsite.bur_input_validators import SCRIPT_OBJECTS, validate_boolean_input, \
    validate_get_main_logger, validate_input_arguments, validate_log_level, \
    validate_log_root_path, validate_onsite_offsite_locations, validate_script_settings
from network_backup_offsite.exceptions import NotificationHandlerException
from network_backup_offsite.onsite_handler import OnsiteHandler
from network_backup_offsite.logger import logging
from network_backup_offsite.offsite_handler import OffsiteHandler
from network_backup_offsite.utils import format_time, get_filtered_cli_arguments, get_home_dir, \
    get_formatted_timestamp, LOG_ROOT_PATH_CLI, LOG_SUFFIX, timeit, PROCESSED_BACKUP_ENDS_WITH


SCRIPT_OPTION_HELP = "Select the function to be executed.\n" \
                     "    1 - Upload backup to cloud\n" \
                     "    2 - Download backup from cloud\n" \
                     "    3 - List backups on cloud\n" \
                     "    4 - Execute backup retention on cloud"
NUMBER_RSYNC_INSTANCES_HELP = "Select the number of working rsync instances. Defaults to 8."
DO_CLEANUP_HELP = "Whether cleanup NFS and off-site. Defaults to False."
LOG_ROOT_PATH_HELP = "Provide a path to store the logs."
LOG_LEVEL_HELP = "Provide the log level. Options: [CRITICAL, ERROR, WARNING, INFO, DEBUG]."
BACKUP_TAG_HELP = "Provide the backup tag to be restored."
BACKUP_DESTINATION_HELP = "Provide the destination of the restored backup."
RSYNC_SSH_HELP = "Whether to use rsync over ssh. Defaults to False, which means it will use " \
                 "rsync daemon."
USAGE_HELP = "Display detailed help."
NTWK_BKP_VERSION_HELP = "Show currently installed ntwk_bkp version."

SCRIPT_PATH = os.path.dirname(__file__)
SCRIPT_FILE = os.path.basename(__file__).split('.')[0]

CONF_FILE_NAME = 'config.cfg'

MAIN_LOG_FILE_NAME = "ntwk_bkp_{}.{}".format(SCRIPT_FILE, LOG_SUFFIX)
DEFAULT_LOG_ROOT_PATH = os.path.join(get_home_dir(), "network_device_backup_logs")

SUCCESS_EXIT_CODE = 0

EXIT_CODES = Enum('ExitCodes', 'INVALID_INPUT, FAILED_UPLOAD, FAILED_DOWNLOAD, '
                               'FAILED_OFFSITE_CLEANUP, FAILED_VALIDATION')

SCRIPT_OPERATIONS = Enum('ScriptOperations', 'BKP_UPLOAD, BKP_DOWNLOAD, LIST_BKPS ,RETENTION, SIZE')


def main():
    """
    Start the backup upload/download/list/retention processes according to the input.

    1. Validate input parameters.
    2. Read the configuration file and validate it.
    3. Check the connection with offsite environment.
    4. Execute the backup upload/download/list/retention.

    In case of success, return SUCCESS code.

    In case of error, exit with one of the error codes specified by ExitCodes enumerator.
    """
    args = parse_arguments()

    if args.usage:
        usage()

    if args.version:
        show_ntwk_bkp_version()

    logger = validate_get_main_logger(args, MAIN_LOG_FILE_NAME, SCRIPT_OPERATIONS)

    provided_cli_args = get_filtered_cli_arguments()
    if provided_cli_args:
        logger.log_info("Running ntwk_bkp with the following arguments: {}"
                        .format(provided_cli_args))

    config_object_dict = execute_validation_input(args, logger)

    offsite_config = config_object_dict[SCRIPT_OBJECTS.OFFSITE_CONFIG.name]
    deployment_config_dict = config_object_dict[SCRIPT_OBJECTS.DEPLOYMENT_CONFIG_DICT.name]
    gpg_manager = config_object_dict[SCRIPT_OBJECTS.GNUPG_MANAGER.name]
    notification_handler = config_object_dict[SCRIPT_OBJECTS.NOTIFICATION_HANDLER.name]
    delay_config = config_object_dict[SCRIPT_OBJECTS.DELAY_CONFIG.name]

    op_time = []

    if str(args.script_option) == str(SCRIPT_OPERATIONS.BKP_UPLOAD.value):
        execute_backup_upload(deployment_config_dict, offsite_config, gpg_manager,
                              notification_handler, logger, args, delay_config,
                              get_elapsed_time=op_time)

        logger.log_time("Elapsed time to complete the backup upload operation", op_time[0])

    elif str(args.script_option) == str(SCRIPT_OPERATIONS.BKP_DOWNLOAD.value):
        execute_backup_download(deployment_config_dict, offsite_config, gpg_manager,
                                notification_handler, logger, args)

    elif str(args.script_option) == str(SCRIPT_OPERATIONS.LIST_BKPS.value):
        execute_list_offsite_backups(deployment_config_dict, offsite_config, gpg_manager, logger,
                                     args)

    elif str(args.script_option) == str(SCRIPT_OPERATIONS.RETENTION.value):
        execute_offsite_backup_cleanup(deployment_config_dict, offsite_config, gpg_manager,
                                       notification_handler, logger, args)

    else:
        logger.log_error_exit("Operation {} not supported.".format(args.script_option),
                              EXIT_CODES.INVALID_INPUT.value)

    return SUCCESS_EXIT_CODE


def execute_validation_input(args, logger):
    """
    Validate the configuration file and input arguments.

    :param args: argument object.
    :param logger: logger object.

    :return: configuration object dictionary if success, exit with INVALID_INPUT error code.
    """
    script_objects = {}
    try:
        script_objects = validate_script_settings(CONF_FILE_NAME, script_objects, logger)

        validate_onsite_offsite_locations(CONF_FILE_NAME, script_objects, logger)

        validate_input_arguments(args, SCRIPT_OPERATIONS)

    except Exception as validation_exception:
        if script_objects and SCRIPT_OBJECTS.NOTIFICATION_HANDLER.name in script_objects.keys():
            notification_handler = script_objects[SCRIPT_OBJECTS.NOTIFICATION_HANDLER.name]

            operation = "Input Validation"
            report_error(notification_handler, logger, operation, validation_exception.message,
                         EXIT_CODES.FAILED_VALIDATION.value, None, exit_script=True)
        else:
            logger.log_error_exit(validation_exception.message, EXIT_CODES.FAILED_VALIDATION.value)

    return script_objects


@timeit
def execute_backup_upload(deployment_config_dict, offsite_config, gpg_manager,
                          notification_handler, logger, args, delay_config, **kwargs):
    """
    Go over the deployment list and trigger their backup processes.

    If deployment label was provided, it will perform the backup of this single deployment.

    :param deployment_config_dict: dictionary with the configuration per deployment.
    :param offsite_config: offsite object.
    :param gpg_manager: gpg manager object.
    :param notification_handler: object to send e-mail in case of error.
    :param logger: logger object.
    :param args: the CLI arguments.
    :param delay_config: max time to wait for an operation before sending a notification email.

    :return: true if success, exit with FAILED_UPLOAD error code.
    """
    operation = SCRIPT_OPERATIONS.BKP_UPLOAD.name
    success_message_list = []
    onsite_handler = None

    try:
        for deployment_config in deployment_config_dict.values():
            if not os.path.exists(deployment_config.backup_path):
                logger.error("Backup path '{}' does not exist."
                             .format(deployment_config.backup_path))
                continue

            onsite_handler = OnsiteHandler(offsite_config, deployment_config, gpg_manager,
                                           logger, args.rsync_ssh)

            upload_time = []

            report_delay_args = [deployment_config.name, operation, delay_config.max_delay,
                                 get_formatted_timestamp(), notification_handler, logger]

            no_upload_exceptions, successfully_uploaded_backups =  \
                onsite_handler.process_backup_list(get_elapsed_time=upload_time,
                                                   max_delay=delay_config.max_delay,
                                                   on_timeout=report_delay,
                                                   on_timeout_args=report_delay_args)

            if no_upload_exceptions:
                if successfully_uploaded_backups:
                    success_message_list.append("Successfully uploaded backups were:")
                    for uploaded_backup_tag in successfully_uploaded_backups:
                        success_message_list.append(uploaded_backup_tag)
                else:
                    success_message_list.append("No backups to upload to offsite.")

            if upload_time:
                elapsed_msg = "Elapsed time to complete upload"
                success_message_list.append("{}: {}.".format(elapsed_msg,
                                                             format_time(upload_time[0])))
                logger.log_time(elapsed_msg, upload_time[0])

            op_succeeded, success_msg, removed_offsite_bkps = execute_offsite_backup_cleanup(
                deployment_config_dict, offsite_config, gpg_manager, notification_handler,
                logger, args, None)

            if op_succeeded:
                success_message_list.append(prepare_email_body_retention_section(
                    success_msg, removed_offsite_bkps))

            op_succeeded, success_msg, removed_onsite_bkps = execute_onsite_backup_cleanup(
                deployment_config, offsite_config, gpg_manager, notification_handler,
                logger, args, None)

            if op_succeeded:
                success_message_list.append(prepare_email_body_retention_section(
                    success_msg, removed_onsite_bkps))

        # Uncomment to send an email after successful upload, refer to [NMAAS-2692].
        # report_success(notification_handler, logger, operation, success_message_list, SCRIPT_NAME)

    except Exception as upload_exception:
        logger.error(upload_exception.message)
        onsite_handler.delete_tmp_bkp_folder()
        report_error(notification_handler, logger, operation, upload_exception.message,
                     EXIT_CODES.FAILED_UPLOAD.value, SCRIPT_NAME)

    return True


@timeit
def execute_backup_download(deployment_config_dict, offsite_config, gpg_manager,
                            notification_handler, logger, args, **kwargs):
    """
    Call download backup function.

    :param deployment_config_dict: dictionary with deployment configuration data.
    :param offsite_config: offsite object.
    :param gpg_manager: gpg manager object.
    :param notification_handler: object to send e-mail in case of error.
    :param logger: logger object.
    :param args: the CLI arguments.

    :return: true if success, exit with FAILED_DOWNLOAD error code.
    """
    operation = SCRIPT_OPERATIONS.BKP_DOWNLOAD.name
    deployment_label = ""
    success_list = []
    try:

        for deployment_config in deployment_config_dict.values():
            deployment_label = deployment_config.name

            offsite_handler = OffsiteHandler(gpg_manager, offsite_config, deployment_config_dict,
                                             logger, args.rsync_ssh)

            if args.backup_tag is None or not args.backup_tag.strip():

                no_download_exceptions, downloaded_backup_name = \
                    offsite_handler.prepare_and_download_newest_bkp_offsite(
                        deployment_config.name, args.backup_destination)

                downloaded_backup_tag = downloaded_backup_name.split(PROCESSED_BACKUP_ENDS_WITH)[0]

                success_list.append("The most recent backup {} was downloaded successfully."
                                    .format(downloaded_backup_tag))
            else:
                offsite_handler.prepare_and_download_certain_bkp_tag(deployment_config.name,
                                                                     args.backup_tag,
                                                                     args.backup_destination)

                success_list.append("The backup {} was downloaded successfully."
                                    .format(args.backup_tag))

        # Uncomment to send an email after successful download, refer to [NMAAS-2692].
        # report_success(notification_handler, logger, operation, success_list, deployment_label)

    except Exception as backup_restore_exception:
        report_error(notification_handler, logger, operation, backup_restore_exception.message,
                     EXIT_CODES.FAILED_DOWNLOAD.value, deployment_label, exit_script=True)

    return True


def execute_list_offsite_backups(deployment_config_dict, offsite_config, gpg_manager, logger, args):
    """
    Perform the backup offsite cleanup for all deployments.

    If more than 3 backups are found on offsite, the oldest one will be deleted.

    :param deployment_config_dict: dictionary with all enmaas configuration data.
    :param offsite_config: offsite object.
    :param gpg_manager: gpg manager object.
    :param logger: logger object.
    :param args: the CLI arguments.

    :return: true if success, exit with FAILED_OFFSITE_CLEANUP error code.
    """
    offsite_handler = OffsiteHandler(gpg_manager, offsite_config, deployment_config_dict, logger,
                                     args.rsync_ssh)

    offsite_handler.list_backups_on_offsite()

    return True


def execute_offsite_backup_cleanup(deployment_config_dict, offsite_config, gpg_manager,
                                   notification_handler, logger, args, deployment_label=None):
    """
    Perform the backup offsite cleanup for all deployments.

    If more than 3 backups were found on offsite, the oldest one will be deleted.

    :param deployment_config_dict: dictionary with all enmaas configuration data.
    :param offsite_config: offsite object.
    :param gpg_manager: gpg manager object.
    :param notification_handler: object to send e-mail in case of error.
    :param logger: logger object.
    :param args: the CLI arguments.
    :param deployment_label: informed in case of executing clean-up right after backup.

    :return: true if success, exit with FAILED_OFFSITE_CLEANUP error code.
    """
    offsite_backup_handler = OffsiteHandler(gpg_manager,
                                            offsite_config,
                                            deployment_config_dict,
                                            logger,
                                            args.rsync_ssh)

    cleanup_status, out_msg, removed_dirs = \
        offsite_backup_handler.clean_offsite_backup(offsite_config.offsite_retention)

    if not cleanup_status:
        report_error(notification_handler, logger, SCRIPT_OPERATIONS.RETENTION.name, out_msg,
                     EXIT_CODES.FAILED_OFFSITE_CLEANUP.value, deployment_label, exit_script=True)

    logger.info(out_msg)

    if removed_dirs:
        logger.info("Removed directories were: {}".format(removed_dirs))

    return cleanup_status, out_msg, removed_dirs


def execute_onsite_backup_cleanup(deployment_config_dict, offsite_config, gpg_manager,
                                  notification_handler, logger, args, deployment_label=None,):
    """
    Perform onsite backup cleanup for the provided path under config section[network_dev_backups].

    If there are more than 2 backups onsite, the oldest ones will be deleted.

    :param deployment_config_dict: dictionary with all enmaas configuration data.
    :param offsite_config: offsite object.
    :param gpg_manager: gpg manager object.
    :param notification_handler: object to send e-mail in case of error.
    :param logger: logger object.
    :param args: the CLI arguments.
    :param deployment_label: informed in case of executing clean-up right after backup.

    :return: true if success, exit with FAILED_OFFSITE_CLEANUP error code.
    """
    onsite_handler = OnsiteHandler(offsite_config, deployment_config_dict, gpg_manager, logger,
                                   args.rsync_ssh)

    successful_retention_onsite, out_msg, removed_dirs = \
        onsite_handler.perform_onsite_retention(deployment_config_dict.onsite_retention,
                                                deployment_config_dict.backup_path)

    if not successful_retention_onsite:
        report_error(notification_handler, logger, SCRIPT_OPERATIONS.RETENTION.name, out_msg,
                     EXIT_CODES.FAILED_OFFSITE_CLEANUP.value, deployment_label, exit_script=True)

    logger.info(out_msg)

    if removed_dirs:
        logger.info("Removed directories were: {}".format(removed_dirs))

    return successful_retention_onsite, out_msg, removed_dirs


def prepare_email_body_retention_section(success_msg, removed_backups):
    """
    Prepare an email ready information section about the retention operation.

    :param success_msg: success message shown after successful retention operation.
    :param removed_backups: the backup tags which were removed after performing the retention op.
    :return: an email ready string about the successful retention operation outcome.
    """
    if removed_backups:
        retention_info = success_msg + "<br>"
        for removed_backup_tag in removed_backups:
            retention_info += removed_backup_tag + "<br>"
        return "<br>" + retention_info
    else:
        return "<br>" + success_msg


def report_error(notification_handler, logger, operation, error_list, error_code, sender,
                 exit_script=False):
    """
    In case of error during backup operation, log the returned error, send email and exit.

    :param notification_handler: object that process the e-mail sending.
    :param logger: logger object.
    :param operation: operation that raised the error.
    :param error_list: raised error message.
    :param error_code: error code.
    :param sender: deployment label that the operation was triggered for.
    :param exit_script: if the report should finish the script and exit the execution.

    :return true if success.
    """
    try:
        operation = get_readable_operation_name(operation)
        subject = "Error executing BUR {} Operation".format(operation)

        if sender is None or not sender.strip():
            sender = SCRIPT_NAME

        notification_handler.send_error_email(sender, subject, error_list, error_code)

    except NotificationHandlerException as notification_exp:
        logger.error(notification_exp.message)

    if exit_script:
        logger.log_error_exit("BUR Operation finished.", error_code)

    return True


def report_success(notification_handler, logger, operation, success_list, sender):
    """
    In case of error during backup operation, log the returned error, send email and exit.

    :param notification_handler: object that process the e-mail sending.
    :param logger: logger object.
    :param operation: operation that triggered success e-mail.
    :param success_list: list of success messages.
    :param sender: deployment label that the operation was triggered for.

    :return true if success.
    """
    try:
        operation = get_readable_operation_name(operation)
        report_title = "Network Device {} Operation finished".format(operation)
        if sender is None or not sender.strip():
            sender = SCRIPT_NAME

        notification_handler.send_success_email(sender, report_title, success_list)

    except NotificationHandlerException as notification_exp:
        logger.error(notification_exp.message)

    return True


def report_delay(customer_name, operation, max_delay, start_time, notification_handler, logger):
    """
    In case of delay during backup operation, send a notification e-mail.

    :param customer_name: customer that the operation was triggered for.
    :param operation: operation that triggered success e-mail.
    :param max_delay: max running time for the process.
    :param start_time: time when the operation started.
    :param notification_handler: object that process the e-mail sending.
    :param logger: logger object.
    """
    operation = get_readable_operation_name(operation)

    subject = "Max delay reached - offsite network device backup script - {} Operation"\
        .format(operation)

    logger.warning(subject)

    message_list = list()
    message_list.append("{} for {} is taking longer than expected."
                        .format(operation, customer_name))
    message_list.append("{} started at {} and is still running.".format(operation, start_time))
    message_list.append("Max delay time defined ({}s) was reached.".format(max_delay))

    try:
        notification_handler.send_warning_email(SCRIPT_NAME, subject, message_list)

    except NotificationHandlerException as notification_exception:
        logger.error(notification_exception.__str__())


def get_readable_operation_name(operation):
    """
    Format Enum values to readable string.

    :param operation: name value from ScriptOperations

    :return: formatted string
    """
    if operation == SCRIPT_OPERATIONS.BKP_UPLOAD.name:
        return "Backup Upload"
    if operation == SCRIPT_OPERATIONS.BKP_DOWNLOAD.name:
        return "Backup Download"
    if operation == SCRIPT_OPERATIONS.RETENTION.name:
        return "Cleanup"
    return operation


def parse_arguments():
    """
    Parse input arguments.

    :return: parsed arguments .
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--script_option", default=1, help=SCRIPT_OPTION_HELP)
    parser.add_argument("--do_cleanup", default=False, help=DO_CLEANUP_HELP)
    parser.add_argument("--do_onsite_cleanup", default=False, help=DO_CLEANUP_HELP)
    parser.add_argument(LOG_ROOT_PATH_CLI, nargs='?', default=DEFAULT_LOG_ROOT_PATH,
                        help=LOG_ROOT_PATH_HELP)
    parser.add_argument("--log_level", nargs='?', default=logging.INFO, help=LOG_LEVEL_HELP)
    parser.add_argument("--backup_tag", help=BACKUP_TAG_HELP)
    parser.add_argument("--backup_destination", nargs='?', help=BACKUP_DESTINATION_HELP)
    parser.add_argument("--rsync_ssh", default=False, help=RSYNC_SSH_HELP)
    parser.add_argument("--usage", action="store_true", help=USAGE_HELP)
    parser.add_argument("--version", action="store_true", help=NTWK_BKP_VERSION_HELP)

    args = parser.parse_args()

    args.log_root_path = validate_log_root_path(args.log_root_path, DEFAULT_LOG_ROOT_PATH)
    args.log_level = validate_log_level(args.log_level)
    args.do_cleanup = validate_boolean_input(args.do_cleanup)
    args.do_onsite_cleanup = validate_boolean_input(args.do_onsite_cleanup)
    args.rsync_ssh = validate_boolean_input(args.rsync_ssh)

    return args


def usage():
    """
    Display this usage help message whenever the script is run with '--usage' argument.

    :param logger:    logger object.
    :param exit_code: exit code to quit this application with after running this method.
    """
    print("""
        Usage of: '{}'

        This message is displayed when script is run with '--usage' argument.
        ============================================================================================
                                            Overview:
        ============================================================================================
        This script is for automating the process of offsite upload and download for network confgs.
        The genie-bur network device backup requirements are defined under Jira issue NMAAS-1812:
        (https://jira-nam.lmera.ericsson.se/browse/NMAAS-1812).

        It basically does the following for each option:

        1. Upload.

        1.1 Read and parse the parameters from a configuration file.
        1.2 Validate the input arguments and the current settings.
        1.3 Tar the backup directory.
        1.4 Encrypt the backup file using gpg tool.
        1.5 Upload to Azure.
        1.5 If cleanup option is enabled, delete the oldest backup sets on offsite.
        The deletion will be for the backups other than the most recent four.
        1.6 Send an email to notify about a successful backup upload.

        2. Download.

        2.1 Download a specific backup if the Backup tag was provided,
        otherwise download the most recent backup.
        2.2 Download the backup to the specific destination if it was provided through CLI,
        otherwise download it the default path specified in the config file "BACKUPS_PATH".
        2.3 Once the backups is downloaded, decrypt and extract the backup content.
        2.4 Send an email to notify about a successful backup download.

        3. List backups.

        3.1 List the downloadable backups on Azure.

        4. Retention.

        4.1 Delete any backup sets, other than four most recent backups on Azure.

        ============================================================================================
                                    Script Exit Codes:
        ============================================================================================

        The following error codes can be raised in case of other failures during the process:

        INVALID_INPUT (2): Error while validating input arguments or configuration file.
        FAILED_UPLOAD (3): Error while executing the upload function.
        FAILED_DOWNLOAD (4): Error while executing the download function.
        FAILED_OFFSITE_CLEANUP (5): Error while executing the cleanup function.

        ============================================================================================
                                        Configuration File ({}):
        ============================================================================================

        The script depends on a configuration file '{}' for all operations.
        The operations are: Upload, Download, List, Retention.

        --------------------------------------------------------------------------------------------
        It must contain the following sections:

        [SUPPORT_CONTACT]
        EMAIL_TO       Email address to send failure notifications.
        EMAIL_URL      URL of the email service.

        [GNUPG]
        GPG_USER_NAME  User name used by gpg to create a encryption key.
        GPG_USER_EMAIL Use email for gpg usage.

        [OFFSITE_CONN]
        IP              remote ip address.
        USER            server user.
        BKP_PATH        remote root path where the backups will be placed.
        BKP_DIR         remote folder name where the backups will be stored. This folder will be
                        created in the BKP_PATH if it does not exist.
        BKP_TEMP_FOLDER local temporary folder to store files during the upload process before
                        transferring.

        For example:

        [SUPPORT_CONTACT]
        EMAIL_TO=fo-enmaas@ericsson.com
        EMAIL_URL=https://172.31.2.5/v1/emailservice/send

        [GNUPG]
        GPG_USER_NAME=backup
        GPG_USER_EMAIL=backup@root.com

        [OFFSITE_CONN]
        IP=10.1.100.4
        USER=root
        BKP_PATH=/offsite_azure
        BKP_DIR=network_dev_backups
        BKP_TEMP_FOLDER=/data1/ntwk_bkp_tmp

        [network_dev_backups]
        DEPLOYMENT_PATH=/data1/network_dev_backups/

        Note: Path variables should not contain quotes.

        ============================================================================================
        ============================================================================================
        """.format(SCRIPT_FILE, CONF_FILE_NAME, CONF_FILE_NAME))

    sys.exit(SUCCESS_EXIT_CODE)


def show_ntwk_bkp_version():
    """
    Display currently installed ntwk_bkp_offsite version, when running with '--version' argument.
    """
    print "ntwk_bkp_offsite version: {}".format(__version__)

    sys.exit(SUCCESS_EXIT_CODE)


if __name__ == '__main__':
    RET = main()
    sys.exit(RET)
