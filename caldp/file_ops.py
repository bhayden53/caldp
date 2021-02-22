import sys
import os
import glob
import shutil
import tarfile
import boto3
import threading
from caldp import process
from caldp import log


def get_output_dir(output_uri):
    """Returns full path to output folder """
    if output_uri.startswith("file"):
        output_dir = output_uri.split(":")[-1]
    elif output_uri.startswith("s3"):
        output_dir = os.path.abspath("outputs")
    return output_dir


def find_files(ipppssoot):
    search_fits = f"{ipppssoot}/*.fits"
    search_tra = f"{ipppssoot}/*.tra"
    search_prev = f"{ipppssoot}/previews/*"
    file_list = list(glob.glob(search_fits))
    file_list.extend(list(glob.glob(search_tra)))
    file_list.extend(list(glob.glob(search_prev)))
    return file_list


def make_tar(file_list, ipppssoot):
    tar = ipppssoot + ".tar.gz"
    log.info("Creating tarfile: ", tar)
    if os.path.exists(tar):
        os.remove(tar)  # clean up from prev attempts
    with tarfile.open(tar, "x:gz") as t:
        for f in file_list:
            t.add(f)
    log.info("Tar successful: ", tar)
    tar_dest = os.path.join(ipppssoot, tar)
    shutil.copy(tar, ipppssoot)  # move tarfile to outputs/{ipst}
    os.remove(tar)
    return tar_dest


def upload_tar(tar, output_path):
    client = boto3.client("s3")
    parts = output_path[5:].split("/")
    bucket, prefix = parts[0], "/".join(parts[1:])
    objectname = prefix + "/" + os.path.basename(tar)
    log.info(f"Uploading: s3://{bucket}/{objectname}")
    if output_path.startswith("s3"):
        with open(tar, "rb") as f:
            client.upload_fileobj(f, bucket, objectname, Callback=ProgressPercentage(tar))


class ProgressPercentage(object):
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            sys.stdout.write("\r%s  %s / %s  (%.2f%%)" % (self._filename, self._seen_so_far, self._size, percentage))
            sys.stdout.flush()


# def clean_up(file_list, ipppssoot, dirs=None):
#     print("Cleaning up...")
#     for f in file_list:
#         try:
#             os.remove(f)
#         except FileNotFoundError:
#             pass
#     if dirs is not None:
#         for d in dirs:
#             subdir = os.path.abspath(f"outputs/{ipppssoot}/{d}")
#             os.rmdir(subdir)
#     print("Done.")


def tar_outputs(ipppssoot, output_uri):
    working_dir = os.getcwd()
    output_path = process.get_output_path(output_uri, ipppssoot)
    output_dir = get_output_dir(output_uri)
    os.chdir(output_dir)  # create tarfile with ipst/*fits as top dir
    file_list = find_files(ipppssoot)
    tar = make_tar(file_list, ipppssoot)
    upload_tar(tar, output_path)
    os.chdir(working_dir)
    # clean_up(file_list, ipppssoot, dirs=["previews"])
    if output_uri.startswith("file"):  # test cov only
        return tar, file_list  # , local_outpath