##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For too many attributes comments
# For snake_case comments (invalid-name)
# For too many arguments comments
# pylint: disable=R0902,C0103,R0913,E0401

"""Module for processing config.cfg file."""

from ConfigParser import ConfigParser, MissingSectionHeaderError, NoOptionError, NoSectionError, \
    ParsingError
import os

from network_backup_offsite.exceptions import BackupSettingsErrorCodes, BackupSettingsException, \
    ExceptionCodes
from network_backup_offsite.gnupg_manager import GnupgManager
from network_backup_offsite.logger import CustomLogger
from network_backup_offsite.notification_handler import NotificationHandler
from network_backup_offsite.utils import get_home_dir, to_seconds

SCRIPT_FILE = os.path.basename(__file__).split('.')[0]

SYSTEM_CONFIG_FILE_ROOT_PATH = os.path.join(get_home_dir(), "network_backup_offsite", "config")
DEFAULT_CONFIG_FILE_ROOT_PATH = os.path.join(os.path.dirname(__file__), 'config')


class SupportInfo(object):
    """Class used to hold parsed information from config.cfg about support."""

    def __init__(self, email, server):
        """
        Initialize Support Info object.

        :param email: support email info.
        :param server: email server.
        """
        self.email = email
        self.server = server

    def __str__(self):
        """Represent Support Info object as string."""
        return "({}, {})".format(self.email, self.server)

    def __repr__(self):
        """Represent Support Info object."""
        return self.__str__()


class OffsiteConfig(object):
    """Class used to hold parsed information from config.cfg about offsite."""

    def __init__(self, ip, user, path, folder, temp_path, storage_account, container_name, offsite_retention, name="AZURE"):
        """
        Initialize Offsite Config object.

        :param ip: ip of the server.
        :param user: user allowed to access the server.
        :param path: path in which the backup folder will be placed.
        :param folder: backup folder's name.
        :param temp_path: temporary folder to store files during the backup process.
        :param offsite_retention: value for offsite retention policy, how many bkps to keep offsite.
        :param name: name of offsite location.
        """
        self.name = name
        self.ip = ip
        self.user = user
        self.path = path
        self.folder = folder
        self.full_path = os.path.join(path, folder)
        self.host = user + '@' + ip
        self.temp_path = temp_path
        self.offsite_retention = offsite_retention
        self.storage_account = storage_account
        self.container_name = container_name
        self.full_container_path = os.path.join(storage_account, container_name)

    def __str__(self):
        """Represent Offsite Config object as string."""
        return "({}, {}, {}, {}, offsite retention: {})"\
            .format(self.ip, self.user, self.full_path, self.temp_path, self.offsite_retention)

    def __repr__(self):
        """Represent Offsite Config object."""
        return self.__str__()


class EnmConfig(object):
    """Class used to hold parsed information from config.cfg about the deployment onsite."""

    def __init__(self, name, path, onsite_retention):
        """
        Initialize ENM Config object.

        :param name: deployment name from the configuration section.
        :param path: backup path.
        :param onsite_retention: how many backups to keep onsite.
        """
        self.name = name
        self.backup_path = path
        self.onsite_retention = onsite_retention

    def __str__(self):
        """Represent EnmConfig object as string."""
        return "({}, {}, onsite retention: {})"\
            .format(self.name, self.backup_path, self.onsite_retention)

    def __repr__(self):
        """Represent EnmConfig object."""
        return self.__str__()


class DelayConfig:
    """Class for holding delay configurations from config file."""

    def __init__(self, max_delay):
        """
        Initialize DelayConfig object.

        :param max_delay: max seconds of how long the upload process can take.
        """
        self.max_delay = max_delay

    def __str__(self):
        """Represent DelayConfig object as string."""
        return "({})".format(self.max_delay)

    def __repr__(self):
        """Represent DelayConfig object."""
        return self.__str__()


class ScriptSettings(object):
    """
    Class used to hold and information from the configuration file config.cfg.

    Configuration file will be checked first in $USER_HOME/network_backup_offsite/config/config.cfg
    and then at the directory "config" in the same level as the script.
    """

    def __init__(self, config_file_name, logger):
        """
        Initialize Script Settings object.

        :param config_file_name: name of the configuration file.
        :param logger: logger object.
        """
        self.config_file_name = config_file_name

        self.config_file_path = self._get_config_file_path()

        self.logger = CustomLogger(SCRIPT_FILE, logger.log_root_path, logger.log_file_name,
                                   logger.log_level)

        self.config = self._get_config_details()

    def _get_config_file_path(self):
        """
        Verify the path to config file.

        :return: config file pathname
        """
        config_root_path = SYSTEM_CONFIG_FILE_ROOT_PATH
        if not os.access(config_root_path, os.R_OK):
            config_root_path = DEFAULT_CONFIG_FILE_ROOT_PATH

        return os.path.join(config_root_path, self.config_file_name)

    def _get_config_details(self):
        """
        Read, validate the configuration file and create the main objects used by the system.

        Errors that occur during this process are appended to the validation error list.

        :return: a dictionary with the following objects: notification handler, gnupg manager,
         offsite configuration, deployment configuration dictionary and delay configuration,
         if success; an empty dictionary, otherwise.
        """
        if not os.access(self.config_file_path, os.R_OK):
            raise BackupSettingsException("Configuration file is not accessible '{}'"
                                          .format(self.config_file_path),
                                          BackupSettingsErrorCodes.ConfigurationFileReadError)

        try:
            config = ConfigParser()
            config.readfp(open(self.config_file_path))

        except (AttributeError, MissingSectionHeaderError, ParsingError) as parser_error:
            raise BackupSettingsException("Parsing configuration file error: {}"
                                          .format(parser_error.message),
                                          BackupSettingsErrorCodes.ConfigurationFileParsingError)

        except IOError as exception:
            raise BackupSettingsException("Configuration file error: {}".format(exception.message),
                                          BackupSettingsErrorCodes.ConfigurationFileReadError)

        self.logger.info("Reading configuration file '%s'.", self.config_file_path)
        return config

    def get_notification_handler(self):
        """
        Read the support contact information from the config file.

        1. EMAIL_TO: email address of the support team.
        2. EMAIL_URL: email server url.

        If an error occurs, an Exception is raised with the details of the problem..

        :return the notification handler with the informed data.
        """
        try:
            support_info = SupportInfo(str(self.config.get('SUPPORT_CONTACT', 'EMAIL_TO')),
                                       str(self.config.get('SUPPORT_CONTACT', 'EMAIL_URL')))
        except (NoSectionError, NoOptionError) as exception:
            raise BackupSettingsException("Error reading the configuration file '{}': {}"
                                          .format(self.config_file_name, exception.message),
                                          BackupSettingsErrorCodes.ConfigurationFileOptionError)

        self.logger.info("The following support information was defined: %s.", support_info)

        return NotificationHandler(support_info.email, support_info.server, self.logger)

    def get_gnupg_manager(self):
        """
        Read the GPG information from the config file.

        1. GPG_USER_NAME:  gpg configured user name.
        2. GPG_USER_EMAIL: gpg configured email.

        If one of these information is missing in the configuration file,
        an INVALID_INPUT error is raised.

        Configure the GnupgManager according to the provided settings and platform.
        If an error occurs, an Exception is raised with the details of the problem.

        :return an object with the gnupg information.
        """
        try:
            gpg_manager = GnupgManager(str(self.config.get('GNUPG', 'GPG_USER_NAME')),
                                       str(self.config.get('GNUPG', 'GPG_USER_EMAIL')),
                                       self.logger)
        except (NoSectionError, NoOptionError) as exception:
            raise BackupSettingsException("Error reading the configuration file '{}': {}"
                                          .format(self.config_file_name, exception.message),
                                          BackupSettingsErrorCodes.ConfigurationFileOptionError)

        self.logger.info("The following gnupg information was defined: %s.", gpg_manager)

        return gpg_manager

    def get_offsite_config(self):
        """
        Read the cloud connection details, as well as the backup path.

        1. IP: ip address.
        2. USER: server user.
        3. BKP_PATH: main path where the backup content will be placed.
        4. BKP_DIR: folder where the deployment's backup will be transferred.

        If an error occurs, an Exception is raised with the details of the problem.

        :return an object with the offsite information.
        """
        try:
            offsite_config = OffsiteConfig(self.config.get('OFFSITE_CONN', 'IP'),
                                           self.config.get('OFFSITE_CONN', 'USER'),
                                           self.config.get('OFFSITE_CONN', 'BKP_PATH'),
                                           self.config.get('OFFSITE_CONN', 'BKP_DIR'),
                                           self.config.get('OFFSITE_CONN', 'BKP_TEMP_FOLDER'),
                                           self.config.get('OFFSITE_CONN', 'STORAGE_ACCOUNT'),
                                           self.config.get('OFFSITE_CONN', 'CONTAINER_NAME'),
                                           int(self.config.get('OFFSITE_CONN',
                                                               'OFFSITE_RETENTION')))
        except (NoSectionError, NoOptionError, KeyError, ValueError) as exception:
            raise BackupSettingsException("Error reading the configuration file '{}': {}"
                                          .format(self.config_file_name, exception.message),
                                          BackupSettingsErrorCodes.ConfigurationFileOptionError)

        self.logger.info("The following off-site information was defined: %s.", offsite_config)

        return offsite_config

    def get_deployment_config_dict(self, deployment_label=None):
        """
        Read deployment details.

        DEPLOYMENT_PATH: path to the deploment's backups.
        If an error occurs, an Exception is raised with the details of the problem.

        :param deployment_label: deployment label if running the script just for one deployment.

        :return dictionary with the information of all deployments in the configuration file.
        """
        try:
            sections = self.config.sections()
            sections.remove('SUPPORT_CONTACT')
            sections.remove('GNUPG')
            sections.remove('OFFSITE_CONN')
            sections.remove('DELAY')

            self.logger.info("The following deployments were defined: %s.", sections)

            deployment_config_dict = {}

            if deployment_label and deployment_label.strip():
                self.logger.info("Configuration loaded only for: {}.".format(deployment_label))
                path = self.config.get(deployment_label, "DEPLOYMENT_PATH")
                onsite_retention = int(self.config.get(deployment_label, "ONSITE_RETENTION"))

                return {deployment_label: EnmConfig(deployment_label, path, onsite_retention)}

            for section in sections:
                path = self.config.get(section, "DEPLOYMENT_PATH")
                onsite_retention = int(self.config.get(section, "ONSITE_RETENTION"))

                deployment_config_dict[section] = EnmConfig(section, path, onsite_retention)

        except (NoSectionError, NoOptionError) as exception:
            raise BackupSettingsException("Error reading the configuration file '{}': {}"
                                          .format(self.config_file_name, exception.message),
                                          BackupSettingsErrorCodes.ConfigurationFileOptionError)

        return deployment_config_dict

    def get_delay_config(self):
        """
        Read delay details from config file.

        :return: a DelayConfig object.
        :raise BackupSettingsException: if the configuration file cannot be parsed.
        """
        try:
            max_delay = to_seconds(self.config.get("DELAY", "BKP_MAX_DELAY"))

            self.logger.log_info("Max running time for a backup upload is defined up to {} seconds."
                                 .format(max_delay))

            return DelayConfig(max_delay)

        except NoSectionError as error:
            raise BackupSettingsException(ExceptionCodes.MissingBackupDelaySection, error)

        except NoOptionError as error:
            raise BackupSettingsException(ExceptionCodes.ConfigurationFileOptionError, error)

