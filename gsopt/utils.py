'''
General utilities and helper functions
'''

import os
import datetime

def get_last_modified_time(file_path):
    return os.path.getmtime(file_path)


def get_last_modified_time_as_datetime(file_path):
    return datetime.datetime.fromtimestamp(get_last_modified_time(file_path))