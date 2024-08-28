##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

"""Module to handle network backup encryption/decryption and related sub-procedures."""

import os
from subprocess import Popen

from gnupg import GPG
from network_backup_offsite.logger import CustomLogger
from network_backup_offsite.utils import get_home_dir, GPG_SUFFIX, PLATFORM_NAME, remove_path, \
    timeit

GPG_KEY_PATH = os.path.join(get_home_dir(), ".gnupg")

SCRIPT_FILE = os.path.basename(__file__).split('.')[0]


class GnupgManager:
    """Class to encapsulate the components related to backup encruption/decryption features."""

    def __init__(self, gpg_user_name, gpg_user_email, logger, gpg_key_path=GPG_KEY_PATH):
        """
        Initialize GPG Manager class.

        Configure additional parameters:

        gpg_cmd:        gpg command according to the platform.
        gpg_handler:    gpg python object.

        :param gpg_user_name: gpg configured user name.
        :param gpg_user_email: gpg configured email.
        :param logger:  logger object.
        :param gpg_key_path: gpg key path, usually is ~/.gnupg.
        """
        self.gpg_user_name = gpg_user_name
        self.gpg_user_email = gpg_user_email
        self.gpg_key_path = gpg_key_path
        self.gpg_file_extension = ".{}".format(GPG_SUFFIX)

        self.logger = CustomLogger(SCRIPT_FILE, logger.log_root_path, logger.log_file_name,
                                   logger.log_level)

        if 'linux' in PLATFORM_NAME:
            self.gpg_cmd = 'gpg'
            self.gpg_handler = GPG(homedir=self.gpg_key_path)
        elif 'sun' in PLATFORM_NAME:
            self.gpg_cmd = 'gpg2'
            self.gpg_handler = GPG(self.gpg_cmd, gnupghome=self.gpg_key_path)
        else:
            raise Exception("Platform not supported for GNUPG encryption tool.")

        self.validate_encryption_key()

    def validate_encryption_key(self):
        """
        Check the system for the encryption key.

        Creates a new key if there is no one for the informed user.

        If an error occurs, an Exception is raised with the details of the problem.

        :return: true if the key already exists or if a new one was created.
        """
        self.logger.info("Validating GPG encryption settings.")

        with open(os.devnull, "w") as devnull:
            ret_code = Popen([self.gpg_cmd, "--list-keys", self.gpg_user_email],
                             stdout=devnull, stderr=devnull).wait()
            if ret_code == 0:
                self.logger.info("Backup key already exists.")
                return True

        if self.gpg_handler is None:
            raise Exception("GPG program not installed properly in this system.")

        self.logger.info("Backup key does not exist yet. Creating a new one.")

        self.gpg_handler.gen_key(self.gpg_handler.gen_key_input(key_type='RSA',
                                                                key_length=1024,
                                                                name_real=self.gpg_user_name,
                                                                name_email=self.gpg_user_email))

        return True

    @timeit
    def encrypt_file(self, file_path, output_path, **kwargs):
        """
        Encrypt a file using the gpg strategy.

        The resulting file name will be like <file_path>.gpg.

        For example,
            given a file_path = '~/Documents/file.tgz',

        The resulting encrypted file will be like:
            '~/Documents/file.tgz.gpg'

        If an error occurs, an Exception is raised with the details of the problem.

        :param file_path:   file path to be encrypted.
        :param output_path: path where the encrypted file will be stored.

        :return encrypted file name.
        """
        if not file_path.strip() or not output_path.strip():
            raise Exception("An empty file path or output file path was provided.")

        if not os.path.exists(file_path):
            raise Exception("Informed file does not exist '{}'.".format(file_path))

        self.logger.info("Encrypting file '{}'".format(file_path))

        with open(os.devnull, "w") as devnull:
            output = "{}{}".format(os.path.join(output_path, os.path.basename(file_path)),
                                   self.gpg_file_extension)
            ret_code = Popen([self.gpg_cmd, "--output", output, "-r", self.gpg_user_email,
                              "--cipher-algo", "AES256", "--compress-algo", "none",
                              "--encrypt", file_path], stdout=devnull, stderr=devnull).wait()
            if ret_code != 0:
                raise Exception("Encryption of file {} could not be completed."
                                .format(file_path))
        return output

    @timeit
    def decrypt_file(self, encrypted_file_path, remove_encrypted=False, **kwargs):
        """
        Decrypt a file using the gpg strategy.

        If an error occurs, an Exception is raised with the details of the problem.

        :param encrypted_file_path: file to be decrypted in the format <file_name>.gpg.
        :param remove_encrypted:    flag to inform if the encrypted file should be deleted after
        decryption.

        :return decrypted file name.
        """
        if not encrypted_file_path.strip():
            raise Exception("An empty file path was provided.")

        if self.gpg_file_extension not in encrypted_file_path:
            raise Exception("Not a valid GPG encrypted file '{}'.".format(encrypted_file_path))

        if not os.path.exists(encrypted_file_path):
            raise Exception("Informed file does not exist '{}'.".format(encrypted_file_path))

        if os.path.isdir(encrypted_file_path):
            raise Exception("Informed path is a directory '{}'.".format(encrypted_file_path))

        self.logger.info("Decrypting file {}.".format(encrypted_file_path))

        dec_filename = \
            encrypted_file_path[0:len(encrypted_file_path) - len(self.gpg_file_extension)]

        with open(os.devnull, "w") as devnull:
            ret_code = Popen([self.gpg_cmd, "--output", dec_filename, "--decrypt",
                              encrypted_file_path], stdout=devnull, stderr=devnull).wait()
            if ret_code != 0:
                raise Exception("Decryption of file '{}' could not be completed."
                                .format(encrypted_file_path))

        if remove_encrypted:
            self.logger.info("Removing file '{}'.".format(encrypted_file_path))
            remove_path(encrypted_file_path)

        return dec_filename

    def __str__(self):
        """Represent GnupgManager object as string."""
        return "({}, {}, {})".format(self.gpg_user_name, self.gpg_user_email, self.gpg_key_path)

    def __repr__(self):
        """Represent GnupgManager object."""
        return self.__str__()
