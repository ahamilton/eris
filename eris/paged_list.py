# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import functools
import gzip
import os
import pickle


class PagedList:

    def __init__(self, list_, pages_dir, page_size, cache_size):
        self.pages_dir = pages_dir  # An empty or non-existant directory.
        self.page_size = page_size
        self.cache_size = cache_size
        self._len = len(list_)
        tmp_dir = pages_dir + ".tmp"
        os.makedirs(tmp_dir)
        if len(list_) == 0:
            pages = [[]]
        else:
            pages = (list_[start:start+self.page_size]
                     for start in range(0, len(list_), self.page_size))
        for index, page in enumerate(pages):
            pickle_path = os.path.join(tmp_dir, str(index))
            with gzip.open(pickle_path, "wb") as file_:
                pickle.dump(page, file_, protocol=pickle.HIGHEST_PROTOCOL)
        self.page_count = index + 1
        os.rename(tmp_dir, self.pages_dir)
        self._get_page = functools.lru_cache(maxsize=cache_size)(self._get_page)

    def __len__(self):
        return self._len

    def _get_page(self, index):  # This is cached, see __init__.
        pickle_path = os.path.join(self.pages_dir, str(index))
        with gzip.open(pickle_path, "rb") as file_:
            return pickle.load(file_)

    def __getitem__(self, index):
        if type(index) == slice:
            start, stop, step = index.indices(self._len)
            start_page_index, start_page_offset = divmod(start, self.page_size)
            stop_page_index, stop_page_offset = divmod(stop, self.page_size)
            if stop_page_index == self.page_count:
                stop_page_index -= 1
                stop_page_offset = self.page_size
            if start_page_index == stop_page_index:
                return (self._get_page(start_page_index)
                        [start_page_offset:stop_page_offset])
            else:
                result = self._get_page(start_page_index)[start_page_offset:]
                middle_pages = (self._get_page(page_index) for page_index in
                                range(start_page_index+1, stop_page_index))
                for page in middle_pages:
                    result.extend(page)
                result.extend(
                    self._get_page(stop_page_index)[:stop_page_offset])
                return result
        else:
            page_index, page_offset = divmod(index, self.page_size)
            return self._get_page(page_index)[page_offset]

    def __getstate__(self):  # Don't pickle the lru_cache.
        state = self.__dict__.copy()
        del state["_get_page"]
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self._get_page = \
            functools.lru_cache(maxsize=self.cache_size)(self._get_page)
