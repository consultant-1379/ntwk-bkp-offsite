##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For snake_case comments (invalid-name)
# pylint: disable=C0103

"""Module to handle all kinds of input validations prior to core processing."""

from enum import Enum
import logging
import os

from network_backup_offsite.backup_settings import ScriptSettings
from network_backup_offsite.exceptions import BackupSettingsException
from network_backup_offsite.logger import CustomLogger
from network_backup_offsite.utils import check_remote_path_exists, create_path, \
    create_remote_dir, is_host_accessible, is_valid_ip, LOG_SUFFIX

SCRIPT_OBJECTS = Enum('SCRIPT_OBJECTS', 'NOTIFICATION_HANDLER, OFFSITE_CONFIG, GNUPG_MANAGER, '
                                        'DEPLOYMENT_CONFIG_DICT, DELAY_CONFIG, SIZE')


def validate_get_main_logger(console_input_args, main_script_file_name, bur_operation_enum):
    """
    Validate and get the main logger object, which is created based on the selected operation.

    Raise an exception if an error happens while creating the new log object.

    :param console_input_args: arguments passed to the console.
    :param main_script_file_name: name of the main script.
    :param bur_operation_enum: enumerator defined by main.py with the valid operations supported
    by BUR.

    :return: custom logger object.
    """
    try:
        operation = validate_script_option_argument(console_input_args.script_option,
                                                    bur_operation_enum.SIZE.value)

        main_log_file_name = prepare_log_file_name(operation, bur_operation_enum,
                                                   console_input_args.backup_tag)

        return CustomLogger(main_script_file_name, console_input_args.log_root_path,
                            main_log_file_name, console_input_args.log_level)

    except Exception as invalid_script_opt_exp:
        logger = CustomLogger(main_script_file_name, "")

        logger.log_error_exit("Error creating the logger object. Cause: {}."
                              .format(invalid_script_opt_exp.message))


def prepare_log_file_name(operation, script_operations_enum, backup_tag):
    """
    Prepare a meaningful log file name based on the provided cli arguments.

    Raise an exception if an invalid operation is passed.

    :param operation: the script option, refer to --script_option to see the possible values.
    :param script_operations_enum: enumerator defined by main.py with the valid operations
    supported by BUR.
    :param backup_tag: the provided value for --backup_tag, if any.

    :return: a meaningful log file name based on the required operation and the passed parameters.
    """
    if operation == int(script_operations_enum.BKP_UPLOAD.value):
        main_log_file_name = "network_device_backup_upload.{}".format(LOG_SUFFIX)

    elif operation == int(script_operations_enum.BKP_DOWNLOAD.value):
        if backup_tag is not None:
            if backup_tag.strip():
                main_log_file_name = "{}_download.{}".format(backup_tag, LOG_SUFFIX)
            else:
                main_log_file_name = "error_download.{}".format(LOG_SUFFIX)
        else:
            main_log_file_name = "network_device_backup_download.{}".format(LOG_SUFFIX)

    elif operation == int(script_operations_enum.LIST_BKPS.value):
        main_log_file_name = "list_network_device_backups.{}".format(LOG_SUFFIX)

    elif operation == int(script_operations_enum.RETENTION.value):
        main_log_file_name = "network_device_backup_retention.{}".format(LOG_SUFFIX)

    else:
        raise Exception("Operation {} not supported.".format(operation))

    return main_log_file_name


def validate_log_root_path(log_root_path, default_log_root_path):
    """
    Validate the informed log root path.

    Try to create this path if it does not exist.

    Raise an exception if an error occurs.

    :param log_root_path: log root path to be validated.
    :param default_log_root_path: default log value..

    :return validated log root path.
    """
    if log_root_path is None or not log_root_path.strip():
        log_root_path = default_log_root_path

    if not create_path(log_root_path):
        raise Exception("Error creating log root path '{}'.".format(log_root_path))

    return log_root_path


def validate_log_level(log_level):
    """
    Validate the informed log level. Sets to INFO when the informed value is invalid.

    :param log_level: log level.
    :return validated log level.
    """
    if log_level in (logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG):
        return log_level

    log_level = str(log_level)

    if str(log_level).lower() == "critical":
        log_level = logging.CRITICAL
    elif str(log_level).lower() == "error":
        log_level = logging.ERROR
    elif str(log_level).lower() == "warning":
        log_level = logging.WARNING
    elif str(log_level).lower() == "info":
        log_level = logging.INFO
    elif str(log_level).lower() == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    return log_level


def validate_boolean_input(bool_arg):
    """
    Convert an input value into boolean.

    :param bool_arg: value to be converted into boolean.
    :return: converted value into boolean.
    """
    if isinstance(bool_arg, str):
        return bool_arg.lower() in ("yes", "true", "t", "1")

    return bool_arg


def validate_script_settings(config_file_name, script_objects, logger, deployment_label=None):
    """
    Validate the config_file parsing and the objects created from it.

    :param config_file_name: BUR configuration file name.
    :param logger: logger object.
    :param script_objects: ScriptSetting objects.
    :param deployment_label: if running the script just for one deployment.

    :return script_objects: ScriptSetting objects validated.
    """
    script_settings = ScriptSettings(config_file_name, logger)

    try:
        script_objects[SCRIPT_OBJECTS.NOTIFICATION_HANDLER.name] = \
            script_settings.get_notification_handler()

        script_objects[SCRIPT_OBJECTS.GNUPG_MANAGER.name] = \
            script_settings.get_gnupg_manager()

        script_objects[SCRIPT_OBJECTS.OFFSITE_CONFIG.name] = \
            script_settings.get_offsite_config()

        script_objects[SCRIPT_OBJECTS.DEPLOYMENT_CONFIG_DICT.name] = \
            script_settings.get_deployment_config_dict(deployment_label)

        script_objects[SCRIPT_OBJECTS.DELAY_CONFIG.name] = \
            script_settings.get_delay_config()

    except BackupSettingsException as exception:
        raise Exception("Error validating ScriptSettings object due to: {}."
                        .format(str(exception)))

    return script_objects


def validate_onsite_offsite_locations(config_file_name, script_objects, logger):
    """
    Validate if onsite and offsite location/server paths.

    :param config_file_name: BUR configuration file name.
    :param script_objects: dictionary of validated ScriptSettings objects.
    :param logger: logger object.
    """
    deployment_config_dict = script_objects[SCRIPT_OBJECTS.DEPLOYMENT_CONFIG_DICT.name]
    offsite_config = script_objects[SCRIPT_OBJECTS.OFFSITE_CONFIG.name]

    validation_error_list = []

    validate_onsite_backup_locations(deployment_config_dict, config_file_name,
                                     validation_error_list)
    validate_offsite_backup_server(offsite_config, config_file_name, logger, validation_error_list)

    validate_retention_config(offsite_config.offsite_retention, validation_error_list)

    for deployment_key in deployment_config_dict.keys():
        deployment_config = deployment_config_dict[deployment_key]
        validate_retention_config(deployment_config.onsite_retention, validation_error_list)

    if validation_error_list:
        raise Exception(validation_error_list)

    return True


def validate_input_arguments(console_input_args, bur_operations_enum):
    """
    Validate the input arguments.

    Raise an exception if there is an error in the validation process.

    :param console_input_args: informed argument object.
    :param bur_operations_enum: BUR operations enumerator.
    """
    validation_error_list = []
    validate_bur_operation_arguments(console_input_args, bur_operations_enum, validation_error_list)

    if validation_error_list:
        raise Exception(validation_error_list)


def validate_script_option_argument(str_script_option, script_option_enum_size):
    """
    Validate the provided value for --script_option, if any.

    Raise an exception in case of an invalid operation.

    :param str_script_option: the value provided with --script_option, if any.
    :param script_option_enum_size: the enum size from main.py to validate that the provided
    value is withing the enum range.

    :return validated integer script operation.
    """
    operation = int(str_script_option)

    if operation <= 0 or operation >= script_option_enum_size:
        raise ValueError("Invalid script option: {}.".format(operation))

    return operation


def validate_bur_operation_arguments(console_input_args, bur_operations_enum,
                                     validation_error_list=None):
    """
    Validate script operation argument and its dependent parameters.

    If BKP_DOWNLOAD option is selected, validate the deployment label and backup tag arguments.

    In case of validation error, exits with error code: INVALID_INPUT.

    :param console_input_args: input arguments to be validated.
    :param bur_operations_enum: BUR operations enumerator.
    :param validation_error_list: validation error list.
    """
    try:
        operation = validate_script_option_argument(console_input_args.script_option,
                                                    bur_operations_enum.SIZE.value)

        if operation == int(bur_operations_enum.BKP_DOWNLOAD.value):
            if console_input_args.backup_destination is None or not \
                    console_input_args.backup_destination.strip():
                console_input_args.backup_destination = ""

            # enable this checking to force the user to provide a backup tag.
            # note that if this checking is enabled, ntwk_bkp won't be able to automatically
            # download the most recent backup from offsite.

            # is_backup_tag_empty = console_input_args.backup_tag is None or not \
            #     console_input_args.backup_tag.strip()
            #
            # if is_backup_tag_empty:
            #     raise ValueError("Inform the backup tag to do the download.")

    except ValueError as e:
        if validation_error_list is None:
            validation_error_list = []

        validation_error_list.append(e.message)


def validate_onsite_backup_locations(deployment_config_dict, config_file_name,
                                     validation_error_list=None):
    """
    Check if the on-site paths informed in the configuration file are valid for each deployment.

    In case of validation error, the message is appended to the validation error list.

    :param deployment_config_dict: information about each deployment in the configuration file.
    :param config_file_name: BUR configuration file name.
    :param validation_error_list: validation error list.
    """
    if validation_error_list is None:
        validation_error_list = []

    if not deployment_config_dict.keys():
        validation_error_list.append("No deployment defined in the configuration file '{}'. "
                                     "Nothing to do.".format(config_file_name))

    for deployment_key in deployment_config_dict.keys():
        deployment_config = deployment_config_dict[deployment_key]
        if not os.path.exists(deployment_config.backup_path):
            validation_error_list.append("Informed path for deployment {} does not exist: '{}'."
                                         .format(deployment_key, deployment_config.backup_path))


def validate_offsite_backup_server(offsite_config, config_file_name, logger,
                                   validation_error_list=None):
    """
    Check if the off-site server is up and validates the specified path on that server.

    1. Check if the provided parameters are not empty.
    2. Check if the provided IP is valid;
    3. Check if the provided IP is working;
    4. Verifies if the provided path exists, otherwise tries to create it.

    In case of validation error, the message is appended to the validation error list.

    :param offsite_config: offsite config object.
    :param config_file_name: BUR configuration file name.
    :param logger: logger object.
    :param validation_error_list: validation error list.

    :return True if successfully validates offsite object;
            False if something went wrong (check validation_error_list)
    """
    if validation_error_list is None:
        validation_error_list = []

    if not offsite_config:
        validation_error_list.append("Off-site parameters not defined in the configuration file "
                                     "'{}'. Nothing to do.".format(config_file_name))
        return False

    if not offsite_config.user.strip():
        validation_error_list.append("Off-site field 'user' is empty.")

    if not offsite_config.path.strip():
        validation_error_list.append("Off-site field 'path' is empty.")

    if not offsite_config.folder.strip():
        validation_error_list.append("Off-site field 'folder' is empty.")

    if not offsite_config.ip.strip():
        validation_error_list.append("Off-site field 'ip' is empty.")

    if not is_valid_ip(offsite_config.ip):
        validation_error_list.append("Informed off-site IP '{}' is not valid."
                                     .format(offsite_config.ip))

    if not check_remote_path_exists(offsite_config.host, offsite_config.path):
        validation_error_list.append("Informed root backup path does not exist on off-site: '{}'."
                                     .format(offsite_config.path))
        return False

    if not check_remote_path_exists(offsite_config.host, offsite_config.full_path):
        logger.warning("Remote backup path '{}' does not exist yet. Trying to create it."
                       .format(offsite_config.full_path))

        if not create_remote_dir(offsite_config.host, offsite_config.full_path):
            validation_error_list.append("Remote directory could not be created '{}'"
                                         .format(offsite_config.full_path))
        else:
            logger.info("New remote path '{}' created successfully."
                        .format(offsite_config.full_path))
    else:
        logger.info("Remote directory '{}' already exists".format(offsite_config.full_path))

    return True


def validate_retention_config(retention_value, validation_error_list):
    """
    Validate the retention value defined in config file.

    :param retention_value: how many backups should be kept.
    :param validation_error_list: validation error list.
    :return: True if the retention value is valid, False otherwise.
    """
    if validation_error_list is None:
        validation_error_list = []

    retention = int(retention_value)

    if retention < 0:
        validation_error_list.append("Invalid retention value: {}. "
                                     "Must be equal to or bigger than zero."
                                     .format(retention))
        return False

    return True


def validate_retention_argument(retention_value):
    """
    Validate the retention value.

    :param retention_value: how many backups should be kept at off-side.
    :return: a valid integer retention value.

    :raise: ValueError if a negative number is passed.
    """
    retention = int(retention_value)

    if retention < 0:
        raise ValueError("Invalid retention value: {}.".format(retention))

    return retention
