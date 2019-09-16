# Copyright (C) 2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import functools
import os
import pickle
import shutil


class PagedList:

    def __init__(self, list_, pages_dir, page_size, cache_size, exist_ok=False,
                 open_func=open):
        self.pages_dir = pages_dir  # An empty or non-existant directory.
        self.page_size = page_size
        self.cache_size = cache_size
        self.open_func = open_func
        self._len = len(list_)
        tmp_dir = pages_dir + ".tmp"
        if exist_ok:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            shutil.rmtree(pages_dir, ignore_errors=True)
        os.makedirs(tmp_dir)
        pages = ([[]] if len(list_) == 0 else
                 (list_[start:start+self.page_size]
                  for start in range(0, len(list_), self.page_size)))
        for index, page in enumerate(pages):
            pickle_path = os.path.join(tmp_dir, str(index))
            with self.open_func(pickle_path, "wb") as file_:
                pickle.dump(page, file_, protocol=pickle.HIGHEST_PROTOCOL)
        self.page_count = index + 1
        os.rename(tmp_dir, self.pages_dir)
        self._setup_page_cache()

    def __len__(self):
        return self._len

    def _get_page(self, index):  # This is cached, see setup_page_cache.
        pickle_path = os.path.join(self.pages_dir, str(index))
        with self.open_func(pickle_path, "rb") as file_:
            return pickle.load(file_)

    def __getitem__(self, index):
        if isinstance(index, slice):
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
                return (self._get_page(start_page_index)[start_page_offset:] +
                        [line for page_index in
                         range(start_page_index+1, stop_page_index)
                         for line in self._get_page(page_index)] +
                        self._get_page(stop_page_index)[:stop_page_offset])
        else:
            page_index, page_offset = divmod(index, self.page_size)
            return self._get_page(page_index)[page_offset]

    def _setup_page_cache(self):
        self._get_page = functools.lru_cache(self.cache_size)(self._get_page)

    def __getstate__(self):  # Don't pickle the lru_cache.
        state = self.__dict__.copy()
        del state["_get_page"]
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self._setup_page_cache()
