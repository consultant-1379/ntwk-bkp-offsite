##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

"""Module to handle helper functions."""

from enum import Enum
import gzip
import os
import shutil
import socket
from subprocess import PIPE, Popen
import sys
from tarfile import TarError, TarFile
from threading import Timer
import time

from network_backup_offsite.exceptions import ExceptionCodes, UtilsException


LOG_SUFFIX = "log"
TAR_SUFFIX = "tar"
GZ_SUFFIX = "gz"
GPG_SUFFIX = "gpg"
METADATA_FILE_SUFFIX = "_metadata"

SUCCESS_FLAG_FILE = "BACKUP_OK"

BUR_FILE_LIST_DESCRIPTOR_FILE_NAME = "bur_file_list_descriptor.dat"
BUR_VOLUME_LIST_DESCRIPTOR_FILE_NAME = "bur_volume_list_descriptor.dat"

LOG_ROOT_PATH_CLI = "--log_root_path"

TIMEOUT = 120
LOG_LEVEL = "LogLevel=ERROR"

BLOCK_SIZE_MB_STR = "MB"
BLOCK_SIZE_GB_STR = "GB"

BLOCK_SIZE_MB = 1000
BLOCK_SIZE_GB = 1024

DEFAULT_NUM_THREADS = 5
DEFAULT_NUM_PROCESSORS = 5
DEFAULT_NUM_TRANSFER_PROCS = 8

PLATFORM_NAME = str(sys.platform).lower()

DF_COMMAND_AVAILABLE_SPACE_INDEX = 3
DF_COMMAND_MOUNTED_ON_INDEX = 5

PROCESSED_BACKUP_ENDS_WITH = "." + TAR_SUFFIX + "." + GPG_SUFFIX

TAR_CMD = "tar"
if 'sun' in PLATFORM_NAME:
    TAR_CMD = "gtar"

META_DATA_KEYS = Enum('MetadataKeys', 'objects, md5')

VOLUME_OUTPUT_KEYS = Enum('VolumeOutputKeys', 'volume_path, processing_time, tar_time, output, '
                          'status, rsync_output, transfer_time')

DECORATOR_KEYS = Enum('DECORATOR_KEYS', 'get_elapsed_time, max_delay, on_timeout, on_timeout_args')


def get_home_dir():
    """
    Get home directory for the current user.

    :return: home directory.
    """
    return os.path.expanduser("~")


def create_path(path):
    """
    Create a path in the local storage.

    :param path: path to be created.

    :return: true if path already exists or was successfully created,
             false otherwise.
    """
    if os.path.exists(path):
        return True

    try:
        os.makedirs(path)
    except OSError:
        return False

    return True


def remove_path(path):
    """
    Delete a path from local storage.

    :param path:   file name to be removed.

    :return: true if path does not exist or was successfully deleted,
             false otherwise.
    """
    if not os.path.exists(path):
        return True

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError:
        return False

    return True


def popen_communicate(host, command, timeout=TIMEOUT):
    """
    Use Popen library to communicate to a remote server by using ssh protocol.

    :param host: remote host to connect.
    :param command: command to execute on remote server.
    :param timeout: timeout to wait for the process to finish.

    :return: pair stdout, stderr from communicate command,
             empty string pair, otherwise.
    """
    if host == "" or command == "":
        return "", ""

    ssh = Popen(['ssh', '-o', LOG_LEVEL, host, 'bash'],
                stdin=PIPE, stdout=PIPE, stderr=PIPE)

    timer = Timer(timeout, lambda process: process.kill(), [ssh])

    try:
        timer.start()
        stdout, stderr = ssh.communicate(command)
    finally:
        if not timer.is_alive():
            stderr = "Command '{}' timeout.".format(command)
        timer.cancel()

    return stdout, stderr


def check_remote_path_exists(host, path, timeout=TIMEOUT):
    """
    Check if a remote path exists.

    First check what kind of path is being looked for, whether it is a directory or a file,
    in order to run the proper command.

    :param host: remote host address, e.g. user@host_ip
    :param path: remote path to be verified.
    :param timeout: timeout to wait for the process to finish.

    :return: false, if the path does not exist,
             true, otherwise
    """
    if not host.strip() or not path.strip():
        return False

    ssh_check_dir_command = """
    if [ -d {} ] || [ -f {} ]; then echo "DIR_IS_AVAILABLE"; fi\n
    """.format(path, path)

    stdout, _ = popen_communicate(host, ssh_check_dir_command, timeout)

    if stdout.strip() != "DIR_IS_AVAILABLE":
        return False

    return True


def create_remote_dir(host, full_path, timeout=TIMEOUT):
    """
    Try to create a remote directory with ssh commands.

    :param host:      remote host address, e.g. user@host_ip
    :param full_path: full path to be created.
    :param timeout: timeout to wait for the process to finish.

    :return: true, if directory was successfully created
             false, otherwise.
    """
    ssh_create_dir_commands = """
    if [ -d {} ]; then\n
        echo "DIR_IS_AVAILABLE\n"
    else\n
        mkdir {}\n
        if [ -d {} ]; then\n
            echo "DIR_IS_AVAILABLE";\n
        fi\n
    fi\n
    """.format(full_path, full_path, full_path)

    stdout, stderr = popen_communicate(host, ssh_create_dir_commands, timeout)

    if stderr.strip():
        return False

    if stdout.strip() != "DIR_IS_AVAILABLE":
        return False

    return True


def remove_remote_dir(host, dir_list=None, timeout=TIMEOUT):
    """
    Remove the informed directory list from the remote server.

    An exception is raised if a problem happens during the process.

    :param host:     remote host address, e.g. user@host_ip
    :param dir_list: directory list.
    :param timeout: timeout to wait for the process to finish.

    :return: tuple (list of not removed directories, list of validated removed directories).
    """
    if not host.strip():
        raise Exception("Empty host was provided.")

    if dir_list is None:
        dir_list = []

    if isinstance(dir_list, str):
        if not dir_list.strip():
            raise Exception("Empty directory was provided.")
        dir_list = [dir_list]

    if not dir_list:
        raise Exception("Empty list was provided.")

    remove_dir_cmd = ""

    for folder_path in dir_list:
        folder_path = folder_path.strip()
        remove_dir_cmd += "rm -rf {}\n".format(folder_path)

    _, stderr = popen_communicate(host, remove_dir_cmd, timeout)

    if stderr.strip():
        raise Exception("Unable to perform the remove command on offsite due to: {}".format(stderr))

    return validate_removed_dir_list(host, dir_list)


def validate_removed_dir_list(host, remove_dir_list=None):
    """
    Check the list of removed dirs, to validate if they were successfully deleted from offsite.

    :param host: remote host to do the validation.
    :param remove_dir_list: list of directories supposed to be removed.

    :return: list of not removed directories, list of validated removed directories.
    """
    if remove_dir_list is None:
        remove_dir_list = []

    not_removed_list = []
    validated_removed_list = []
    for removed_path in remove_dir_list:
        if not check_remote_path_exists(host, removed_path):
            validated_removed_list.append(removed_path)
        else:
            not_removed_list.append(removed_path)

    return not_removed_list, validated_removed_list


def is_valid_ip(ip):
    """
    Validate if provided IP is valid.

    :param ip: IP in string format to be validated.

    :return: true if ip is valid,
             false, otherwise.
    """
    try:
        socket.inet_aton(ip)
    except socket.error:
        return False

    return True


def is_host_accessible(ip):
    """
    Validate host is accessible.

    :param ip: remote host IP.

    :return: true, if host is accessible,
             false, otherwise.
    """
    with open(os.devnull, "w") as devnull:
        ret_code = Popen(["ping", "-c", "1", ip], stdout=devnull, stderr=devnull).wait()
        return ret_code == 0


def truncate_microseconds_from_timestamp(time_stamp_value):
    """
    Remove the microseconds part from the timestamp value.

    :param time_stamp_value: time represented in seconds and microseconds.
    :return: time represented in seconds only.
    :raise UtilsException: if the time_stamp_value is negative or other invalid value.
    """
    if time_stamp_value < 0:
        raise UtilsException(ExceptionCodes.InvalidValue, time_stamp_value)

    try:
        time_stamp_value = float(int(time_stamp_value))
    except (ValueError, TypeError):
        raise UtilsException(ExceptionCodes.InvalidValue, time_stamp_value)

    return time_stamp_value


def get_formatted_timestamp():
    """
    Get formatted local date and time, based on seconds since the epoch(1st Jan 1970).

    :return: formatted local date and time, in the format YY-MM-DD HH:MM:SS.
    """
    return format_time(truncate_microseconds_from_timestamp(time.time()), '%Y-%m-%d %H:%M:%S')


def format_time(elapsed_time, time_format="%H:%M:%S"):
    """
    Display a float time according to the format string.

    :param elapsed_time: float time representation.
    :param time_format: format string.

    :return: formatted time.
    """
    return time.strftime(time_format, time.gmtime(elapsed_time))


def get_elem_dict(dic, key):
    """
    Find and get element from dictionary.

    :param dic: dictionary.
    :param key: key to the value.
    :return: value referred by the key, if exists,
             None otherwise.
    """
    if not isinstance(dic, dict):
        return None

    if key in dic.keys():
        return dic[key]

    return None


def get_values_from_dict(dic, key=""):
    """
    Get values from dictionary based on the passed key.

    If no key is specified, get all key-value pairs.

    Raise an exception in case of error.

    :param dic: dictionary with key value pairs.
    :param key: dictionary's key.

    :return: list with the result of the search.
    """
    if key is None or not key.strip():
        return dic.values()

    element = get_elem_dict(dic, key)
    if element is None:
        raise Exception("Key {} not found in the dictionary.".format(key))

    return [element]


def timer_delay(method):
    """
    Execute a function after the specified timeout. Decorator function.

    :param method: decorated method.
    """
    def wrapper(*args, **kw):
        """Execute a function after timeout."""
        max_delay = None
        if DECORATOR_KEYS.max_delay.name in kw:
            max_delay = kw[DECORATOR_KEYS.max_delay.name]

        on_timeout_function = None
        if DECORATOR_KEYS.on_timeout.name in kw and callable(kw[DECORATOR_KEYS.on_timeout.name]):
            on_timeout_function = kw[DECORATOR_KEYS.on_timeout.name]

        on_timeout_function_args = []
        if DECORATOR_KEYS.on_timeout_args.name in kw and \
                isinstance(kw[DECORATOR_KEYS.on_timeout_args.name], list):
            on_timeout_function_args = kw[DECORATOR_KEYS.on_timeout_args.name]

        if on_timeout_function is None or max_delay is None:
            return method(*args, **kw)

        try:
            timer = Timer(float(max_delay), on_timeout_function, on_timeout_function_args)
            timer.start()

            return method(*args, **kw)

        finally:
            if timer.is_alive():
                timer.cancel()

    wrapper.__wrapped__ = method

    return wrapper


def timeit(method):
    """
    Calculate the elapsed time to execute a function. Decorator function.

    :param: method: annotated method.
    """
    def timed(*args, **kw):
        """Calculate the elapsed time to execute a function. Decorator function."""
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        if 'get_elapsed_time' in kw:
            if isinstance(kw['get_elapsed_time'], list):
                kw['get_elapsed_time'].append(te - ts)

        return result

    return timed


@timeit
def compress_file(source_path, output_path=None, mode="w:gz", **kwargs):
    """
    Compress or archive a path using tarfile module.

    This function expects a mode to be either "w:gz", referring to compressing with gzip, or "w",
    which uses no compression.

    Output file is placed in the same directory as the original file by default,
    if no output_path is specified.

    If an error occurs, an Exception is raised with the details of the problem.

    :param source_path: file/folder path to be compressed.
    :param output_path: destination folder of the compressed file.
    :param mode:        compression mode to write file (w:gz) or tar mode (w).

    :return compressed file path.
    """
    if not os.path.exists(source_path):
        raise Exception("File '{}' does not exist.".format(source_path))

    if mode not in ["w", "w:", "w:gz"]:
        raise Exception("Provided invalid mode '{}'.".format(mode))

    if output_path is None or not output_path.strip():
        output_path = os.path.dirname(source_path)

    if not os.path.exists(output_path):
        raise Exception("Output path '{}' does not exist.".format(output_path))

    try:
        if GZ_SUFFIX in mode:
            compressed_file_path = gzip_file(source_path, output_path)
        else:
            compressed_file_path = tar_file(source_path, output_path)

    except Exception as comp_exp:
        raise Exception("Error while compressing file '{}' to destination '{}' due to {}."
                        .format(source_path, output_path, comp_exp.message))

    return compressed_file_path


@timeit
def decompress_file(source_path, output_path, remove_compressed=False, **kwargs):
    """
    Decompress a file using the tar strategy.

    Output file is placed in the same directory as the original file by default,
    if no output_path is specified.

    If an error occurs, an Exception is raised with the details of the problem.

    :param source_path:       file to be decompressed.
    :param output_path:       file path of the output file.
    :param remove_compressed: flag to inform if the compressed file should be deleted at the end.

    :return decompressed file path.
    """
    if not os.path.exists(source_path):
        raise Exception("File does not exist '{}'".format(source_path))

    if output_path is None or not output_path.strip():
        output_path = os.path.dirname(source_path)

    if not os.path.exists(output_path):
        raise Exception("Output path '{}' does not exist.".format(output_path))

    try:
        if is_tar_file(source_path):
            decompressed_file_path = untar_file(source_path, output_path)
        elif is_gzip_file(source_path):
            decompressed_file_path = gunzip_file(source_path, output_path)
        else:
            raise Exception("File format not supported for decompressing. "
                            "Supported files are .tar and .gz")

        if remove_compressed:
            remove_path(source_path)

    except Exception as dec_exp:
        raise Exception("Error while decompressing file '{}' due to {}.".format(source_path,
                                                                                dec_exp.message))
    return decompressed_file_path


def gzip_file(file_path, file_destination):
    """
    Compress file using gzip strategy.

    :param file_path: file to be compressed.
    :param file_destination: destination folder.

    :return: full compressed file path.
    """
    try:
        compressed_file_name = "{}.{}".format(os.path.basename(file_path), GZ_SUFFIX)

        compressed_file_path = os.path.join(file_destination, compressed_file_name)

        compress_command = "gzip -r -c {} > {}".format(file_path, compressed_file_path)

        ret = Popen(compress_command, shell=True).wait()

        if int(ret) != 0:
            raise Exception("Gzip command returned error code: {}.".format(ret))

    except Exception as gzip_exp:
        raise Exception("gzip_file failed due to: {}.".format(gzip_exp.message))

    return compressed_file_path


def tar_file(file_path, file_destination):
    """
    Archive file using tar strategy.

    It raises an exception if an error occurs.

    :param file_path: file to be archived.
    :param file_destination: destination folder.

    :return: full archived file path.
    """
    try:
        archived_file_name = "{}.{}".format(os.path.basename(file_path), TAR_SUFFIX)

        tar_file_path = os.path.join(file_destination, archived_file_name)

        compress_command = "{} -cf {} -C {} {}".format(TAR_CMD, tar_file_path, os.path.dirname(
            file_path), os.path.basename(file_path))

        ret = Popen(compress_command, shell=True).wait()

        if int(ret) != 0:
            raise Exception("Tar command returned error code: {}.".format(ret))

    except Exception as tar_exp:
        raise Exception("tar_file failed due to: {}.".format(tar_exp.message))

    return tar_file_path


def gunzip_file(file_path, file_destination):
    """
    Decompress file using gzip strategy.

    It raises an exception if an error occurs.

    :param file_path: file to be decompressed.
    :param file_destination: destination folder.

    :return decompressed file path.
    """
    try:
        if GZ_SUFFIX not in file_path:
            raise Exception("Invalid file path '{}'.".format(file_path))

        decompressed_file_name = os.path.basename(file_path).replace(".{}".format(
            GZ_SUFFIX), "")

        decompress_command = "gunzip -c {} > {}".format(file_path, os.path.join(
            file_destination, decompressed_file_name))

        ret = Popen(decompress_command, shell=True).wait()

        if int(ret) != 0:
            raise Exception("Gunzip command returned error code: {}.".format(ret))

    except Exception as gunzip_exp:
        raise Exception("gunzip_file failed due to: {}.".format(gunzip_exp.message))

    return os.path.join(file_destination, decompressed_file_name)


def untar_file(file_path, file_destination):
    """
    Decompress file using tar strategy.

    It raises an exception if an error occurs.

    :param file_path: file to be decompressed.
    :param file_destination: destination folder.

    :return decompressed file path.
    """
    try:
        if TAR_SUFFIX not in file_path:
            raise Exception("Invalid file path '{}'.".format(file_path))

        decompress_command = "{} -C {} -xf {}".format(TAR_CMD, file_destination, file_path)

        ret = Popen(decompress_command, shell=True).wait()

        if int(ret) != 0:
            raise Exception("Tar command returned error code: {}.".format(ret))

    except Exception as untar_exp:
        raise Exception("untar_file failed due to: {}.".format(untar_exp.message))

    decompressed_file_name = os.path.basename(file_path).replace(".{}".format(
        TAR_SUFFIX), "")

    return os.path.join(file_destination, decompressed_file_name)


def is_gzip_file(file_path):
    """
    Check whether the informed file path is in gzip format.

    :param file_path: file path.

    :return: whether the path refers to a gzip file or not.
    """
    if not file_path.strip():
        raise Exception("File path is empty.")

    with gzip.open(file_path) as compressed_file:
        try:
            compressed_file.read()
        except IOError:
            return False

    return True


def is_tar_file(file_path):
    """
    Check whether the informed file path is in tar format.

    :param file_path: file path.

    :return: whether the path refers to a tar file or not.
    """
    if not file_path.strip():
        raise Exception("File path is empty.")

    with open(file_path, "r") as compressed_file:
        try:
            TarFile(fileobj=compressed_file)
        except TarError:
            return False

    return True


def get_existing_root_path(destination_path):
    """
    Get the physical path, to perform disk space check on it.

    :param destination_path: the provided path where BUR will store backup data.

    :return: tuple: true, destination path after shrinking, informative message,
             if the destination path or path head exists.
             or
             tuple: false, if neither the destination path nor the path head exist.
    """
    starts_with_dot = str(destination_path)[0] == '.'
    absolute_path = os.path.isabs(destination_path)
    if not starts_with_dot and not absolute_path:
        log_message = "The destination path '{}' is invalid. It should start with '.' or '/'." \
                      ".".format(destination_path)

        return False, destination_path, log_message

    original_bkp_destination = destination_path
    while not os.path.exists(destination_path):
        if destination_path.strip():
            destination_path, _ = os.path.split(destination_path)
        else:
            log_message = "No part of the destination path: {} exists.".format(
                original_bkp_destination)

            return False, destination_path, log_message

    log_message = "The destination path to check after shrinking: {}.".format(destination_path)

    return True, destination_path, log_message


def get_filtered_cli_arguments():
    """
    Filter the unnecessary CLI arguments.

    :return a filtered list of CLI arguments, or an empty list if there was no CLI arguments passed.
    """
    filtered_cli_args = []

    if sys.argv:
        filtered_cli_args = list(sys.argv)

        for cli_argument in filtered_cli_args:

            if cli_argument.endswith(".py") or "/bin/ntwk_bkp" in cli_argument:
                filtered_cli_args.remove(cli_argument)

    return filtered_cli_args


def to_seconds(duration):
    """
    Convert time string to second, where string is of form 3h, 5m, 20s etc.

    :param duration: str with numeric value suffixed with h, s, or m.
    :return: seconds represented by the duration as int type.
    :raise UtilsException: if the string cannot be parsed.
    """
    try:
        units = {"s": 1, "m": 60, "h": 3600}
        return int(float(duration[:-1]) * units[duration[-1]])

    except KeyError:
        raise UtilsException(ExceptionCodes.InvalidTimeUnit, duration)
    except (ValueError, NameError):
        raise UtilsException(ExceptionCodes.InvalidTimeFormat, duration)
