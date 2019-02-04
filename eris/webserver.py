#!/usr/bin/env python3.7

# Copyright (C) 2018-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import gzip
import http.server
import os
import sys
import pickle

import eris.fill3 as fill3
import eris.tools as tools


USAGE = """Usage:
  eris-webserver <directory>

Example:
  eris-webserver my_project
"""


def make_page(body_html, title):
    return (f"<html><head><title>{title}</title></head><body><style>body "
            f"{{ background-color: black; }} </style>{body_html}</body></html>"
           ).encode("utf-8")


class Webserver(http.server.BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        if self.path == "/":
            page = summary_page
        elif "/" in self.path[1:]:
            path, tool = os.path.split(self.path[1:])
            result = index[(path, tool)]
            body = fill3.appearance_as_html(
                fill3.Border(result).appearance_min())
            page = make_page(body, f"{tool} of {path}")
        else:
            return
        self.wfile.write(page)

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        self._set_headers()
        self.wfile.write("posted".encode("utf-8"))


def make_summary_page(project_name, summary):
    summary_html, summary_styles = summary.as_html()
    body_html = ("\n".join(style.as_html() for style in summary_styles)
                 + "\n" + summary_html)
    return make_page(body_html, "Summary of " + project_name)


def run(server_class=http.server.HTTPServer, handler_class=Webserver, port=80):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    print("Starting httpd...")
    httpd.serve_forever()


def main():
    global summary_page, index
    if len(sys.argv) == 1:
        print(USAGE)
        sys.exit(1)
    project_path = os.path.abspath(sys.argv[1])
    os.chdir(project_path)
    project_name = os.path.basename(project_path)
    pickle_path = os.path.join(project_path, tools.CACHE_PATH,
                               "summary.pickle")
    with gzip.open(pickle_path, "rb") as file_:
        screen = pickle.load(file_)
    summary_page = make_summary_page(project_name, screen._summary)
    index = {}
    for row in screen._summary._column:
        for result in row:
            index[(result.path[2:], result.tool.__name__)] = result.result
    run()


if __name__ == "__main__":
    main()
