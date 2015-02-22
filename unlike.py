
import os
from collections import Iterable, defaultdict
from functools import namedtuple
import argparse
import re

import colorama


FileInfo = namedtuple('FileInfo', ['path', 'file', 'info'])

colorama.init()


class FolderMerger():
    """ Compares two folder crawls and calculates differences between them.
    """

    def __init__(self, left, right):
        self.left = left
        self.right = right

    @staticmethod
    def _get_canonical_name(fi, base):
        return os.path.relpath(os.path.join(fi.path, fi.file), start=base)

    def merge(self, show_left_only=False, show_right_only=False, show_both=False, summarize=False):
        file_map = defaultdict(lambda: [None, None])

        for i, crawler in enumerate([self.left, self.right]):
            for fi in crawler:
                canonical_name = self._get_canonical_name(fi, base=crawler.root)
                file_map[canonical_name][i] = fi

        left_only = []
        right_only = []
        both = []

        for t in file_map.values():
            if t[0] is None:
                right_only.append(t[1])
            elif t[1] is None:
                left_only.append(t[0])
            else:
                both.append(os.path.join(t[1].path, t[1].file))

        if show_left_only:
            print('')
            print('Files only in left folder:')
            folders = defaultdict(int)
            for file in sorted(left_only, key=lambda li: os.path.join(li.path, li.file).lower()):
                if summarize:
                    folders[file.path] += 1
                else:
                    print('\t {}'.format(os.path.join(file.path, file.file)))
            if summarize:
                for folder in sorted(folders.keys(), key=lambda k: k.lower()):
                    count = folders[folder]
                    print('\t {}: {} file{}'.format(folder, count, 's' if count > 1 else ''))

        if show_right_only:
            print('')
            print('Files only in right folder:')
            folders = defaultdict(int)
            for file in sorted(right_only, key=lambda li: os.path.join(li.path, li.file).lower()):
                if summarize:
                    folders[file.path] += 1
                else:
                    print('\t {}'.format(os.path.join(file.path, file.file)))
            if summarize:
                for folder in sorted(folders.keys(), key=lambda k: k.lower()):
                    count = folders[folder]
                    print('\t {}: {} file{}'.format(folder, count, 's' if count > 1 else ''))

        if show_both:
            print('')
            print('Files in both folders:')
            folders = defaultdict(int)
            for file in sorted(both, key=lambda li: os.path.join(li.path, li.file).lower()):
                if summarize:
                    folders[file.path] += 1
                else:
                    print('\t {}'.format(os.path.join(file.path, file.file)))
            if summarize:
                for folder in sorted(folders.keys(), key=lambda k: k.lower()):
                    count = folders[folder]
                    print('\t {}: {} file{}'.format(folder, count, 's' if count > 1 else ''))

        print('Left only: {}'.format(len(left_only)))
        print('Right only: {}'.format(len(right_only)))
        print('In both: {}'.format(len(both)))
        print('Total (by len): {}'.format(len(list(file_map.keys()))))
        print('Total (by sum): {}'.format(len(left_only) + len(right_only) + len(both)))


class FolderCrawler():
    """ Crawls a folder, listing every file encountered there.
    """

    CSI = '\x1b['

    def __init__(self, root: str):
        self.root = root
        self.filters = []
        """ Filter chain """
        self.file_map = {}

    def add_filter(self, method):
        """ Adds a filter method to the filter chain. The method must accept one parameter: the file name to be checked.
        The method must return True if the file should be maintained or False if it shouldn't be yielded.
        """
        if callable(method):
            self.filters.append(method)
        return self

    @staticmethod
    def pos(x, y):
        """ Moves cursor to position (x, y)
        """
        return FolderCrawler.CSI + '{};{}H'.format(y, x)

    @staticmethod
    def linestart():
        """ Moves cursor to the beginning of the current line.
        """
        return FolderCrawler.CSI + '0G'

    def _filter(self, path, filename):
        """ Run the filter chain for the specified file.
        """
        for f in self.filters:
            if not f(os.path.relpath(path, start=self.root), filename):
                return False
        return True

    def iter_files(self) -> Iterable:
        """ Iterate through all files in a folder.
        """
        for path, dirs, files in os.walk(self.root):
            for fname in files:
                if self._filter(path, fname):
                    yield (path, fname)

    def __iter__(self):
        return self.stat_files()

    def stat_files(self) -> Iterable:
        """ Iterate through all files in a folder, returning tuples of FileInfo.
        """
        for path, file in self.iter_files():
            info = os.stat(os.path.join(path, file))
            yield FileInfo(path, file, info)

    def dump(self):
        for i, path, file, info in ((i, t.path, t.file, t.info) for i, t in enumerate(self.stat_files())):
            print(os.path.join(path, file))
            # print('{}{}'.format(self.linestart(), i), end='', flush=True)

    def make_map(self):
        self.file_map = {
            os.path.relpath(os.path.join(fi.path, fi.file), start=self.root): fi
            for fi in self.stat_files()
        }


def filter_out_ignored_files(ignore_list):

    def _filter_out(path, filename):
        filename = os.path.join(path, filename)
        for ignore_pat in ignore_list:
            if re.search(ignore_pat, filename) is not None:
                return False
        return True

    if len(ignore_list) > 0:
        return _filter_out
    else:
        return None


def make_filter_of_ignored_files(args):
    ignore_list = []
    if args.ignore_list:
        with open(args.ignore_list) as ignore_file:
            ignore_list = [line.strip() for line in ignore_file if len(line.strip()) > 0]
    return filter_out_ignored_files(ignore_list)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('left', action='store', metavar='left_folder', help='the left folder')
    parser.add_argument('right', action='store', metavar='right_folder', help='the right folder')
    parser.add_argument('-l', '--left-only', action='store_true', help='show files only in left folder')
    parser.add_argument('-r', '--right-only', action='store_true', help='show files only in right folder')
    parser.add_argument('-b', '--both', action='store_true', help='show only files present in both folders',
                        dest='both')
    parser.add_argument('-s', '--summarize', action='store_true', help='group files by folder')
    parser.add_argument('-i', '--ignore-list', action='store', help='file with list of patterns to ignore')
    return parser.parse_args()


def main():
    args = parse_args()

    ignore_fn = make_filter_of_ignored_files(args)

    fs_left = FolderCrawler(args.left)
    fs_left.add_filter(ignore_fn)
    fs_left.make_map()

    fs_right = FolderCrawler(args.right)
    fs_left.add_filter(ignore_fn)
    fs_right.make_map()

    fm = FolderMerger(fs_left, fs_right)
    fm.merge(show_left_only=args.left_only, show_right_only=args.right_only, show_both=args.both,
             summarize=args.summarize)


if __name__ == '__main__':
    main()
