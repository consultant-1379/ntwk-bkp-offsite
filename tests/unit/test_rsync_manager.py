##############################################################################
# COPYRIGHT Ericsson 2018
#
# The copyright to the computer program(s) herein is the property of
# Ericsson Inc. The programs may be used and/or copied only with written
# permission from Ericsson Inc. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
##############################################################################

# For the snake_case comments
# pylint: disable=C0103,E0401

"""This is unit test module for the backup.rsync_manager script."""
import unittest

from network_backup_offsite.rsync_manager import RsyncManager, RsyncOutput

import mock

MOCK_PACKAGE = 'network_backup_offsite.rsync_manager'

MOCK_NUMBER_FILES = MOCK_PACKAGE + '.RsyncManager.get_number_of_files_to_send'
MOCK_PARSE_OUTPUT = MOCK_PACKAGE + '.RsyncManager.parse_output'
MOCK_SEND = MOCK_PACKAGE + '.RsyncManager.send'
MOCK_RECEIVE = MOCK_PACKAGE + '.RsyncManager.receive'

MOCK_PATH = MOCK_PACKAGE + '.os.path'
MOCK_LIST_DIR = MOCK_PACKAGE + '.os.listdir'
MOCK_SUBPROCESS_CHECK_OUTPUT = MOCK_PACKAGE + '.subprocess.check_output'
MOCK_CHECK_REMOTE_PATH_EXISTS = MOCK_PACKAGE + '.check_remote_path_exists'

FAKE_TRIES = 1
FAKE_PATH = 'fake/path'
FAKE_HOST = 'fake_host@fake_ip'
FAKE_SOURCE = 'fake_source_path'
FAKE_TARGET = 'fake_target_path'
FAKE_FULL_HOST_SOURCE_PATH = "{}:{}".format(FAKE_HOST, FAKE_SOURCE)

RSYNC_OUTPUT = "Number of files: 2 (reg: 1, dir: 1)\n" \
               "Number of created files: 1\n" \
               "Number of deleted files: 2\n" \
               "Number of regular files transferred: 1\n" \
               "Total file size: 685 bytes\n" \
               "Total transferred file size: 787 bytes\n" \
               "Literal data: 680 bytes\n" \
               "Matched data: 787 bytes\n" \
               "File list size: 0\n" \
               "File list generation time: 0.001 seconds\n" \
               "File list transfer time: 0.000 seconds\n" \
               "Total bytes sent: 95\n" \
               "Total bytes received: 17\n\n" \
               "sent 95 bytes  received 17 bytes  74.67 bytes/sec\n" \
               "total size is 0  speedup is 0.00"

HALF_RSYNC_OUTPUT = "Number of files: 2 (reg: 1, dir: 1)\n" \
                    "Number of regular files transferred: 1\n" \
                    "Total file size: 685 bytes\n" \
                    "Total transferred file size: 787 bytes\n" \
                    "Literal data: 680 bytes\n" \
                    "Matched data: 787 bytes\n" \
                    "File list size: 0\n" \
                    "Total bytes sent: 95\n" \
                    "Total bytes received: 17\n\n" \
                    "sent 95 bytes  received 17 bytes  74.67 bytes/sec\n"


class RsyncManagerGetNumberOfFilesToSendTestCase(unittest.TestCase):
    """This is a scenario when the number of files are returned successfully."""

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)

    @mock.patch(MOCK_LIST_DIR)
    @mock.patch(MOCK_PATH + '.isdir')
    @mock.patch(MOCK_PATH + '.exists')
    def test_get_number_of_files_to_send_source_path_is_folder(self, mock_path_exists,
                                                               mock_path_isdir, mock_list_dir):
        """
        Test when the source path is a folder with 3 files.
        :param mock_path_exists: mocking the os.path.exists method.
        :param mock_path_isdir: mocking the os.path.isdir method.
        :param mock_list_dir: mocking the os.listdir method.
        """
        mock_path_exists.return_value = True
        mock_path_isdir.side_effect = [True, False, False, False]
        mock_list_dir.return_value = ['file0', 'file1', 'file2']

        n_files = self.rsync.get_number_of_files_to_send()

        self.assertEquals(n_files, 3, "Should have returned 3 files.")

    @mock.patch(MOCK_PATH + '.isdir')
    @mock.patch(MOCK_PATH + '.exists')
    def test_get_number_of_files_to_send_source_path_is_file(self, mock_path_exists,
                                                             mock_path_isdir):
        """
        Asserts if there are files to be transferred from the source path.
        :param mock_path_exists: mocking the os.path.exists method.
        """
        mock_path_exists.return_value = True
        mock_path_isdir.return_value = False

        result = self.rsync.get_number_of_files_to_send()
        self.assertEqual(result, 1)


class RsyncManagerGetNumberOfFilesToSendInvalidDirExceptionTestCase(unittest.TestCase):
    """
    This is a scenario when the source path is an invalid one (doesn't exist or it's typed
    incorrect) and an exception is raised.
    """

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)
        self.exception_message = "Specified path 'fake_source_path' does not exist."

    def test_get_number_of_files_to_send_invalid_dir(self):
        """Asserts if an Exception with the expected message is raised."""
        with self.assertRaises(Exception) as cex:
            self.rsync.get_number_of_files_to_send()

        self.assertEqual(cex.exception.message, self.exception_message)


class RsyncManagerGetNumberOfFilesToSendNoFilesExceptionTestCase(unittest.TestCase):
    """
    This is a scenario when there is no file within the source path and an exception is raised,
    informing that there is no file to be transferred.
    """

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)
        self.exception_message = 'There is no file in \'fake_source_path\' to be copied to the ' \
                                 'remote location.'

    @mock.patch(MOCK_PATH)
    @mock.patch(MOCK_LIST_DIR)
    def test_get_number_of_files_to_send_no_files(self, mock_listdir, mock_path):
        """
        Asserts if an Exception with the expected message is raised when there is no file within
        the folder.
        :param mock_listdir: mocking the os.listdir method.
        :param mock_path: mocking the os.path to make the fake path valid.
        """
        mock_path.exists.return_value = True
        mock_path.isdir.return_value = True

        mock_listdir.return_value = []

        with self.assertRaises(Exception) as cex:
            self.rsync.get_number_of_files_to_send()

        self.assertEqual(cex.exception.message, self.exception_message)


class RsyncManagerParseNumberOfFileKeyValueTestCase(unittest.TestCase):
    """
    These are scenarios when a line from the output result is read and parsed correctly,
    returning a tuple with the key and its value.
    """

    def setUp(self):
        """Set up the test constants."""
        self.total_files_tuple = 'total_files', '2'
        self.created_tuple = 'created', '1'
        self.deleted_tuple = 'deleted', '2'
        self.transferred_tuple = 'transferred', '1'

    def test_parse_number_of_file_key_value_total_files(self):
        """Asserts if the 'total files line' output is read and parsed."""
        line_output = RSYNC_OUTPUT.lower().split('\n')[0]
        result = RsyncManager.parse_number_of_file_key_value(line_output)
        self.assertEqual(result, self.total_files_tuple)

    def test_parse_number_of_file_key_value_created(self):
        """Asserts if the 'created line' output is read and parsed."""
        line_output = RSYNC_OUTPUT.lower().split('\n')[1]
        result = RsyncManager.parse_number_of_file_key_value(line_output)
        self.assertEqual(result, self.created_tuple)

    def test_parse_number_of_file_key_value_deleted(self):
        """Asserts if the 'deleted line' output is read and parsed."""
        line_output = RSYNC_OUTPUT.lower().split('\n')[2]
        result = RsyncManager.parse_number_of_file_key_value(line_output)
        self.assertEqual(result, self.deleted_tuple)

    def test_parse_number_of_file_key_value_transferred(self):
        """Asserts if the 'transferred line' output is read and parsed."""
        line_output = RSYNC_OUTPUT.lower().split('\n')[3]
        result = RsyncManager.parse_number_of_file_key_value(line_output)
        self.assertEqual(result, self.transferred_tuple)


class RsyncManagerParseNumberOfFileKeyValueExceptionTestCase(unittest.TestCase):
    """
    These are scenarios when an invalid line (doesn't have the 'number of' or a valid value) from
    output is not parsed and exceptions are raised.
    """

    def test_parse_number_of_file_key_value_no_number(self):
        """
        Asserts if an Exception with the correct message is raised when the line doesn't have
        the 'number of' string on it.
        """
        line_output = RSYNC_OUTPUT.lower().split('\n')[4]
        exception_message = "Line '" + line_output + "' does not contain a number of measurement."

        with self.assertRaises(Exception) as cex:
            RsyncManager.parse_number_of_file_key_value(line_output)

        self.assertEqual(cex.exception.message, exception_message)

    def test_parse_number_of_file_key_value_no_value(self):
        """
        Asserts if the correct exception with the correct message is raised when the line does
        have the 'number of' string on it, but doesn't a valid value following it.
        """
        line_output = "Number of regular files transferred"
        exception_message = "Could not parse rsync output line: " + line_output.lower() + "."

        with self.assertRaises(Exception) as cex:
            RsyncManager.parse_number_of_file_key_value(line_output.lower())

        self.assertEqual(cex.exception.message, exception_message)


class RsyncManagerParseOutputValidateDictionaryTestCase(unittest.TestCase):
    """
    This is a scenario when a rsync output is valid and correctly parsed to a rsync output
    dictionary.
    """

    def test_parse_output(self):
        """Asserts if the rsync_output passed is correctly parsed."""
        summary_dic = {'total_files': '2',
                       'created': '1',
                       'deleted': '2',
                       'transferred': '1',
                       'rate': '74.67',
                       'speedup': '0.00'}
        rsync_output = RsyncOutput(summary_dic)

        result = RsyncManager.parse_output(RSYNC_OUTPUT)
        self.assertEqual(str(result), str(rsync_output))


class RsyncManagerParseOutputInvalidOutputExceptionTestCase(unittest.TestCase):
    """
    This is scenario when an output has information, but doesn't have the tags used to create
    the RsyncOutput object.
    """

    def setUp(self):
        """Set up the test constants."""
        self.exception_message = "Parsing did not find valid tags in the output."

    def test_parse_output_empty_input(self):
        """
        Asserts if an Exception with the correct message is raised when an invalid output is
        informed.
        """
        with self.assertRaises(Exception) as cex:
            RsyncManager.parse_output("This is an invalid output with text but no tags!")

        self.assertEqual(cex.exception.message, self.exception_message)

    def test_parse_output_half_dictionary(self):
        """
        Asserts if an Exception with the correct message is raised when an incomplete output is
        informed.
        """
        with self.assertRaises(Exception) as cex:
            RsyncManager.parse_output(HALF_RSYNC_OUTPUT)

        self.assertEqual(cex.exception.message, self.exception_message)


class RsyncManagerParseOutputEmptyExceptionTestCase(unittest.TestCase):
    """
    These are scenarios when an invalid line (empty or None) from output is not read
    and exceptions are raised.
    """

    def setUp(self):
        """Set up the test constants."""
        self.exception_message = "Empty output."

    def test_parse_output_empty_input(self):
        """
        Asserts if an Exception with the correct message is raised when an empty output is
        informed as an argument.
        """
        with self.assertRaises(Exception) as cex:
            RsyncManager.parse_output(" ")

        self.assertEqual(cex.exception.message, self.exception_message)

    def test_parse_output_none_input(self):
        """
        Asserts if an Exception with the correct message is raised when a None object is
        informed as an argument.
        """
        with self.assertRaises(Exception) as cex:
            RsyncManager.parse_output(None)

        self.assertEqual(cex.exception.message, self.exception_message)


class RsyncManagerReceiveTestCase(unittest.TestCase):
    """This is a scenario when a rsync process receives files successfully from remote to local."""

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_FULL_HOST_SOURCE_PATH, FAKE_TARGET, FAKE_TRIES)

        self.summary_dic = {'total_files': '2',
                            'created': '1',
                            'deleted': '2',
                            'transferred': '1',
                            'rate': '74.67',
                            'speedup': '0.00'}
        self.rsync_output = RsyncOutput(self.summary_dic)

    @mock.patch(MOCK_CHECK_REMOTE_PATH_EXISTS)
    @mock.patch(MOCK_SUBPROCESS_CHECK_OUTPUT)
    def test_receive(self, mock_check_output, mock_check_remote_path_exists):
        """
        Asserts if the receive process was successful and returned the rsync output correctly.

        :param mock_check_output: mocking a valid result from subprocess.check_output.
        :param mock_check_remote_path_exists: mocking a valid result from
        utils.mock_check_remote_path_exists.
        """
        mock_check_remote_path_exists.return_value = True
        mock_check_output.return_value = RSYNC_OUTPUT

        result = self.rsync.receive()
        self.assertEqual(str(result), str(self.rsync_output))


class RsyncManagerReceiveCalledProcessErrorTestCase(unittest.TestCase):
    """
    This is a scenario when CalledProcessError is raised when checking the rsync output by the
    subprocess.check_output method.
    """

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_FULL_HOST_SOURCE_PATH, FAKE_TARGET, FAKE_TRIES)
        self.exception_message = "Error code"

    @mock.patch(MOCK_CHECK_REMOTE_PATH_EXISTS)
    def test_receive(self, mock_check_remote_path_exists):
        """
        Asserts if the exception with the correct message is raised when the
        CalledProcessError exception is caught.

        :param mock_check_remote_path_exists: mocking a valid result from
        utils.mock_check_remote_path_exists.
        """
        mock_check_remote_path_exists.return_value = True

        with self.assertRaises(Exception) as cex:
            self.rsync.receive()

        self.assertRegexpMatches(cex.exception.message, self.exception_message)


class RsyncManagerReceiveExceptionTestCase(unittest.TestCase):
    """
    This is a scenario when any other kind of exception happens and it's caught and raised as an
    Exception type with a custom message.
    """

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)
        self.command_exception_message = "Error while receiving file"

    def test_receive_invalid_source_path(self):
        """Test when the source path is invalid."""
        with self.assertRaises(Exception) as cex:
            self.rsync.receive()

        self.assertRegexpMatches(cex.exception.message, "Invalid source path '{}'.".format(
            FAKE_SOURCE))

    @mock.patch(MOCK_CHECK_REMOTE_PATH_EXISTS)
    def test_receive_remote_path_does_not_exist(self, mock_check_remote_path_exists):
        """
        Test when the remote path does not exist.

        :param mock_check_remote_path_exists: mocking a valid output for the
        utils.check_remote_path_exists method.
        """
        self.rsync.source_path = "fake:remote_path"
        mock_check_remote_path_exists.return_value = False

        with self.assertRaises(Exception) as cex:
            self.rsync.receive()

        self.assertRegexpMatches(cex.exception.message, "Remote file 'remote_path' does not exist.")

    @mock.patch(MOCK_SUBPROCESS_CHECK_OUTPUT)
    def test_receive(self, mock_check_output):
        """
        Asserts if the Exception raised has the custom message.

        :param mock_check_output: mocking a valid output for the subprocess.check_output method.
        """
        mock_check_output.side_effect = Exception

        with self.assertRaises(Exception) as cex:
            self.rsync.receive()

        self.assertRegexpMatches(cex.exception.message, self.command_exception_message)


class RsyncManagerSendTestCase(unittest.TestCase):
    """This is scenario when files are successfully send from local to remote."""

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)

        self.summary_dic = {'total_files': '2',
                            'created': '1',
                            'deleted': '2',
                            'transferred': '1',
                            'rate': '74.67',
                            'speedup': '0.00'}
        self.rsync_output = RsyncOutput(self.summary_dic)

    @mock.patch(MOCK_SUBPROCESS_CHECK_OUTPUT)
    @mock.patch(MOCK_NUMBER_FILES)
    def test_send(self, mock_number_files, mock_check_output):
        """
        Asserts if the rsync_output is returned correctly.

        :param mock_number_files: mocking the number of files that should be transferred.
        :param mock_check_output: mocking a valid subprocess.check_output return.
        """
        mock_check_output.return_value = RSYNC_OUTPUT
        mock_number_files.return_value = 1

        result = self.rsync.send()
        self.assertEqual(str(result), str(self.rsync_output))


class RsyncManagerSendNotRsyncOutputExceptionTestCase(unittest.TestCase):
    """
    This is a scenario when the rsync_output isn't a valid one or the parse_output doesn't parse
    the rsync_output correctly, so it doesn't have an instance of RsyncOutput
    and raises an Exception.
    """

    def setUp(self):
        """Set up the test constants."""
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)
        self.exception_message = "Error while sending file '{}'. Can't parse the output from " \
                                 "rsync command.".format(FAKE_SOURCE)

    @mock.patch(MOCK_PARSE_OUTPUT)
    @mock.patch(MOCK_NUMBER_FILES)
    @mock.patch(MOCK_SUBPROCESS_CHECK_OUTPUT)
    def test_send(self, mock_check_output, mock_number_files, mock_parse_output):
        """
        Asserts if the Exception is raised with the correct message.

        :param mock_check_output: mocking an empty subprocess.check_output return value.
        :param mock_number_files: mocking the number of files that should be transferred.
        :param mock_parse_output: mocking a None parse_output return value.
        """
        mock_check_output.return_value = ""
        mock_parse_output.return_value = None
        mock_number_files.return_value = '1'

        with self.assertRaises(Exception) as cex:
            self.rsync.send()

        self.assertEqual(cex.exception.message, self.exception_message)


class RsyncManagerSendRetryExceptionTestCase(unittest.TestCase):
    """
    This is a scenario when the maximum number of tries has been reached and not all the files
    have been transferred, so an Exception is raised.
    """

    def setUp(self):
        """Set up the test constants."""
        self.number_files_to_transfer = 7
        self.rsync = RsyncManager(FAKE_SOURCE, FAKE_TARGET, FAKE_TRIES)
        self.exception_message = "Error while sending file '{}'. " \
                                 "Can't transfer file(s) to remote server:\n" \
                                 "Number of tries: {}\n" \
                                 "Number of files to be transferred: {}\n" \
                                 "Number of transferred files: {}\n" \
            .format(FAKE_SOURCE, FAKE_TRIES, self.number_files_to_transfer, 1)

    @mock.patch(MOCK_NUMBER_FILES)
    @mock.patch(MOCK_SUBPROCESS_CHECK_OUTPUT)
    def test_send(self, mock_check_output, mock_number_files):
        """
        Asserts if Exception with the correct message is raised when the maximum tries are reached.
        :param mock_check_output: mocking a valid subprocess.check_output return value.
        :param mock_number_files: mocking the number of files that should be transferred.
        """
        mock_check_output.return_value = RSYNC_OUTPUT
        mock_number_files.return_value = self.number_files_to_transfer

        with self.assertRaises(Exception) as cex:
            self.rsync.send()

        self.assertEqual(cex.exception.message, self.exception_message)


class RsyncManagerTransferFileTestCases(unittest.TestCase):
    """This is a scenario to test the behavior of the static transfer file method."""

    def setUp(self):
        """Set up the test constants."""
        self.summary_dic = {'total_files': '2',
                            'created': '1',
                            'deleted': '2',
                            'transferred': '1',
                            'rate': '74.67',
                            'speedup': '0.00'}

        self.rsync_output = RsyncOutput(self.summary_dic)

    def test_transfer_file_empty_source_and_target(self):
        """Test transfer with empty parameters."""
        with self.assertRaises(Exception) as cex:
            RsyncManager.transfer_file("", "")

        empty_input_exception_message = "Empty input was provided."

        self.assertEqual(cex.exception.message, empty_input_exception_message)

    def test_transfer_file_receive_mode_invalid_source(self):
        """Test transfer in receive mode with invalid source."""
        with self.assertRaises(Exception) as cex:
            RsyncManager.transfer_file(FAKE_FULL_HOST_SOURCE_PATH, FAKE_TARGET)

        invalid_source_exception_message = "Error while receiving file '{}'. Remote file '{}' " \
                                           "does not exist.".format(FAKE_FULL_HOST_SOURCE_PATH,
                                                                    FAKE_SOURCE)

        self.assertEqual(cex.exception.message, invalid_source_exception_message)

    def test_transfer_file_send_mode_invalid_source(self):
        """Test transfer in send mode with invalid source."""
        with self.assertRaises(Exception) as cex:
            RsyncManager.transfer_file(FAKE_PATH, FAKE_TARGET)

        invalid_source_path_exception_message = "Specified path '{}' does not exist.".format(
            FAKE_PATH)

        self.assertRegexpMatches(cex.exception.message, invalid_source_path_exception_message)

    @mock.patch(MOCK_SEND)
    def test_transfer_file_valid_send(self, mock_send):
        """
        Test transfer file in send mode with valid parameters.

        :param mock_send: mock of RsyncManager send function.
        """
        mock_send.return_value = self.rsync_output

        send_result = RsyncManager.transfer_file(FAKE_PATH, FAKE_TARGET)

        self.assertTrue(isinstance(send_result, RsyncOutput))

    @mock.patch(MOCK_RECEIVE)
    def test_transfer_file_valid_receive(self, mock_receive):
        """
        Test transfer file in receive mode with valid parameters.

        :param mock_receive: mock of RsyncManager receive function.
        """
        mock_receive.return_value = self.rsync_output

        receive_result = RsyncManager.transfer_file(FAKE_FULL_HOST_SOURCE_PATH, FAKE_TARGET)

        self.assertTrue(isinstance(receive_result, RsyncOutput))
